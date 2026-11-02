# -*- coding: utf-8 -*-
"""إعداد قاعدة بيانات Supabase الحيّة لمنصة أبو نواف (مخطط + RLS + دوال + بذر بيانات)."""
import json, os, hashlib, urllib.request, time

TOK = os.environ.get("SUPABASE_PAT", "")
if not TOK:
    raise SystemExit("ضع مفتاح الإدارة في متغيّر البيئة SUPABASE_PAT")
REF = "kneluxgbulzvnedjarsf"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
TEAM_KEY = "abunawaf-2026"
BASE = "/home/user/abunawaf"


def q(sql, retries=3):
    data = json.dumps({"query": sql}).encode()
    for i in range(retries):
        req = urllib.request.Request(API, data=data, headers={
            "Authorization": f"Bearer {TOK}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode()
                return json.loads(body) if body.strip() else []
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:600]
            if i == retries - 1:
                raise RuntimeError(f"HTTP {e.code}: {msg}\nSQL: {sql[:300]}")
            time.sleep(2)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2)


SCHEMA = r"""
create extension if not exists pgcrypto;

create table if not exists public.os_leads (
  id text primary key,
  title text,
  url text unique,
  snippet text,
  platform text,
  kind text,
  service text,
  query text,
  score int default 0,
  tier text,
  signals jsonb default '[]'::jsonb,
  action text,
  source text default 'harvest',
  status text default 'جديد',
  owner text,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.os_keywords (
  id bigserial primary key,
  keyword text unique,
  intent text,
  google_hits int default 0,
  bing_hits int default 0,
  engines jsonb default '[]'::jsonb,
  seeds jsonb default '[]'::jsonb,
  popularity int default 0,
  difficulty int default 0,
  buyer_intent int default 0,
  opportunity numeric default 0,
  relevance int default 100,
  created_at timestamptz default now()
);

create table if not exists public.os_notes (
  id bigserial primary key,
  lead_id text references public.os_leads(id) on delete cascade,
  body text not null,
  author text default 'الفريق',
  created_at timestamptz default now()
);

create table if not exists public.os_events (
  id bigserial primary key,
  kind text not null,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.os_config (key text primary key, value text not null);

create index if not exists os_leads_score_idx on public.os_leads (score desc);
create index if not exists os_leads_status_idx on public.os_leads (status);
create index if not exists os_kw_opp_idx on public.os_keywords (opportunity desc);

create or replace function public.os_hash_key(p_key text) returns text
language sql immutable set search_path = public, extensions as $$
  select encode(extensions.digest(coalesce(p_key,''),'sha256'),'hex') $$;

create or replace function public.os_check_key(p_key text) returns boolean
language sql stable security definer set search_path = public, extensions as $$
  select exists (select 1 from public.os_config where key='team_hash' and value = public.os_hash_key(p_key))
$$;

create or replace function public.os_touch() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

drop trigger if exists os_leads_touch on public.os_leads;
create trigger os_leads_touch before update on public.os_leads
for each row execute function public.os_touch();

create or replace function public.os_add_lead(p jsonb, p_key text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare v_id text; v_url text;
begin
  if not public.os_check_key(p_key) then
    return jsonb_build_object('ok', false, 'error', 'مفتاح الفريق غير صحيح');
  end if;
  v_url := nullif(trim(coalesce(p->>'url','')), '');
  v_id  := nullif(trim(coalesce(p->>'id','')), '');
  if v_url is null then return jsonb_build_object('ok', false, 'error', 'الرابط مطلوب'); end if;
  if v_id is null then v_id := md5(v_url); end if;
  insert into os_leads (id,title,url,snippet,platform,kind,service,query,score,tier,signals,action,source,status,owner,notes)
  values (v_id, p->>'title', v_url, p->>'snippet', coalesce(p->>'platform','يدوي'), coalesce(p->>'kind','منشور/موضوع'),
          coalesce(p->>'service','غير محدد'), p->>'query', coalesce((p->>'score')::int, 50), coalesce(p->>'tier','دافئ'),
          coalesce(p->'signals','[]'::jsonb), p->>'action', coalesce(p->>'source','manual'),
          coalesce(nullif(p->>'status',''),'جديد'), p->>'owner', p->>'notes')
  on conflict (url) do update set
     title = coalesce(excluded.title, os_leads.title),
     service = coalesce(excluded.service, os_leads.service),
     score = greatest(os_leads.score, excluded.score),
     updated_at = now()
  returning id into v_id;
  insert into os_events(kind,payload) values ('lead_add', jsonb_build_object('id',v_id,'url',v_url));
  return jsonb_build_object('ok', true, 'id', v_id);
end $$;

create or replace function public.os_set_status(p_id text, p_status text, p_key text, p_owner text default null, p_notes text default null)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare n int;
begin
  if not public.os_check_key(p_key) then
    return jsonb_build_object('ok', false, 'error', 'مفتاح الفريق غير صحيح');
  end if;
  update os_leads set status = coalesce(nullif(p_status,''), status),
                      owner = coalesce(nullif(p_owner,''), owner),
                      notes = coalesce(nullif(p_notes,''), notes)
   where id = p_id;
  get diagnostics n = row_count;
  insert into os_events(kind,payload) values ('status', jsonb_build_object('id',p_id,'status',p_status,'n',n));
  return jsonb_build_object('ok', n > 0, 'updated', n);
end $$;

create or replace function public.os_add_note(p_lead text, p_body text, p_key text, p_author text default 'الفريق')
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare v_id bigint;
begin
  if not public.os_check_key(p_key) then
    return jsonb_build_object('ok', false, 'error', 'مفتاح الفريق غير صحيح');
  end if;
  if coalesce(trim(p_body),'') = '' then return jsonb_build_object('ok', false, 'error', 'الملاحظة فارغة'); end if;
  insert into os_notes(lead_id, body, author) values (p_lead, p_body, coalesce(nullif(p_author,''),'الفريق'))
  returning id into v_id;
  return jsonb_build_object('ok', true, 'id', v_id);
end $$;

create or replace function public.os_stats()
returns jsonb language sql stable security definer set search_path = public, extensions as $$
  select jsonb_build_object(
    'leads', (select count(*) from os_leads),
    'by_status', (select coalesce(jsonb_object_agg(status, c),'{}'::jsonb) from (select status, count(*) c from os_leads group by status) s),
    'by_tier', (select coalesce(jsonb_object_agg(tier, c),'{}'::jsonb) from (select tier, count(*) c from os_leads group by tier) t),
    'notes', (select count(*) from os_notes),
    'keywords', (select count(*) from os_keywords),
    'last_event', (select max(created_at) from os_events)
  )
$$;

-- الصلاحيات
grant usage on schema public to anon, authenticated;
grant select on public.os_leads, public.os_keywords, public.os_notes to anon, authenticated;
grant insert, update, delete on public.os_leads, public.os_keywords to authenticated, service_role;
grant all on public.os_leads, public.os_keywords, public.os_notes, public.os_events, public.os_config to service_role;
grant usage, select on all sequences in schema public to anon, authenticated, service_role;
grant execute on function public.os_add_lead(jsonb,text) to anon, authenticated;
grant execute on function public.os_set_status(text,text,text,text,text) to anon, authenticated;
grant execute on function public.os_add_note(text,text,text,text) to anon, authenticated;
grant execute on function public.os_stats() to anon, authenticated;

-- RLS: قراءة عامة، كتابة عبر الدوال فقط
alter table public.os_leads enable row level security;
alter table public.os_keywords enable row level security;
alter table public.os_notes enable row level security;
alter table public.os_events enable row level security;
alter table public.os_config enable row level security;

drop policy if exists os_leads_read on public.os_leads;
create policy os_leads_read on public.os_leads for select to anon, authenticated using (true);
drop policy if exists os_kw_read on public.os_keywords;
create policy os_kw_read on public.os_keywords for select to anon, authenticated using (true);
drop policy if exists os_notes_read on public.os_notes;
create policy os_notes_read on public.os_notes for select to anon, authenticated using (true);
"""


