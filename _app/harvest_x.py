# -*- coding: utf-8 -*-
"""
harvest_x.py — محرّك الصيد v4
────────────────────────────────────────────────────────────────────────────
• نافذة زمنية دقيقة: WINDOW_HOURS (24 / 48 / 72 / 168) — تُحسب من طابع الوقت
  الحقيقي للمنشور (Snowflake ID أو تاريخ RSS) لا من ترتيب البحث.
• تركيز على X: استعلامات site:x.com / twitter.com + إثراء كل منشور عبر
  cdn.syndication.twimg.com (النص + التاريخ + صاحب الحساب).
• مصطلحات واسعة: 36 عبارة أساسية + 12 لهجية + 12 هاشتاق + صيغ سؤال = ~250 استعلاماً.
• مصادر متعددة: Yahoo (سريع) → Bing (متصفح عند الحاجة) → Google News RSS.
• تقييم صارم: يرفض الإنجليزية وغير ذي الصلة، ويكافئ الإشارات القوية والحداثة.

    python harvest_x.py                       # 48 ساعة
    WINDOW_HOURS=24 FOCUS=x python harvest_x.py
    MAX_QUERIES=60 python harvest_x.py
"""
import asyncio, base64, json, os, re, sys, time, hashlib, urllib.parse, urllib.request
from datetime import datetime, timezone
import html as HTML

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
WINDOW = int(os.environ.get("WINDOW_HOURS", "48"))
FOCUS = os.environ.get("FOCUS", "x").lower()          # x | all
MAXQ = int(os.environ.get("MAX_QUERIES", "0")) or None
USE_BING = os.environ.get("USE_BING", "0") == "1"
MAX_ENRICH = int(os.environ.get("MAX_ENRICH", "260"))
MIN_LEADS = int(os.environ.get("MIN_LEADS", "18"))
AUTO_WIDEN = os.environ.get("AUTO_WIDEN", "1") == "1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
NOW = datetime.now(timezone.utc)
TW_EPOCH = 1288834974657          # بداية Snowflake في تويتر

# ─────────────────────────── قاموس المصطلحات ───────────────────────────
CORE = [
    "حسابي مسروق", "حسابي مخترق", "تم اختراق حسابي", "حسابي مقفل", "حسابي موقوف",
    "حسابي محظور", "حسابي انسرق", "سرقوا حسابي", "هكروا حسابي", "اخترقوا حسابي",
    "فك باند", "فك حظر", "رفع باند", "رفع حظر", "ابتزاز الكتروني", "مبتز",
    "يهددني بصور", "ينشر صوري", "انتحال شخصيتي", "حساب مزيف باسمي",
    "استرجاع حساب", "استعادة حساب", "ما اقدر ادخل حسابي", "نسيت كلمة السر",
    "كلمة السر تغيرت", "الرمز ما يوصل", "التحقق بخطوتين", "اختراق واتساب",
    "اختراق سناب", "اختراق انستقرام", "اختراق تيك توك", "كشف هوية",
    "معرفة صاحب حساب", "حساب وهمي", "شخص مجهول يهددني", "متجري تهكر",
]
DIALECT = [
    "ابغى استرجع حسابي", "تكفون ساعدوني حسابي", "وش الحل حسابي مقفل",
    "الحقوني حسابي انسرق", "احد يعرف كيف ارجع حسابي", "حسابي ماراح اقدر ادخله",
    "محتاج مساعدة بخصوص حسابي", "ضايع حسابي", "علّقوا حسابي ظلم",
    "حسابي بالايقاف", "موقعي مخترق", "متجري تهكر",
]
HASHTAGS = [
    "#حسابي_مسروق", "#تم_اختراق_حسابي", "#اختراق_حسابي", "#حسابي_مخترق",
    "#ابتزاز_الكتروني", "#ابتزاز", "#فك_باند", "#سناب_مقفل", "#حسابي_موقوف",
    "#انستقرام_مقفل", "#تيك_توك_موقوف", "#تهكير",
]
QUESTION = ["كيف", "الحل", "مساعدة", "تكفون", "ضروري", "وش اسوي", "احد يفيدني", "استفسار"]


