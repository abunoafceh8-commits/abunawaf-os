# -*- coding: utf-8 -*-
"""محرك صيد العملاء المحتملين — يقرأ نتائج بحث حقيقية عبر r.jina.ai + Bing،
يفك روابط Bing المحوّلة، ويرشّح المنشورات التي يطلب أصحابها خدمة فعلية."""
import httpx, json, re, base64, time, hashlib, os

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
cl = httpx.Client(headers={"User-Agent": UA}, timeout=75, follow_redirects=True)

# (الوصف، الاستعلام، المنصة، الخدمة المرتبطة)
QUERIES = [
    ("حساب مخترق على إكس",        '"حسابي مخترق" site:x.com',            "X (تويتر)", "استعادة حساب مسروق"),
    ("حساب مسروق على إكس",        '"حسابي مسروق" site:x.com',            "X (تويتر)", "استعادة حساب مسروق"),
    ("حساب موقوف على إكس",        '"حسابي موقوف" site:x.com',            "X (تويتر)", "استعادة حساب موقوف"),
    ("طلب هكر أخلاقي",            '"هكر اخلاقي" site:x.com',             "X (تويتر)", "اختراق/استعادة"),
    ("ابتزاز على إكس",            '"ابتزاز" "صور" site:x.com',           "X (تويتر)", "مكافحة ابتزاز"),
    ("حساب مخترق رديت",           'site:reddit.com hacked instagram account help', "Reddit", "استعادة حساب مسروق"),
    ("حساب مسروق رديت عربي",      'site:reddit.com "حسابي" اختراق',      "Reddit", "استعادة حساب مسروق"),
    ("طلب خدمة حراج",             'site:haraj.com.sa استرجاع حساب',      "حراج", "استعادة حساب مسروق"),
    ("فك باند سناب حراج",         'site:haraj.com.sa فك باند سناب',      "حراج", "استعادة حساب موقوف"),
    ("استرجاع حساب منتديات",      '"استرجاع حساب" "مخترق" منتدى',        "منتديات", "استعادة حساب مسروق"),
    ("منتدى اختراق حساب",         '"تم اختراق حسابي" منتدى سعودي',       "منتديات", "استعادة حساب مسروق"),
    ("ابتزاز الكتروني مساعدة",    '"اتعرض للابتزاز" مساعدة',             "ويب/تعليقات", "مكافحة ابتزاز"),
    ("تهديد بنشر صور",            '"يهددني" "صور" مساعدة حساب',          "ويب/تعليقات", "مكافحة ابتزاز"),
    ("كشف هوية حساب مجهول",       '"كشف هوية" حساب مجهول طلب',           "ويب/منتديات", "كشف هوية OSINT"),
    ("حساب منتحل شخصيتي",         '"ينتحل شخصيتي" حساب بلاغ',            "ويب/منتديات", "إغلاق حسابات منتحلة"),
    ("حساب شخص متوفي",            '"حساب" "متوفي" اغلاق حساب',           "ويب/منتديات", "إغلاق حسابات المتوفين"),
    ("هاتفي مخترق",               '"هاتفي مخترق" فحص',                   "ويب/منتديات", "فحص أمني للجهاز"),
    ("أبحث عن هكر سعودي",         '"ابحث عن هكر" سعودي',                 "ويب", "اختراق/استعادة"),
    ("مطلوب خبير أمن سيبراني",    '"مطلوب" "خبير امن سيبراني" خدمات',    "ويب", "خدمات أمن سيبراني"),
    ("تسريب بياناتي",             '"بياناتي" "مسربة" ماذا افعل',         "ويب", "حماية وتأمين"),
    ("تيك توك موقوف",             '"حسابي موقوف" تيك توك site:tiktok.com', "TikTok", "استعادة حساب موقوف"),
    ("انستقرام مخترق",            '"حسابي مخترق" انستقرام site:instagram.com', "Instagram", "استعادة حساب مسروق"),
    ("حسابي انسرق",               '"حسابي انسرق" ساعدوني',                "ويب/منتديات", "استعادة حساب مسروق"),
    ("تبند حسابي",                '"تبند حسابي" وش الحل',                 "ويب/منتديات", "استعادة حساب موقوف"),
    ("أحد يعرف هكر",              '"احد يعرف هكر" اتفق معه',              "ويب/منتديات", "اختراق/استعادة"),
    ("محتاج هكر ثقة",             '"محتاج هكر" ثقة',                     "ويب/منتديات", "اختراق/استعادة"),
    ("أبي أستعيد حسابي",          '"ابي استعيد حسابي"',                   "ويب/منتديات", "استعادة حساب مسروق"),
    ("حسابي معلق",                '"حسابي معلق" في الانستقرام',           "ويب/منتديات", "استعادة حساب موقوف"),
    ("شخص يبتزني",                '"شخص يبتزني" ماذا افعل',               "ويب/منتديات", "مكافحة ابتزاز"),
    ("تهديد بصوري",               '"يهددني بصوري"',                       "ويب/منتديات", "مكافحة ابتزاز"),
    ("حسابي اخترق وايميل",        '"تم اختراق ايميلي" استرجاع',           "ويب/منتديات", "استعادة حساب مسروق"),
    ("سناب مقفل",                 '"سنابي مقفل" فك',                      "ويب/منتديات", "استعادة حساب موقوف"),
    ("حساب تيك توك مسروق",        '"حسابي في التيك توك" اخترق',           "ويب/منتديات", "استعادة حساب مسروق"),
    ("انستقرام موقوف",            '"الانستقرام" "حسابي موقوف"',           "ويب/منتديات", "استعادة حساب موقوف"),
    ("طلب كشف هوية",              '"كشف هوية" حساب "مقابل"',              "ويب/منتديات", "كشف هوية OSINT"),
    ("تتبع شخص مجهول",            '"تتبع" "شخص" "حساب" مجهول',            "ويب/منتديات", "كشف هوية OSINT"),
    ("بلاغ حساب منتحل",           '"حساب منتحل" باسمي بلاغ',              "ويب/منتديات", "إغلاق حسابات منتحلة"),
    ("حساب مزعج",                 '"حساب مزعج" "كيف ابلغ"',               "ويب/منتديات", "إغلاق حسابات منتحلة"),
    ("مخترق جوال",                '"جوال مخترق" "برنامج تجسس"',           "ويب/منتديات", "فحص أمني للجهاز"),
    ("reddit hacked account",     'site:reddit.com "my account was hacked" help', "Reddit", "استعادة حساب مسروق"),
    ("reddit sextortion",         'site:reddit.com "sextortion" help me', "Reddit", "مكافحة ابتزاز"),
    ("twitter hacked arabic",     '"تم اختراق حسابي" site:x.com',         "X (تويتر)", "استعادة حساب مسروق"),
    ("twitter محتاج مساعدة",      '"محتاج مساعدة" "حسابي" site:x.com',    "X (تويتر)", "استعادة حساب مسروق"),
    ("snapchat locked",           '"snapchat" "account locked" site:reddit.com', "Reddit", "استعادة حساب موقوف"),
    ("instagram disabled",        '"instagram disabled" site:reddit.com', "Reddit", "استعادة حساب موقوف"),
    ("حراج خدمات استرجاع",        'site:haraj.com.sa "هكر"',              "حراج", "اختراق/استعادة"),
    ("X: حسابي انسرق",          '"حسابي انسرق" site:x.com',                "X (تويتر)", "استعادة حساب مسروق"),
    ("X: سرقوا حسابي",          '"سرقوا حسابي" site:x.com',                "X (تويتر)", "استعادة حساب مسروق"),
    ("X: هكروا حسابي",          '"هكروا حسابي" site:x.com',                "X (تويتر)", "استعادة حساب مسروق"),
    ("X: تبند حسابي",           '"تبند حسابي" site:x.com',                 "X (تويتر)", "استعادة حساب موقوف"),
    ("X: حسابي مقفل",           '"حسابي مقفل" site:x.com',                 "X (تويتر)", "استعادة حساب موقوف"),
    ("X: يهددني",               '"يهددني" site:x.com',                     "X (تويتر)", "مكافحة ابتزاز"),
    ("X: ابتزاز",               '"ابتزاز" "حسابي" site:x.com',             "X (تويتر)", "مكافحة ابتزاز"),
    ("X: تكفون ساعدوني",        '"تكفون" "حسابي" site:x.com',              "X (تويتر)", "استعادة حساب مسروق"),
    ("X: استرجاع حساب",         '"استرجاع حساب" site:x.com',               "X (تويتر)", "استعادة حساب مسروق"),
    ("X: حسابي موقوف",          '"حسابي موقوف" site:twitter.com',          "X (تويتر)", "استعادة حساب موقوف"),
    ("تلجرام طلبات",            '"استرجاع حساب" site:t.me',                "Telegram", "استعادة حساب مسروق"),
    ("تلجرام ابتزاز",           '"ابتزاز" site:t.me',                      "Telegram", "مكافحة ابتزاز"),
    ("مشكلة حسابي بالتفصيل",   '"حسابي" "مخترق" "وش اسوي"',             "ويب/منتديات", "استعادة حساب مسروق"),
    ("سرقوا حسابي",             '"سرقوا حسابي"',                          "ويب/منتديات", "استعادة حساب مسروق"),
    ("هكروا حسابي",             '"هكروا حسابي"',                          "ويب/منتديات", "استعادة حساب مسروق"),
    ("قفلوا حسابي",             '"قفلوا حسابي"',                          "ويب/منتديات", "استعادة حساب موقوف"),
    ("أحتاج مساعدة عاجلة",      '"محتاج مساعده" "حساب" "اختراق"',        "ويب/منتديات", "استعادة حساب مسروق"),
    ("تهديد بفضحي",             '"يهددني" "بفضح"',                        "ويب/منتديات", "مكافحة ابتزاز"),
    ("نشر صوري",                '"ينشر صوري" "بلاغ"',                     "ويب/منتديات", "مكافحة ابتزاز"),
    ("حساب انتحل",              '"انتحل" "حسابي" "انستقرام"',            "ويب/منتديات", "إغلاق حسابات منتحلة"),
    ("بلاغ حساب مبروك",         '"حساب" "مزعج" "بلاغ" تويتر',            "ويب/منتديات", "إغلاق حسابات منتحلة"),
    ("استشارة أمن سيبراني",     '"استشارة" "امن سيبراني" سعر',            "ويب", "خدمات أمن سيبراني"),
    ("فحص جوال مخترق",          '"افحص" "جوالي" "مخترق"',                 "ويب/منتديات", "فحص أمني للجهاز"),
    ("طلبات في تلجرام",         '"استرجاع حساب" "تلجرام" "قناة"',         "ويب", "استعادة حساب مسروق"),
]

