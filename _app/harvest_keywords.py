# -*- coding: utf-8 -*-
"""محرك جمع كلمات البحث الحقيقي — Google Suggest + Bing Suggest (بدون مفاتيح API)"""
import httpx, json, time
from collections import defaultdict

SEEDS = [
 "استرجاع حساب","استعادة حساب","حسابي مخترق","حسابي مسروق","حسابي موقوف","حسابي محظور",
 "فك باند","فك حظر","استرجاع حساب سناب شات","استرجاع حساب انستقرام","استرجاع حساب تيك توك",
 "استرجاع حساب تويتر","استرجاع حساب فيس بوك","استرجاع حساب جيميل","استرجاع حساب تلجرام",
 "حساب مقفل","تم اختراق حسابي","استعادة حساب مسروق","رجوع حساب",
 "هكر اخلاقي","هكر اخلاقي سعودي","هاكر اخلاقي","خبير اختراق","اختراق حساب","تهكير حساب",
 "اختراق سناب","اختراق واتساب","اختراق ايميل","كشف هوية حساب","كشف هوية شخص",
 "ابتزاز","ابتزاز الكتروني","ابتزاز الصور","تهديد بنشر صور","كشف مبتز","حل قضية ابتزاز",
 "حذف حساب شخص متوفي","حساب منتحل","انتحال شخصية","حساب وهمي","بلاغ حساب مزعج",
 "فحص اختراق الجوال","هاتفي مخترق","برامج تجسس","حماية الحسابات","تأمين حساب انستقرام",
 "التحقق بخطوتين","كلمات مرور قوية","تسريب بيانات",
 "خدمات امن سيبراني","شركة امن سيبراني السعودية","خبير امن معلومات",
]