def build_queries_rss():
    """استعلامات مقتبسة دقيقة — الأنسب لمحرك Bing RSS (أعلى إنتاجية وجودة)."""
    qs = []
    for t in CORE:
        qs.append(f'"{t}"')
    for t in DIALECT:
        qs.append(f'"{t}"')
    for t in ["اخترقوا حسابي", "تهكر حسابي", "سرقوا حسابي", "مبتزني", "يهددني بصوري",
              "انتحل شخصيتي", "سنابي مقفل", "انستقرامي موقوف", "تيك توكي موقوف",
              "حسابي مسروق ساعدوني", "كيف ارجع حسابي", "وش الحل حسابي مقفل",
              "قفلوا حسابي", "علّقوا حسابي", "حسابي بالايقاف", "ابتزوني",
              "صورة خاصة تهديد", "حسابي في الانستقرام مسروق", "تم تهكير حسابي",
              "حسابي انسرق مني", "احد يهكر حساب", "استرجاع حساب مسروق",
              "تم اختراق حسابي في", "اخترقوا حسابي", "سنابي انسرق", "انستقرامي انسرق",
              "تيك توكي انسرق", "واتسابي مخترق", "ابتزني شخص", "يهددني بنشر",
              "حسابي مقفل ولا اعرف السبب", "قفلوا حسابي بدون سبب", "ارسلوا لي رسالة تهديد",
              "حسابي تهكر ورجعت", "انتحل شخصيتي وحساب مزيف", "شخص يهددني بنشر صوري",
              "حسابي في الانستقرام مقفل", "سنابي محظور", "حسابي بالتيك توك موقوف",
              # نية شراء مباشرة (أعلى قيمة تجارية)
              "احد يعرف شخص يرجع حساب", "مين يرجع حساب", "ابي شخص يرجع حسابي",
              "في احد يسترجع حسابات", "احد يفك باند", "ابحث عن هاكر", "مطلوب هاكر",
              "من يقدر يرجع حسابي", "ابي احد يهكر حساب", "شخص يسترجع حساب سناب",
              "ابغى استرجع حسابي من الهكر", "احد يساعدني في اختراق حساب"]:
        qs.append(f'"{t}"')
    for h in HASHTAGS:
        qs.append(h)
    for t in CORE[:22]:
        qs.append(t)                      # بلا تنصيص لتغطية أوسع
    seen, out = set(), []
    for q in qs:
        q = q.strip()
        if q and q not in seen:
            seen.add(q); out.append(q)
    return out


def build_queries():
    qs = []
    # 1) X — كل العبارات الأساسية
    for t in CORE:
        qs.append(f'site:x.com "{t}"')
    for t in HASHTAGS:
        qs.append(f'site:x.com "{t}"')
    for t in CORE[:20]:
        qs.append(f'site:x.com {t}')                  # بلا تنصيص = تغطية أوسع
    for t in CORE[:14]:
        qs.append(f'site:twitter.com "{t}"')
    # 2) ويب/منتديات — يلتقط الحالات الطويلة
    if FOCUS != "x":
        for t in CORE[:20]:
            qs.append(f'"{t}" مساعدة')
        qs += DIALECT
    # 3) هاشتاقات مفتوحة
    for h in HASHTAGS[:8]:
        qs.append(h.replace("#", "").replace("_", " "))
    seen, out = set(), []
    for q in qs:
        q = q.strip()
        if q and q not in seen:
            seen.add(q); out.append(q)
    return out[:MAXQ] if MAXQ else out