STRONG = ["مخترق","مسروق","موقوف","مقفل","مبتز","ابتزاز","اتعرض للابتزاز","يهددني","استرجاع حساب","استعادة حساب",
          "فك باند","فك حظر","ساعدوني","مساعده","مساعدة","ابحث عن هكر","هكر اخلاقي","اختراق","منتحل","ينتحل","متوفي","مسربة","محتاج"]
REQUEST = ["ساعدوني","مساعدة","مساعده","ابحث","مطلوب","محتاج","احتاج","هل من","كيف ارجع","وش الحل","الحل","اريد","أريد","ابي","أبي"]
NEGATIVE = ["بنك الرياض","جمعية","وزارة","ابشر","أبشر","توكلنا","قوى","ناجز","الضمان","التأمينات","مدرستي","نور","قياس","السجل المدني","الجامعة","المستشفى","نتائج","وظائف","وظيفة","السوق","مباراة","اسهم","أسهم"]

# نطاقات صفحات الدعم/القواميس/المحتوى الرسمي — تُستبعد لأنها ليست عملاء
BLOCKED_DOMAINS = [
    "help.x.com","support.google.com","support.microsoft.com","linkedin.com/help","facebook.com/help",
    "messenger.com/help","help.instagram.com","help.twitter.com","help.snapchat.com","support.snapchat.com",
    "help.tiktok.com","arabdict.com","wikipedia.org","youtube.com/results","play.google.com","apps.apple.com",
    "support.apple.com","help.whatsapp.com","faq.whatsapp.com","support.discord.com","reddit.com/login",
    "accounts.google.com","x.com/i/","twitter.com/i/","about.meta.com","help.yahoo.com","account.microsoft.com",
]
# مسارات المنشورات الفردية = إشارة قوية لوجود عميل حقيقي
POST_PATTERNS = [r"x\.com/[^/]+/status/\d+", r"twitter\.com/[^/]+/status/\d+", r"reddit\.com/r/[^/]+/comments/",
                 r"haraj\.com\.sa/\d+", r"instagram\.com/p/", r"tiktok\.com/@[^/]+/video/"]