ALPHABET = list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي")
QMODS = ["", " كيف", " مضمون", " سعر", " مجاني", " الرياض", " جدة", " السعودية", " 2026", " خدمة"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
cl = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ar-SA,ar;q=0.9"}, timeout=20, follow_redirects=True)

def google_suggest(q):
    try:
        r = cl.get("https://suggestqueries.google.com/complete/search",
                   params={"client": "firefox", "hl": "ar", "gl": "sa", "q": q})
        d = json.loads(r.text)
        return d[1] or []
    except Exception:
        return []

def bing_suggest(q):
    try:
        r = cl.get("https://api.bing.com/osjson.aspx", params={"query": q, "market": "ar-SA"})
        d = r.json()
        return d[1] or []
    except Exception:
        return []

hits = defaultdict(lambda: {"google": 0, "bing": 0, "sources": set(), "parents": set()})
queries_done = 0

def record(seed, suggestions, engine):
    for s in suggestions:
        s = s.strip()
        if not s or len(s) < 4:
            continue
        h = hits[s]
        h[engine] += 1
        h["sources"].add(engine)
        h["parents"].add(seed)

# 1) استعلامات البذور
for s in SEEDS:
    record(s, google_suggest(s), "google")
    record(s, bing_suggest(s), "bing")
    queries_done += 2
    time.sleep(0.1)

# 2) توسيع أبجدي + لواحق
core = SEEDS[:22]
for s in core:
    for ch in ALPHABET[::4]:
        record(s, google_suggest(f"{s} {ch}"), "google")
        queries_done += 1
        time.sleep(0.08)
    for m in QMODS[1:]:
        record(s, google_suggest(s + m), "google")
        record(s, bing_suggest(s + m), "bing")
        queries_done += 2
        time.sleep(0.08)

# 3) توسيع من النتائج
new = [k for k in list(hits.keys()) if " " in k][:60]
for s in new:
    record(s, google_suggest(s), "google")
    queries_done += 1
    time.sleep(0.08)

INTENT_RULES = [
 ("استعادة حساب", ["استرجاع حساب","استعادة حساب","حسابي مخترق","حسابي مسروق","حسابي موقوف","حسابي محظور","فك باند","فك حظر","حساب مقفل","تم اختراق","رجوع حساب","كيف ارجع","قفل حساب"]),
 ("ابتزاز وتهديد", ["ابتزاز","تهديد","نشر صور","فضح","مبتز"]),
 ("كشف هوية / OSINT", ["كشف هوية","كشف شخص","حساب وهمي","انتحال","منتحل","معلومات عن شخص","تتبع"]),
 ("اختراق وأدوات", ["اختراق","تهكير","هاك","هكر","تجسس"]),
 ("حذف وإغلاق حسابات", ["حذف حساب","اغلاق حساب","متوفي","ايقاف حساب"]),
 ("حماية وتأمين", ["حماية","تأمين","التحقق بخطوتين","كلمة مرور","كلمات مرور","تسريب","امان"]),
 ("خدمات تجارية", ["شركة","خدمات","سعر","مضمون","افضل","خبير","معتمد","سعودي","الرياض","جدة"]),
]

def norm(q):
    return q.replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ة","ه")

def classify(q):
    ql = norm(q)
    for name, kws in INTENT_RULES:
        for k in kws:
            if norm(k) in ql:
                return name
    return "عام"

BRAND_HARD = ["جوجل","google","جيميل","gmail","انستقرام","instagram","سناب","snapchat","تيك توك","tiktok","تويتر","twitter","فيس بوك","facebook","واتساب","whatsapp","تلجرام","telegram","يوتيوب","ايكلاود","apple","مايكروسوفت","روبلكس","ببجي","وزارة","حكومة"]

def difficulty(q, g, b):
    score = 45
    words = len(q.split())
    score -= min(25, max(0, (words - 2) * 7))
    if any(br in q for br in BRAND_HARD):
        score += 22
    if any(x in q for x in ["مجاني","كيف","ماذا","معنى","بالانجليزي","pdf","تعريف","صور"]):
        score -= 18
    if any(x in q for x in ["سعر","مضمون","خدمة","شركة","افضل","معتمد","خبير"]):
        score += 10
    score -= min(12, (g + b) * 1.4)
    return max(6, min(96, round(score)))

BUYER_WORDS = ["استرجاع","استعادة","فك باند","فك حظر","حسابي مخترق","حسابي مسروق","حسابي موقوف","كشف هوية","حل قضية","ابتزاز","اختراق حساب","تهكير","خدمة","سعر","مضمون","خبير","شركة"]

def buyer_intent(q, intent):
    s = 30
    if intent in ("استعادة حساب","ابتزاز وتهديد","كشف هوية / OSINT"):
        s += 35
    if intent == "اختراق وأدوات":
        s += 22
    if intent == "حماية وتأمين":
        s += 8
    if any(w in q for w in BUYER_WORDS):
        s += 20
    if any(w in q for w in ["كيف","ماذا","معنى","بالانجليزي","تعريف","pdf","صور","دورة","تعلم"]):
        s -= 25
    if any(w in q for w in ["سعودي","الرياض","جدة","السعودية","مضمون","سعر"]):
        s += 10
    return max(2, min(99, s))

out = []
for q, h in hits.items():
    if len(q.split()) < 2 and q not in SEEDS:
        continue
    intent = classify(q)
    freq = h["google"] + h["bing"] * 0.8
    vol = min(100, round(12 + freq * 9 + min(len(q.split()), 6) * 2))
    out.append({
        "keyword": q, "intent": intent,
        "google_hits": h["google"], "bing_hits": h["bing"],
        "engines": sorted(h["sources"]),
        "seeds": sorted(h["parents"])[:4],
        "popularity": vol,
        "difficulty": difficulty(q, h["google"], h["bing"]),
        "buyer_intent": buyer_intent(q, intent),
    })
for r in out:
    r["opportunity"] = round(0.55 * r["buyer_intent"] + 0.45 * (100 - r["difficulty"]), 1)
out.sort(key=lambda x: (-x["opportunity"], -x["popularity"]))

meta = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "queries_used": queries_done,
    "engines": ["Google Suggest (hl=ar, gl=sa)", "Bing Suggest (market=ar-SA)"],
    "seeds": len(SEEDS),
    "total_keywords": len(out),
}
json.dump({"meta": meta, "keywords": out}, open("data/keywords.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False))
print("top 20:")
for r in out[:20]:
    print(f"  {r['opportunity']:5} {r['intent'][:14]:16} {r['keyword'][:48]:50} p={r['popularity']} d={r['difficulty']} bi={r['buyer_intent']}")