# ─────────────────────────── قياس الصلة ───────────────────────────
STRONG = {
    "مسروق": 18, "مخترق": 20, "اختراق": 16, "هكر": 14, "تهكر": 16, "انسرق": 18,
    "سرقوا": 16, "نصب": 10, "احتيال": 12, "مبتز": 22, "ابتزاز": 22, "يهددني": 20,
    "صوري": 14, "مقفل": 16, "موقوف": 16, "محظور": 14, "باند": 16, "حظر": 12,
    "استرجاع": 15, "استعادة": 15, "مساعده": 12, "مساعدة": 12, "ساعدوني": 16,
    "الحقوني": 16, "تكفون": 12, "ضروري": 9, "انتحال": 16, "مزيف": 13, "مجهول": 11,
    "كشف": 9, "هوية": 9, "وهمي": 11, "كلمة السر": 12, "كلمة المرور": 12,
    "الرمز": 8, "تحقق": 6, "ما اقدر": 12, "ماراح": 9, "ضايع": 12, "ايقاف": 13,
    "سناب": 9, "انستقرام": 10, "واتساب": 10, "تيك توك": 9, "فيسبوك": 9, "تويتر": 8,
}
NEG = [
    "إيران", "ايران", "الحوثي", "غزة", "غزه", "انتخابات", "الجيش", "الحكومة", "الرئيس",
    "مرتزقة", "المسؤول الثقافي", "فتوى", "الاحتلال", "دعاء", "سياسي", "تصويت","وظائف", "توظيف", "شراء متابعين", "زيادة متابعين", "لعبة", "games", "bounty",
       "دورة", "كورس", "كتاب", "فيلم", "مسلسل", "مباراة", "نتيجة", "سعر", "بيع",
       "الأسهم", "عملة", "crypto", "airdrop", "تداول", "زواج", "تعارف",
       # إعلانات/موردون/أخبار — ليست عملاء
       "تنبيه أمني", "عاجل", "اشترك", "تابعنا", "للبيع", "بأسعار", "خدماتنا", "نقدم لكم",
       "أفضل شركة", "مضمون", "خصم", "عروض", "رابط التسجيل", "سجل الآن", "خدمات اختراق",
       "اختراق حسابات", "هكر محترف", "نحن نقدم", "للتواصل واتساب", "واتساب 05", "خدمة سريعة",
       # عروض خدمات (لا عملاء)
       "ابرق لنا", "متوفر", "احترافيه", "بسعر", "خاص بسرعة", "تواصل خاص", "خدماتنا تشمل",
       "نخدمك", "أسعارنا", "الدفع بعد", "شغل مضمون", "ابعت رسالة", "كلمني خاص"]
# مؤشرات أن الكاتب يتكلم عن مشكلته الشخصية (لا خبر ولا إعلان)
PERSONAL = ["حسابي", "اخترقوا", "سرقوا", "هكروا", "انسرق", "محتاج", "ابغى", "أبغى",
            "ابي ", "أبي ", "تكفون", "ساعدوني", "الحقوني", "ضايع", "ماراح اقدر",
            "ما اقدر ادخل", "يهددني", "مبتزني", "ينشر", "عندي مشكلة", "وش الحل",
            "احد يفيدني", "محتارة", "محبط", "مدري وش اسوي", "خصوصيتي"]
AR_RE = re.compile(r"[\u0600-\u06FF]")


def is_arabic(text):
    t = text or ""
    letters = len(AR_RE.findall(t))
    return letters >= 4 and letters / max(1, len(t)) > 0.15


def snowflake_age(tid):
    """عمر المنشور بالساعات من معرّفه (بدون أي طلب شبكة)."""
    try:
        ms = (int(tid) >> 22) + TW_EPOCH
        return (NOW.timestamp() * 1000 - ms) / 3_600_000
    except Exception:
        return None


NOISE_AUTHORS = {"grok", "absher", "barq", "alinma", "stc", "mobily", "zain", "saudiairlines",
                 "alrajhibank", "snapchat", "instagram", "tiktok", "x", "support", "help"}