FORUM_HINTS = ["montada","vb.","forum","absba","adslgate","hawamer","saudi","منتدى","community","threads"]

PLATFORM_DOMAIN = {
    "x.com": "X (تويتر)", "twitter.com": "X (تويتر)", "reddit.com": "Reddit", "haraj.com.sa": "حراج",
    "instagram.com": "Instagram", "tiktok.com": "TikTok", "snapchat.com": "Snapchat", "facebook.com": "Facebook",
    "t.me": "Telegram", "youtube.com": "YouTube", "linkedin.com": "LinkedIn",
}

def decode_bing(u):
    """يفك روابط Bing ck/a المحوّلة إلى الرابط الأصلي"""
    m = re.search(r"[?&]u=a1([A-Za-z0-9_\-=]+)", u)
    if not m:
        return u
    s = m.group(1)
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        out = base64.urlsafe_b64decode(s).decode("utf-8", "ignore")
        if out.startswith("http"):
            return out
    except Exception:
        pass
    return u

def parse_md(text, fallback_platform):
    """يستخرج نتائج Bing من مخرجات r.jina.ai (Markdown)"""
    items = []
    blocks = re.split(r"\n\s*\d+\.\s+", text)
    for b in blocks[1:]:
        m = re.search(r"##\s*\[(.+?)\]\((https?://[^\)]+)\)", b, re.S)
        if not m:
            continue
        title = re.sub(r"[*#\[\]]", "", m.group(1)).strip()
        url = decode_bing(m.group(2))
        rest = b[m.end():].strip().replace("\n", " ")
        snippet = rest[:400]
        items.append({"title": title, "url": url, "snippet": snippet})
    return items