def seed():
    leads = json.load(open(f"{BASE}/site/data/leads.json", encoding="utf-8"))["leads"]
    rows = []
    for l in leads:
        rows.append({
            "id": l.get("id"), "title": l.get("title"), "url": l.get("url"),
            "snippet": l.get("snippet"), "platform": l.get("platform"), "kind": l.get("kind"),
            "service": l.get("service"), "query": l.get("query"), "score": l.get("score", 0),
            "tier": l.get("tier"), "signals": l.get("signals", []), "action": l.get("action"),
            "source": "harvest", "status": "جديد",
        })
    sql = ("insert into public.os_leads (id,title,url,snippet,platform,kind,service,query,score,tier,signals,action,source,status) "
           "select id,title,url,snippet,platform,kind,service,query,score,tier,signals,action,source,status "
           "from jsonb_to_recordset(%s::jsonb) as x(id text,title text,url text,snippet text,platform text,kind text,"
           "service text,query text,score int,tier text,signals jsonb,action text,source text,status text) "
           "on conflict (url) do nothing;") % ("'" + json.dumps(rows, ensure_ascii=False).replace("'", "''") + "'")
    print("leads →", q(sql), "rows in:", len(rows))

    kws = json.load(open(f"{BASE}/site/data/keywords.json", encoding="utf-8"))["keywords"]
    chunk, n = 400, 0
    for i in range(0, len(kws), chunk):
        part = [{
            "keyword": k["keyword"], "intent": k.get("intent"), "google_hits": k.get("google_hits", 0),
            "bing_hits": k.get("bing_hits", 0), "engines": k.get("engines", []), "seeds": k.get("seeds", []),
            "popularity": k.get("popularity", 0), "difficulty": k.get("difficulty", 0),
            "buyer_intent": k.get("buyer_intent", 0), "opportunity": k.get("opportunity", 0),
            "relevance": k.get("relevance", 100),
        } for k in kws[i:i + chunk]]
        sql = ("insert into public.os_keywords (keyword,intent,google_hits,bing_hits,engines,seeds,popularity,difficulty,buyer_intent,opportunity,relevance) "
               "select keyword,intent,google_hits,bing_hits,engines,seeds,popularity,difficulty,buyer_intent,opportunity,relevance "
               "from jsonb_to_recordset(%s::jsonb) as x(keyword text,intent text,google_hits int,bing_hits int,engines jsonb,"
               "seeds jsonb,popularity int,difficulty int,buyer_intent int,opportunity numeric,relevance int) "
               "on conflict (keyword) do update set opportunity = excluded.opportunity, popularity = excluded.popularity;") % (
               "'" + json.dumps(part, ensure_ascii=False).replace("'", "''") + "'")
        q(sql)
        n += len(part)
        print(f"  keywords {n}/{len(kws)}")

    q(f"insert into public.os_config(key,value) values ('team_hash', '{hashlib.sha256(TEAM_KEY.encode()).hexdigest()}') "
      f"on conflict (key) do update set value = excluded.value;")
    print("stats →", json.dumps(q("select public.os_stats() as s"), ensure_ascii=False)[:400])


if __name__ == "__main__":
    print("== schema ==")
    q(SCHEMA)
    print("ok")
    print("== seed ==")
    seed()
    print("== verify ==")
    print(q("select count(*) c from public.os_leads"), q("select count(*) c from public.os_keywords"))