ACCOUNT_WORDS = ["حسابي", "حسابه", "حسابها", "حساب ", "سنابي", "سناب", "انستقرام", "انستغرام",
                 "تيك توك", "واتساب", "تويتر", "فيسبوك", "ايميل", "بريدي", "الإيميل", "الايميل",
                 "رقمي", "جوالي", "صوري", "فيديوهاتي", "خصوصيتي"]
DISTRESS = ["مسروق", "مخترق", "اختراق", "هكر", "تهكر", "انسرق", "سرقوا", "مبتز", "ابتزاز",
            "يهددني", "مقفل", "موقوف", "محظور", "باند", "حظر", "انتحال", "مزيف", "مجهول", "وهمي"]


def proximity_ok(text):
    """يشترط أن تكون كلمة الخطر قريبة من كلمة (حساب/منصة/صورة) — يمنع الأخبار والنكات."""
    for w in DISTRESS:
        for m in re.finditer(w, text):
            seg = text[max(0, m.start() - 38): m.end() + 38]
            if any(a in seg for a in ACCOUNT_WORDS):
                return True
    return False


def score_text(text, platform, hours_old=None):
    if not text or not is_arabic(text):
        return 0, []
    t = text.lower()
    if any(n in t for n in NEG):
        return 0, []
    if not proximity_ok(text):
        return 0, []
    signals, score = [], 0
    for k, w in STRONG.items():
        if k in t:
            signals.append(k); score += w
    personal_hits = sum(1 for p in PERSONAL if p in t)
    strong_hits = len(signals)
    # شرط الجودة: مشكلة شخصية واضحة — لا خبر ولا إعلان
    if personal_hits == 0 or strong_hits == 0:
        return 0, []
    if strong_hits < 2 and personal_hits < 2:
        return 0, []
    score += min(12, personal_hits * 4)
    if personal_hits >= 2:
        signals.append("متضرر شخصياً")
    if any(r in t for r in ["محتاج", "ابغى", "أبغى", "ابي", "أبي", "كيف", "وش الحل",
                            "ساعدوني", "تكفون", "احد يعرف", "ضروري", "الحقوني"]):
        score += 9; signals.append("طلب مساعدة")
    if "؟" in text or "?" in text:
        score += 4
    if platform == "X (تويتر)":
        score += 8
    if hours_old is not None:
        if hours_old <= 6: score += 14
        elif hours_old <= 24: score += 10
        elif hours_old <= 48: score += 6
        elif hours_old <= 168: score += 2
    # المنشورات الطويلة (قصص) أقرب لعميل حقيقي
    if len(text) > 120: score += 3
    return min(99, score), signals[:6]


def service_of(text):
    t = text or ""
    if any(k in t for k in ["ابتزاز", "مبتز", "يهددني", "صوري", "ينشر", "فيديو"]): return "مكافحة ابتزاز"
    if any(k in t for k in ["موقوف", "مقفل", "باند", "حظر", "ايقاف", "علّق"]): return "استعادة حساب موقوف"
    if any(k in t for k in ["مجهول", "انتحال", "مزيف", "هوية", "وهمي"]): return "كشف هوية OSINT"
    if any(k in t for k in ["اختراق", "مخترق", "هكر", "تهكر", "موقع", "متجر"]): return "اختراق/تحصين"
    return "استعادة حساب مسروق"