def platform_of(url):
    for d, name in PLATFORM_DOMAIN.items():
        if d in url:
            return name
    return "ويب"

def score(title, snippet, platform):
    txt = (title + " " + snippet)
    s = 25
    hits = [w for w in STRONG if w in txt]
    s += min(40, len(hits) * 12)
    if any(w in txt for w in REQUEST):
        s += 22
    if platform in ("X (تويتر)", "Reddit", "حراج", "TikTok", "Instagram", "منتديات"):
        s += 8
    if any(w in txt for w in NEGATIVE):
        s -= 45
    if "هكر اخلاقي" in txt or "استرجاع حسابات" in txt:
        s -= 18   # منافس يعلن خدماته، ليس عميلاً
    return max(0, min(99, s)), hits


def kind_of(url, txt):
    """تصنيف النتيجة: منشور عميل / منافس / محتوى إرشادي"""
    if any(re.search(p, url) for p in POST_PATTERNS):
        base = "post"
    elif any(h in url for h in FORUM_HINTS):
        base = "forum"
    else:
        base = "page"
    if ("هكر اخلاقي" in txt or "استرجاع الحسابات" in txt or "خدماتنا" in txt) and base != "post":
        return "منافس"
    if base in ("post", "forum"):
        return "منشور/موضوع"
    return "صفحة"

def service_of(txt, default):
    rules = [("مكافحة ابتزاز", ["ابتزاز","مبتز","يهددني","تهديد"]),
             ("كشف هوية OSINT", ["كشف هوية","كشف شخص","مجهول","تتبع","انتحال","ينتحل"]),
             ("استعادة حساب موقوف", ["موقوف","مقفل","فك باند","فك حظر","محظور","معطل"]),
             ("استعادة حساب مسروق", ["مخترق","مسروق","اختراق","تم اختراق"]),
             ("إغلاق حسابات المتوفين", ["متوفي","وفاة"]),
             ("فحص أمني للجهاز", ["هاتفي مخترق","جوال","جهاز","تجسس","فايروس"]),
             ("حماية وتأمين", ["تسريب","مسربة","حماية","تأمين","كلمة المرور"])]
    for svc, kws in rules:
        if any(k in txt for k in kws):
            return svc
    return default

