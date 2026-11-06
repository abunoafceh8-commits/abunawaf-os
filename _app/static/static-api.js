/* ══════════════════════════════════════════════════════════════
   static-api.js — طبقة توافق + قاعدة بيانات حيّة
   • تعمل المنصة على استضافة ثابتة (GitHub Pages) بنفس واجهات الـAPI.
   • البيانات الأساسية من data/*.json (يحدّثها GitHub Actions).
   • الحالة/الملاحظات/الإضافات تُحفظ في **Supabase Postgres** (مشتركة للفريق).
   • ما يحتاج خادماً (زحف/صيد لحظي) يُوجّه إلى GitHub Actions.
   ══════════════════════════════════════════════════════════════ */
(function () {
  if (!window.STATIC_MODE) return;

  const SB_URL = "__SB_URL__";
  const SB_KEY = "__SB_KEY__";
  const SB_ON = /^https:\/\//.test(SB_URL) && SB_KEY.length > 40;

  const BASE = (function () {
    try {
      const src = document.currentScript && document.currentScript.src;
      if (src) return src.replace(/[^/]+$/, "");
    } catch (e) {}
    return location.origin + location.pathname.replace(/[^/]*$/, "");
  })();
  const D = BASE + "data/";
  const cache = {};
  const origFetch = window.fetch.bind(window);
  const LS_KEY = "abunawaf_manual_leads";
  const TK_KEY = "abunawaf_team_key";
  window.ACTIONS_URL = window.ACTIONS_URL || "https://github.com/abunoafceh8-commits/abunawaf-os/actions";
  window.SB_ON = SB_ON;
  window.SB_URL = SB_URL;

  const norm = (u) => String(u || "").split("?")[0].replace(/\/+$/, "").toLowerCase();
  const tierOf = (s) => (s >= 75 ? "ساخن" : s >= 55 ? "دافئ" : "مراقبة");
  const teamKey = () => localStorage.getItem(TK_KEY) || "";
  const setTeamKey = (k) => localStorage.setItem(TK_KEY, k);

  async function j(name) {
    if (cache[name]) return cache[name];
    const r = await origFetch(D + name, { cache: "no-cache" });
    if (!r.ok) throw new Error("ملف البيانات غير متوفر: " + name);
    cache[name] = await r.json();
    return cache[name];
  }
  const manual = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch (e) { return []; } };
  const saveManual = (list) => localStorage.setItem(LS_KEY, JSON.stringify(list));

  /* ─────────── Supabase ─────────── */
  async function sb(path, init) {
    init = init || {};
    const r = await origFetch(SB_URL + "/rest/v1/" + path, {
      method: init.method || "GET",
      headers: Object.assign({
        apikey: SB_KEY,
        Authorization: "Bearer " + SB_KEY,
        "Content-Type": "application/json"
      }, init.headers || {}),
      body: init.body
    });
    const t = await r.text();
    let d = null;
    try { d = t ? JSON.parse(t) : null; } catch (e) { d = t; }
    if (!r.ok) {
      const msg = (d && (d.message || d.hint || d.error)) || ("HTTP " + r.status);
      const err = new Error(msg); err.status = r.status; err.body = d; throw err;
    }
    return d;
  }

  const REMOTE = { rows: [], byUrl: new Map(), byId: new Map(), stats: null, at: 0, err: null };

  async function refreshRemote(force) {
    if (!SB_ON) return REMOTE;
    if (!force && Date.now() - REMOTE.at < 45000 && REMOTE.rows.length) return REMOTE;
    try {
      const rows = await sb("os_leads?select=id,url,title,platform,service,score,tier,status,owner,notes,source,updated_at&order=score.desc&limit=1000");
      REMOTE.rows = rows || [];
      REMOTE.byUrl = new Map(REMOTE.rows.map(r => [norm(r.url), r]));
      REMOTE.byId = new Map(REMOTE.rows.map(r => [r.id, r]));
      try { REMOTE.stats = await sb("rpc/os_stats", { method: "POST", body: "{}" }); } catch (e) {}
      REMOTE.at = Date.now(); REMOTE.err = null;
    } catch (e) {
      REMOTE.err = e.message;
    }
    paintDbStatus();
    return REMOTE;
  }
  window.refreshRemote = refreshRemote;

  function paintDbStatus() {
    const dot = document.getElementById("dbDot"), txt = document.getElementById("dbTxt"), meta = document.getElementById("dbMeta");
    if (!txt) return;
    if (!SB_ON) { if (dot) dot.style.background = "#f59e0b"; txt.textContent = "قاعدة البيانات: غير مهيّأة (وضع ثابت)"; return; }
    if (REMOTE.err) { if (dot) dot.style.background = "#ef4444"; txt.textContent = "قاعدة البيانات: انقطاع — " + REMOTE.err.slice(0, 40); return; }
    if (dot) dot.style.background = "#22c55e";
    txt.textContent = "قاعدة البيانات: متصلة ✔";
    const s = REMOTE.stats || {};
    if (meta) meta.textContent = `${s.leads ?? REMOTE.rows.length} عميل · ${s.keywords ?? "—"} كلمة · ${s.notes ?? 0} ملاحظة` +
      (s.last_event ? ` · آخر نشاط ${String(s.last_event).slice(0, 16).replace("T", " ")}` : "");
  }

  function mergeRemote(rows) {
    if (!REMOTE.rows.length) return rows;
    const seen = new Set();
    const out = rows.map(r => {
      const m = REMOTE.byUrl.get(norm(r.url)) || REMOTE.byId.get(String(r.id));
      seen.add(norm(r.url));
      if (!m) return Object.assign({}, r, { status: r.status || "جديد" });
      return Object.assign({}, r, {
        status: m.status || "جديد", owner: m.owner || "", db_id: m.id, db_notes: m.notes || "",
        updated_at: m.updated_at
      });
    });
    REMOTE.rows.forEach(m => {
      if (seen.has(norm(m.url))) return;
      out.push({
        id: m.id, db_id: m.id, title: m.title || "عميل من قاعدة البيانات", url: m.url, snippet: m.notes || "",
        platform: m.platform || "—", kind: m.source === "manual" ? "مُضاف يدوياً" : "منشور/موضوع",
        service: m.service || "—", score: m.score || 0, tier: m.tier || tierOf(m.score || 0),
        signals: [], action: "تواصل مباشرة", status: m.status || "جديد", owner: m.owner || "",
        query: "قاعدة البيانات", fromDb: true
      });
    });
    const win = Number(params.window || 0);
    return out.sort((a, b) => {
      const g = r => (r.age_hours !== undefined && r.age_hours !== null && win && r.age_hours <= win) ? 0
                   : (r.age_hours === undefined || r.age_hours === null ? 2 : 1);
      const d = g(a) - g(b);
      return d !== 0 ? d : (b.score || 0) - (a.score || 0);
    });
  }

  /* ─────────── Leads ─────────── */
  async function leadsResponse(params) {
    const d = await j("leads.json");
    await refreshRemote(false);
    let base = params.get("include_raw") === "true" ? (d.all || d.leads) : d.leads;
    let rows = mergeRemote(base.slice());
    // إضافات محلية فقط إن لم تكن القاعدة متاحة
    if (!SB_ON || REMOTE.err) {
      const seen = new Set(rows.map(l => norm(l.url)));
      manual().filter(m => !seen.has(norm(m.url))).forEach(m => rows.push(Object.assign({
        kind: "مُضاف يدوياً", signals: [], snippet: m.note || "", title: m.name || "عميل محتمل",
        score: 75, action: "تواصل مباشرة عبر القناة المذكورة", platform: "مباشر",
        service: "—", query: "إدخال محلي", manual: true, status: "جديد"
      }, m, { tier: tierOf(+m.score || 75) })));
    }
    rows = rows.map(l => Object.assign({}, l, { tier: l.tier || tierOf(+l.score || 0), status: l.status || "جديد" }));
    const f = { platforms: [...new Set(rows.map(r => r.platform))].sort(), services: [...new Set(rows.map(r => r.service))].sort() };
    f.tiers = { "ساخن": 0, "دافئ": 0, "مراقبة": 0 };
    rows.forEach(r => { f.tiers[r.tier] = (f.tiers[r.tier] || 0) + 1; });
    f.statuses = {};
    rows.forEach(r => { f.statuses[r.status] = (f.statuses[r.status] || 0) + 1; });
    f.total = rows.length; f.raw_total = (d.all || []).length;
    f.meta = d.meta || {};
    const winSel = +(params.get("window") || d.meta?.window_hours || 48);
    f.inside_window = rows.filter(r => r.age_hours != null && r.age_hours <= winSel).length;
    f.older_count = rows.filter(r => r.age_hours != null && r.age_hours > winSel).length;
    f.undated_count = rows.filter(r => r.age_hours == null).length;
    f.x_total = rows.filter(r => (r.platform || "").includes("X")).length;
    const tier = params.get("tier"), plat = params.get("platform"), svc = params.get("service"),
          q = params.get("q"), st = params.get("status"), win = +(params.get("window") || 0),
          focus = params.get("focus") || "";
    if (tier) rows = rows.filter(r => r.tier === tier);
    if (plat) rows = rows.filter(r => r.platform === plat);
    if (svc) rows = rows.filter(r => r.service === svc);
    if (st) rows = rows.filter(r => r.status === st);
    if (q) { const qq = q.toLowerCase(); rows = rows.filter(r => ((r.title || "") + (r.snippet || "") + r.url).toLowerCase().includes(qq)); }
    if (focus === "x") rows = rows.filter(r => (r.platform || "").includes("X"));
    if (win) {
      const keepUndated = params.get("undated") === "1" || params.get("undated") === "true";
      rows = rows.filter(r => (r.age_hours != null && r.age_hours <= win) || (keepUndated && r.age_hours == null));
    }
    rows = rows.slice().sort((a, b) => {
      const ka = a.age_hours == null ? 1e6 : a.age_hours, kb = b.age_hours == null ? 1e6 : b.age_hours;
      return ka !== kb ? ka - kb : (b.score || 0) - (a.score || 0);
    });
    const min = +(params.get("min_score") || 0);
    rows = rows.filter(r => (r.score || 0) >= min);
    const limit = +(params.get("limit") || 500);
    return { meta: d.meta || {}, sources: d.sources || [], facets: f, count: rows.length, leads: rows.slice(0, limit), live: SB_ON && !REMOTE.err };
  }

  async function addLead(body) {
    const p = typeof body === "string" ? JSON.parse(body || "{}") : (body || {});
    const url = String(p.url || "").trim();
    if (!url) return { ok: false, error: "الرابط مطلوب" };
    if (SB_ON) {
      const payload = {
        id: p.id, title: p.title || p.name || "عميل محتمل", url,
        snippet: p.snippet || p.note || "", platform: p.platform || "مباشر",
        kind: "منشور/موضوع", service: p.service || "غير محدد", query: "إضافة الفريق",
        score: Math.min(100, Math.max(0, parseInt(p.score, 10) || 75)), tier: tierOf(parseInt(p.score, 10) || 75),
        signals: [], action: "تواصل مباشرة عبر القناة المذكورة", source: "manual", status: p.status || "جديد"
      };
      try {
        const r = await sb("rpc/os_add_lead", { method: "POST", body: JSON.stringify({ p: payload, p_key: teamKey() }) });
        if (r && r.ok) { await refreshRemote(true); return { ok: true, id: r.id, live: true }; }
        if (r && r.error) { const e = new Error(r.error); e.needKey = /مفتاح/.test(r.error); throw e; }
      } catch (e) {
        if (e.needKey || (e.body && /مفتاح/.test(String(e.body.message || "")))) {
          const err = new Error("مفتاح الفريق مطلوب أو غير صحيح"); err.needKey = true; throw err;
        }
        // انقطاع شبكة → احفظ محلياً بدل الفشل
        const list = manual(); list.push(p); saveManual(list);
        return { ok: true, local: true, warn: "تعذّر الوصول لقاعدة البيانات — حُفظ محلياً" };
      }
    }
    const list = manual(); list.push(p); saveManual(list);
    return { ok: true, item: list[list.length - 1], local: true };
  }

  async function setStatus(id, status, owner, notes) {
    if (!SB_ON) return { ok: true, local: true };
    const r = await sb("rpc/os_set_status", {
      method: "POST",
      body: JSON.stringify({ p_id: String(id), p_status: status, p_key: teamKey(), p_owner: owner || null, p_notes: notes || null })
    });
    if (r && r.ok) { await refreshRemote(true); return r; }
    const e = new Error((r && r.error) || "فشل التحديث"); e.needKey = /مفتاح/.test(e.message); throw e;
  }

  async function notes(leadId, body) {
    if (!SB_ON) return body ? { ok: false, error: "الملاحظات تحتاج قاعدة البيانات" } : [];
    if (!body) {
      return await sb("os_notes?lead_id=eq." + encodeURIComponent(leadId) + "&select=id,body,author,created_at&order=created_at.desc&limit=50");
    }
    const r = await sb("rpc/os_add_note", {
      method: "POST",
      body: JSON.stringify({
        p_lead: String(body.lead_id || leadId || ""),
        p_body: body.body || body.text || "",
        p_key: teamKey(),
        p_author: body.author || "الفريق"
      })
    });
    if (r && r.ok) return r;
    const e = new Error((r && r.error) || "فشل الحفظ"); e.needKey = /مفتاح/.test(e.message); throw e;
  }

  function kwResponse(params) {
    return j("keywords.json").then(d => {
      let rows = d.keywords;
      const intent = params.get("intent"), q = params.get("q");
      if (intent) rows = rows.filter(k => k.intent === intent);
      if (q) rows = rows.filter(k => k.keyword.toLowerCase().includes(q.toLowerCase()));
      const sortKey = { opportunity: "opportunity", popularity: "popularity", difficulty: "difficulty", buyer_intent: "buyer_intent" }[params.get("sort") || "opportunity"];
      rows = rows.slice().sort((a, b) => (sortKey === "difficulty" ? a.difficulty - b.difficulty : b[sortKey] - a[sortKey]));
      const intents = {};
      d.keywords.forEach(k => { intents[k.intent] = (intents[k.intent] || 0) + 1; });
      return { meta: d.meta, intents, total: d.keywords.length, count: rows.length, keywords: rows.slice(0, +(params.get("limit") || 300)) };
    });
  }

  const ROUTES = {
    "/api/overview": async () => {
      const o = Object.assign({}, await j("overview.json"));
      await refreshRemote(false);
      o.live = { on: SB_ON && !REMOTE.err, stats: REMOTE.stats, error: REMOTE.err };
      if (REMOTE.stats && REMOTE.stats.leads != null) {
        o.leads = Object.assign({}, o.leads, {
          total: REMOTE.stats.leads,
          hot: (REMOTE.stats.by_tier && REMOTE.stats.by_tier["ساخن"]) || o.leads.hot
        });
      }
      return o;
    },
    "/api/db/stats": async () => { await refreshRemote(true); return { on: SB_ON, stats: REMOTE.stats, error: REMOTE.err, rows: REMOTE.rows.length }; },
    "/api/leads": (p) => leadsResponse(p),
    "/api/leads/status": () => j("overview.json").then(o => ({ job: { running: false, error: null }, last_run: o.leads.generated_at, static: true })),
    "/api/candidates": async (u) => {
      const params = new URL(u, location.origin).searchParams;
      const d = await j("x_candidates.json").catch(() => ({ cands: [] }));
      const win = +(params.get("window") || 0), min = +(params.get("min_score") || 20);
      const items = (d.cands || []).filter(c => !c.web && c.age != null && c.score >= min && c.author && (!win || c.age <= win))
        .map(c => ({ id: c.id, author: c.author, score: c.score, age_hours: Math.round(c.age * 10) / 10,
                     text: c.text || "", url: `https://x.com/${c.author}/status/${c.id}`, signals: c.signals || [] }))
        .sort((a, b) => a.age_hours - b.age_hours);
      return { count: items.length, window: win || null, generated_at: d.generated_at, items: items.slice(0, 120) };
    },
    "/api/leads/refresh": () => ({ status: "static", message: "التحديث الحي يحتاج خادماً. شغّل سير العمل من GitHub Actions.", actions: window.ACTIONS_URL }),
    "/api/leads/add": (p, body) => addLead(body),
    "/api/leads/set-status": (p, body) => { const b = JSON.parse(body || "{}"); return setStatus(b.id, b.status, b.owner, b.notes); },
    "/api/notes": (p, body) => notes(p.get("lead_id"), body ? JSON.parse(body) : null),
    "/api/keywords": (p) => kwResponse(p),
    "/api/keywords/clusters": () => j("clusters.json"),
    "/api/keywords/expand": async (p) => {
      const seed = p.get("seed") || "";
      if (SB_ON && seed) {
        try {
          const r = await origFetch(SB_URL + "/functions/v1/api/expand?seed=" + encodeURIComponent(seed),
            { headers: { apikey: SB_KEY, Authorization: "Bearer " + SB_KEY } });
          const d = await r.json();
          if (r.ok && d && Array.isArray(d.merged) && d.merged.length) return Object.assign(d, { live: true });
        } catch (e) {}
      }
      const x = await j("expansions.json");
      return x[seed] || { seed, merged: [], count: 0, raw: { google: [], bing: [] }, note: "لم تُجمَّع بعد — جرّب بذرة أخرى" };
    },
    "/api/x-queries": () => j("x_queries.json"),
    "/api/seo/audit": () => j("audit.json"),
    "/api/seo/fixes": () => j("fixes.json"),
    "/api/tools": () => j("tools.json"),
    "/api/social": () => j("social.json"),
    "/api/competitors": () => j("competitors.json"),
    "/api/read-url": async (p) => {
      const target = p.get("url") || "";
      if (!SB_ON) return { error: "قراءة الروابط تحتاج الخادم أو قاعدة البيانات الحيّة.", url: target };
      const r = await origFetch(SB_URL + "/functions/v1/api/read-url?url=" + encodeURIComponent(target),
        { headers: { apikey: SB_KEY, Authorization: "Bearer " + SB_KEY } });
      const d = await r.json();
      if (!r.ok || d.error) throw new Error(d.error || ("HTTP " + r.status));
      return d;
    }
  };

  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (!url.startsWith("/api/")) return origFetch(input, init);
    const [path, qs] = url.split("?");
    const params = new URLSearchParams(qs || "");
    const body = init && init.body;
    if (path === "/api/report") {
      const r = await origFetch(D + "report.md");
      return new Response(await r.text(), { status: 200, headers: { "Content-Type": "text/markdown; charset=utf-8" } });
    }
    const route = ROUTES[path];
    if (!route) return new Response(JSON.stringify({ error: "مسار غير متاح في النسخة الثابتة: " + path }), { status: 404, headers: { "Content-Type": "application/json" } });
    try {
      const out = await route(params, body);
      const code = out && out.error && !out.leads ? 502 : 200;
      return new Response(JSON.stringify(out), { status: code, headers: { "Content-Type": "application/json; charset=utf-8" } });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message, needKey: !!e.needKey }), { status: e.needKey ? 401 : 500, headers: { "Content-Type": "application/json" } });
    }
  };

  window.DB = { refresh: refreshRemote, key: teamKey, setKey: setTeamKey, on: SB_ON };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('a[href^="/api/leads/export.csv"]').forEach(a => a.href = D + "leads.csv");
    document.querySelectorAll('a[href^="/api/keywords/export.csv"]').forEach(a => a.href = D + "keywords.csv");
    document.querySelectorAll('a[href="/api/report"]').forEach(a => a.href = D + "report.md");
    refreshRemote(true);
  });
})();