# ─────────────────────────── HTTP ───────────────────────────
def http_get(url, timeout=30, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "ar,en;q=0.8"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def yahoo_search(query, btf=None, n=30, page=1):
    url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&ei=UTF-8&n={n}&b={page}"
    if btf: url += f"&btf={btf}"
    try:
        st, body = http_get(url, timeout=25)
    except Exception:
        return []
    out = []
    for blk in re.findall(r'<li><div class="dd[^"]*algo.*?</li>', body, re.S):
        m = re.search(r'href="[^"]*?RU=([^/]+)/RK=', blk)
        t = re.search(r'<h3[^>]*>(.*?)</h3>', blk, re.S)
        p = re.search(r'<p[^>]*class="[^"]*(?:fz-ms|compText)[^"]*"[^>]*>(.*?)</p>', blk, re.S)
        if not m:
            continue
        out.append({
            "url": urllib.parse.unquote(m.group(1)),
            "title": HTML.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip()[:180] if t else "",
            "snippet": HTML.unescape(re.sub(r"<[^>]+>", " ", p.group(1))).strip()[:360] if p else "",
        })
    return out


def bing_rss(query, count=30):
    """Bing عبر RSS: سريع (HTTP فقط) ويعطي تواريخ حقيقية — المحرّك الأساسي."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&format=rss&count={count}"
    try:
        st, body = http_get(url, timeout=25)
    except Exception:
        return []
    out = []
    for it in re.findall(r"<item>(.*?)</item>", body, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        de = re.search(r"<description>(.*?)</description>", it, re.S)
        if not l:
            continue
        hours = None
        if d:
            try:
                from email.utils import parsedate_to_datetime
                hours = (NOW - parsedate_to_datetime(d.group(1)).astimezone(timezone.utc)).total_seconds() / 3600
            except Exception:
                pass
        out.append({"url": l.group(1).strip(),
                    "title": HTML.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else "",
                    "snippet": HTML.unescape(re.sub(r"<[^>]+>", " ", de.group(1))).strip()[:360] if de else "",
                    "hours_old": hours})
    return out


def news_rss(query, days=2):
    q = urllib.parse.quote(f"{query} when:{days}d")
    try:
        st, body = http_get(f"https://news.google.com/rss/search?q={q}&hl=ar&gl=SA&ceid=SA:ar", timeout=25)
    except Exception:
        return []
    out = []
    for it in re.findall(r"<item>(.*?)</item>", body, re.S)[:12]:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        p = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        if not l: continue
        pub = p.group(1) if p else ""
        hours = None
        try:
            from email.utils import parsedate_to_datetime
            dtv = parsedate_to_datetime(pub)
            hours = (NOW - dtv.astimezone(timezone.utc)).total_seconds() / 3600
        except Exception:
            pass
        out.append({"url": l.group(1).strip(), "title": (t.group(1) if t else "").strip(),
                    "snippet": "", "hours_old": hours})
    return out


TWEET_CACHE = {}


def tweet_details(tid):
    if tid in TWEET_CACHE:
        return TWEET_CACHE[tid]
    res = None
    try:
        st, body = http_get(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&token=a", timeout=18)
        d = json.loads(body)
        created = d.get("created_at") or ""
        hours = None
        if created:
            dtv = datetime.fromisoformat(created.replace("Z", "+00:00"))
            hours = (NOW - dtv).total_seconds() / 3600
        res = {"text": d.get("text") or "", "created_at": created, "hours_old": hours,
               "author": (d.get("user") or {}).get("screen_name") or "",
               "likes": d.get("favorite_count", 0)}
    except Exception:
        res = None
    TWEET_CACHE[tid] = res
    return res


def bing_decode(m):
    s = m.replace("-", "+").replace("_", "/"); s += "=" * (-len(s) % 4)
    try: return base64.b64decode(s).decode("utf-8", "ignore")
    except Exception: return ""


async def bing_batch(queries):
    try:
        from playwright.async_api import async_playwright
    except Exception:
        print("   ⚠ المتصفح غير متوفر — تخطي Bing", flush=True)
        return []
    raw = []
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = await br.new_context(user_agent=UA, locale="ar-SA", viewport={"width": 1366, "height": 900})
        pg = await ctx.new_page()
        for i, q in enumerate(queries, 1):
            try:
                url = ("https://www.bing.com/search?q=" + urllib.parse.quote(q)
                       + "&setlang=ar&cc=SA&count=30&filters=" + urllib.parse.quote('ex1:"ez2"'))
                await pg.goto(url, wait_until="domcontentloaded", timeout=40000)
                await pg.wait_for_timeout(1200)
                html = await pg.content()
                for m in re.findall(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"', html):
                    u = bing_decode(re.search(r"u=a1([A-Za-z0-9_\-]+)", m).group(1)) if "bing.com/ck/a" in m else m
                    if u.startswith("http"):
                        raw.append({"url": u, "title": "", "snippet": "", "query": q})
            except Exception:
                pass
            if i % 10 == 0:
                print(f"   bing {i}/{len(queries)} → {len(raw)}", flush=True)
            await asyncio.sleep(0.8)
        await br.close()
    return raw


# ─────────────────────────── التشغيل ───────────────────────────
def build_x_links():
    """روابط بحث X جاهزة بنافذة زمنية حقيقية (since:) — تُفتح بحساب الفريق وتُظهر كل الجديد فوراً."""
    from datetime import timedelta
    terms = []
    for t in CORE:
        terms.append({"term": t, "type": "عبارة"})
    for t in DIALECT:
        terms.append({"term": t, "type": "لهجة"})
    for t in HASHTAGS:
        terms.append({"term": t, "type": "هاشتاق"})
    intent = ["احد يعرف شخص يرجع حساب", "مين يرجع حساب", "ابي شخص يرجع حسابي",
              "في احد يسترجع حسابات", "احد يفك باند", "من يقدر يرجع حسابي",
              "ابي احد يهكر حساب", "شخص يسترجع حساب سناب"]
    for t in intent:
        terms.append({"term": t, "type": "نية شراء"})
    out = []
    for t in terms:
        row = {"term": t["term"], "type": t["type"], "links": {}}
        for hours in (24, 48, 72, 168, 720):
            since = (NOW - timedelta(hours=hours)).strftime("%Y-%m-%d")
            q = f'{t["term"]} since:{since}'
            row["links"][str(hours)] = "https://x.com/search?q=" + urllib.parse.quote(q) + "&f=live"
        out.append(row)
    return {"generated_at": NOW.isoformat(timespec="seconds"), "count": len(out), "items": out}


def norm(u):
    return u.split("?")[0].rstrip("/").lower()


def x_kind(u):
    if re.search(r"(x|twitter)\.com/[A-Za-z0-9_]+/status/\d+", u): return "status"
    if re.match(r"https?://(www\.)?(x|twitter)\.com/[A-Za-z0-9_]+/?$", u): return "profile"
    return ""


async def main():
    t0 = time.time()
    rss_queries = build_queries_rss()
    queries = build_queries()
    print(f"🔎 {len(rss_queries)} استعلام RSS + {len(queries)} استعلام Yahoo · نافذة {WINDOW} ساعة · تركيز {FOCUS}", flush=True)

    pool, x_status, x_profile = {}, set(), set()

    def absorb(res, q):
        for r in res:
            u = norm(r["url"])
            k = x_kind(u)
            if k == "status": x_status.add(u)
            elif k == "profile": x_profile.add(u)
            prev = pool.get(u)
            if not prev or (not prev.get("snippet") and r.get("snippet")):
                pool[u] = {"url": r["url"], "title": r.get("title", ""), "snippet": r.get("snippet", ""),
                           "query": q, "hours_old": r.get("hours_old")}

    # 1) Bing RSS — المحرّك الأساسي (سريع + يعطي تواريخ)
    for i, q in enumerate(rss_queries, 1):
        absorb(bing_rss(q), q)
        if i % 30 == 0:
            print(f"   rss {i}/{len(rss_queries)} → خام {len(pool)} · X {len(x_status)}", flush=True)
        time.sleep(0.2)

    # 2) Yahoo — تغطية إضافية
    btf = "w" if WINDOW <= 168 else "m"
    for i, q in enumerate(queries, 1):
        absorb(yahoo_search(q, btf=btf), q)
        if i % 40 == 0:
            print(f"   yahoo {i}/{len(queries)} → خام {len(pool)} · X {len(x_status)}", flush=True)
        time.sleep(0.25)

    # 3) Google News RSS
    for q in CORE[:6]:
        for it in news_rss(q, days=max(1, WINDOW // 24)):
            pool.setdefault(norm(it["url"]), {"url": it["url"], "title": it["title"],
                                              "snippet": "", "query": "news", "hours_old": it["hours_old"]})
        time.sleep(0.3)

    print(f"→ خام: {len(pool)} · منشورات X: {len(x_status)} · حسابات X: {len(x_profile)}", flush=True)

    leads, expired = [], 0

    # 4) إثراء منشورات X + فلترة زمنية دقيقة (مرتّبة بالأحدث أولاً)
    def _age(u):
        m = re.search(r"/status/(\d+)", u)
        return snowflake_age(m.group(1)) if m else 1e9
    x_sorted = sorted(x_status, key=_age)[:MAX_ENRICH]
    for u in x_sorted:
        m = re.search(r"/status/(\d+)", u)
        if not m: continue
        tid = m.group(1)
        age = snowflake_age(tid)
        det = tweet_details(tid)
        if det and det["hours_old"] is not None:
            age = det["hours_old"]
        # العمر الحقيقي محسوب دائماً؛ التصفية النهائية حسب النافذة في آخر الخط
        if age is not None and age > 24 * 365:
            continue
        text = (det or {}).get("text") or pool[u]["title"] or pool[u]["snippet"]
        title = (det or {}).get("text") or pool[u]["title"]
        sc, sig = score_text(f"{text} {pool[u]['title']} {pool[u]['snippet']}", "X (تويتر)", age)
        author = (det or {}).get("author") or ""
        if author.lower() in NOISE_AUTHORS:
            continue
        if sc < 50:
            continue
        leads.append({
            "id": tid, "title": (title or "")[:180].replace("\n", " "),
            "url": f"https://x.com/{author}/status/{tid}" if author else pool[u]["url"],
            "snippet": (text or pool[u]["snippet"])[:420].replace("\n", " "),
            "platform": "X (تويتر)", "kind": "استغاثة منشورة" if sc >= 75 else "منشور/موضوع",
            "service": service_of(text), "score": sc,
            "tier": "ساخن" if sc >= 75 else "دافئ" if sc >= 55 else "مراقبة",
            "signals": sig, "query": pool[u]["query"],
            "age_hours": round(age, 1) if age is not None else None,
            "created_at": (det or {}).get("created_at", ""), "author": author,
            "action": "ردّ عام مهذّب + عرض مساعدة مجانية أولاً" if sc >= 75 else "راقب المنشور",
        })

    # 5) حسابات X (اسمها نفسه إشارة: «تم اختراق حسابي (@user)»)
    for u in x_profile:
        item = pool[u]
        sc, sig = score_text(f'{item["title"]} {item["snippet"]}', "X (تويتر)", None)
        if sc < 45: continue
        handle = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", u).group(1)
        leads.append({
            "id": "p_" + handle, "title": (item["title"] or f"@{handle}")[:180],
            "url": f"https://x.com/{handle}", "snippet": item["snippet"][:400],
            "platform": "X (تويتر)", "kind": "حساب متضرر", "service": service_of(item["title"] + item["snippet"]),
            "score": sc, "tier": "ساخن" if sc >= 75 else "دافئ" if sc >= 55 else "مراقبة",
            "signals": sig, "query": item["query"], "age_hours": None, "created_at": "",
            "author": handle, "action": "تابع الحساب وراقب تغريداته القادمة",
        })

    # 6) بقية المصادر (منتديات/دعم/مقالات) — مع احترام النافذة إن توفّر التاريخ
    for u, item in pool.items():
        if x_kind(u): continue
        hours = item.get("hours_old")
        text = f'{item["title"]} {item["snippet"]}'
        sc, sig = score_text(text, "ويب", hours)
        if sc < 50: continue
        leads.append({
            "id": hashlib.md5(u.encode()).hexdigest()[:10], "title": (item["title"] or u)[:180],
            "url": item["url"], "snippet": item["snippet"][:400],
            "platform": "منتدى/دعم" if re.search(r"reddit|answers|support|forum|thread", u) else "ويب",
            "kind": "استغاثة منشورة" if sc >= 75 else "منشور/موضوع",
            "service": service_of(text), "score": sc,
            "tier": "ساخن" if sc >= 75 else "دافئ" if sc >= 55 else "مراقبة",
            "signals": sig, "query": item["query"], "age_hours": round(hours, 1) if hours else None,
            "created_at": "", "action": "ردّ على الموضوع أو تواصل عبر القناة المذكورة",
        })

    # ── ترتيب وتنقية ──
    leads.sort(key=lambda x: (-x["score"], x.get("age_hours") if x.get("age_hours") is not None else 9999))
    seen_id, seen_txt, uniq = set(), set(), []
    for l in leads:
        tid = re.search(r"/status/(\d+)", l["url"])
        key = tid.group(1) if tid else None
        if key and key in seen_id:
            continue
        if key:
            seen_id.add(key)
        txt_key = re.sub(r"[^\u0600-\u06FFA-Za-z0-9]+", "", (l.get("snippet") or l["title"]))[:55]
        if txt_key and txt_key in seen_txt:
            continue
        if txt_key:
            seen_txt.add(txt_key)
        uniq.append(l)

    # ── تطبيق النافذة الزمنية + التوسيع التلقائي عند قلّة النتائج ──
    def in_window(l, w):
        a = l.get("age_hours")
        return a is not None and a <= w

    inside = [l for l in uniq if in_window(l, WINDOW)]
    outside = [l for l in uniq if not in_window(l, WINDOW)]
    expired = len(outside)
    window_used, widened = WINDOW, False
    final = list(inside)
    if AUTO_WIDEN and len(inside) < MIN_LEADS:
        for w in [72, 168, 336]:
            if w <= WINDOW: continue
            need = MIN_LEADS - len(final)
            if need <= 0: break
            add = [l for l in outside if (l.get("age_hours") or 1e9) <= w][:need]
            if add:
                final += add
                window_used = w
                widened = True
            if len(final) >= MIN_LEADS: break
    final.sort(key=lambda x: (-x["score"], x.get("age_hours") if x.get("age_hours") is not None else 9999))
    # تنقية نهائية مضمونة (نفس الرابط/المعرّف يُحذف)
    dedup, seen_urls, seen_ids = [], set(), set()
    for l in final:
        u = norm(l["url"])
        t = re.search(r"/status/(\d+)", u)
        tid = t.group(1) if t else None
        if u in seen_urls or (tid and tid in seen_ids):
            continue
        seen_urls.add(u)
        if tid: seen_ids.add(tid)
        a = l.get("age_hours")
        l["fresh"] = bool(a is not None and a <= WINDOW)
        dedup.append(l)
    final = dedup

    meta = {
        "generated_at": NOW.isoformat(timespec="seconds"),
        "window_hours": WINDOW, "window_used_hours": window_used, "widened": widened,
        "inside_window": len(inside), "focus": FOCUS,
        "queries": len(queries), "raw_results": len(pool),
        "x_status_found": len(x_status), "x_profiles_found": len(x_profile),
        "expired_outside_window": expired,
        "unique_leads": len(final), "hot": sum(1 for l in final if l["score"] >= 75),
        "x_leads": sum(1 for l in final if l["platform"] == "X (تويتر)"),
        "engine": "Yahoo + Bing(متصفح) + Google News RSS + X Syndication",
        "elapsed_s": round(time.time() - t0),
    }
    os.makedirs(DATA, exist_ok=True)
    json.dump({"meta": meta, "leads": final}, open(os.path.join(DATA, "leads_raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(build_x_links(), open(os.path.join(DATA, "x_queries.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("✔", json.dumps(meta, ensure_ascii=False))
    for l in final[:8]:
        print(f'   {l["score"]:3} · {l["platform"][:10]:10} · {(l.get("age_hours") or "-")}س · {l["title"][:60]}')


if __name__ == "__main__":
    asyncio.run(main())