def fetch_query(label, q, platform, service):
    try:
        target = "https://www.bing.com/search?q=" + httpx.QueryParams({"q": q, "setlang": "ar", "count": "20"})["q"]
        r = cl.get("https://r.jina.ai/" + target)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        items = parse_md(r.text, platform)
        out = []
        for it in items:
            if not it["url"].startswith("http"):
                continue
            if any(b in it["url"] for b in BLOCKED_DOMAINS):
                continue
            p = platform_of(it["url"])
            txt = it["title"] + " " + it["snippet"]
            sc, hits = score(it["title"], it["snippet"], p)
            kind = kind_of(it["url"], txt)
            if kind == "منشور/موضوع":
                sc = min(99, sc + 14)
            elif kind == "صفحة":
                sc = max(0, sc - 18)
            out.append({
                "title": it["title"][:220],
                "url": it["url"],
                "snippet": it["snippet"][:300],
                "platform": p,
                "kind": kind,
                "service": service_of(txt, service),
                "score": sc,
                "signals": hits,
                "query": label,
                "id": hashlib.md5(it["url"].encode()).hexdigest()[:10],
            })
        return out, "ok"
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"

def qualify(it):
    """بوابة الجودة: لا نعرض إلا نتائج تحمل إشارة طلب خدمة حقيقية"""
    u = it["url"]
    if re.match(r"^https?://[^/]+/?$", u):
        return False
    if "/hashtag/" in u:
        return True
    strong = bool(it["signals"])
    if not strong:
        return False
    if it["kind"] == "منشور/موضوع" and it["score"] >= 35:
        return True
    if it["platform"] in ("X (تويتر)", "حراج", "TikTok", "Instagram", "Snapchat") and it["score"] >= 50:
        return True
    if it["score"] >= 62 and it["platform"] in ("ويب", "منتديات"):
        return True
    return False


def main():
    all_items, sources = [], []
    for label, q, platform, service in QUERIES:
        items, status = fetch_query(label, q, platform, service)
        sources.append({"query": label, "q": q, "status": status, "found": len(items)})
        all_items.extend(items)
        print(f"[{status}] {label}: {len(items)}", flush=True)
        time.sleep(3.0)
    # إزالة التكرار حسب الرابط، مع دمج الإشارات
    uniq = {}
    for it in all_items:
        k = it["url"].split("?")[0].rstrip("/")
        if k in uniq:
            uniq[k]["signals"] = sorted(set(uniq[k]["signals"] + it["signals"]))
            uniq[k]["score"] = min(99, max(uniq[k]["score"], it["score"]) + 2)
        else:
            uniq[k] = it
    kept = [v for v in uniq.values() if qualify(v)]
    leads = sorted(kept, key=lambda x: -x["score"])
    for l in leads:
        l["tier"] = "ساخن" if l["score"] >= 75 else ("دافئ" if l["score"] >= 55 else "مراقبة")
        l["action"] = ("ردّ على المنشور واعرض المساعدة المجانية أولاً" if l["kind"] == "منشور/موضوع"
                       else "افتح المصدر وتحقق من الطلب قبل التواصل")
    meta = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "engine": "Bing SERP عبر r.jina.ai (قارئ صفحات)",
            "queries": len(QUERIES), "ok_queries": sum(1 for s in sources if s["status"] == "ok"),
            "raw_results": len(all_items), "unique_found": len(uniq), "unique_leads": len(leads),
            "hot": sum(1 for l in leads if l["tier"] == "ساخن"),
            "warm": sum(1 for l in leads if l["tier"] == "دافئ")}
    json.dump({"meta": meta, "sources": sources, "leads": leads, "all": sorted(uniq.values(), key=lambda x:-x["score"])},
              open("data/leads_raw.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))
    for l in leads[:15]:
        print(f"  {l['score']:3} {l['tier']:6} {l['platform'][:12]:14} {l['service'][:20]:22} {l['url'][:70]}")


if __name__ == "__main__":
    main()
