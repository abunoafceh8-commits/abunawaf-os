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
MAX_ENRICH = int(os.environ.get("MAX_ENRICH", "1100"))
TIME_BUDGET = int(os.environ.get("TIME_BUDGET", "900"))
MIN_LEADS = int(os.environ.get("MIN_LEADS", "18"))
SCORE_MIN = int(os.environ.get("SCORE_MIN", "42"))
SCORE_MIN_WEB = int(os.environ.get("SCORE_MIN_WEB", "42"))
KEEP_ARCHIVE = int(os.environ.get("KEEP_ARCHIVE", "300"))
AUTO_WIDEN = os.environ.get("AUTO_WIDEN", "1") == "1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
NOW = datetime.now(timezone.utc)
TW_EPOCH = 1288834974657          # بداية Snowflake في تويتر

_AR_DIAC = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي",
                         "ؤ": "و", "ة": "ه", "ﻻ": "لا", "٠": "0", "١": "1", "٢": "2"})


def ar_norm(t):
    """تطبيع عربي: يوحّد الهمزات والألف المقصورة والتاء المربوطة ويحذف التشكيل —
    يجعل «أخترق» = «اخترق» و«مسروقه» = «مسروقة» (يرفع الاستدعاء كثيراً)."""
    if not t:
        return ""
    t = _AR_DIAC.sub("", str(t)).translate(_AR_MAP)
    return re.sub(r"\s+", " ", t)


def _nlist(xs):
    return [ar_norm(x) for x in xs]



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
EXTRA = ["اخترقوا حسابي", "تهكر حسابي", "سرقوا حسابي", "مبتزني", "يهددني بصوري",
         "انتحل شخصيتي", "حسابي مسروق ساعدوني", "كيف ارجع حسابي", "وش الحل حسابي مقفل",
         "قفلوا حسابي", "علّقوا حسابي", "حسابي بالايقاف", "ابتزوني",
         "صورة خاصة تهديد", "حسابي في الانستقرام مسروق", "تم تهكير حسابي",
         "حسابي انسرق مني", "استرجاع حساب مسروق", "تم اختراق حسابي في",
         "سنابي انسرق", "انستقرامي انسرق", "تيك توكي انسرق", "واتسابي مخترق",
         "ابتزني شخص", "يهددني بنشر", "حسابي مقفل ولا اعرف السبب",
         "قفلوا حسابي بدون سبب", "ارسلوا لي رسالة تهديد", "انتحل شخصيتي وحساب مزيف",
         "شخص يهددني بنشر صوري", "حسابي في الانستقرام مقفل", "سنابي محظور",
         "حسابي بالتيك توك موقوف", "احد يعرف شخص يرجع حساب", "مين يرجع حساب",
         "ابي شخص يرجع حسابي", "في احد يسترجع حسابات", "احد يفك باند",
         "ابحث عن هاكر", "مطلوب هاكر", "من يقدر يرجع حسابي", "ابي احد يهكر حساب",
         "شخص يسترجع حساب سناب", "ابغى استرجع حسابي من الهكر", "احد يساعدني في اختراق حساب"]

HASHTAGS = [
    "#حسابي_مسروق", "#تم_اختراق_حسابي", "#اختراق_حسابي", "#حسابي_مخترق",
    "#ابتزاز_الكتروني", "#ابتزاز", "#فك_باند", "#سناب_مقفل", "#حسابي_موقوف",
    "#انستقرام_مقفل", "#تيك_توك_موقوف", "#تهكير",
]
QUESTION = ["كيف", "الحل", "مساعدة", "تكفون", "ضروري", "وش اسوي", "احد يفيدني", "استفسار"]


HIGH_YIELD = [
    "حساب مزيف باسمي", "حساب مزيف باسمي على تويتر", "تواصلوا معي من حساب مزيف",
    "شخص انتحل شخصيتي", "انتحل شخصيتي", "انتحل شخصيتي وسوى حساب", "حساب تقليد باسمي",
    "مبتز يطلب فلوس", "مبتز يهددني", "مبتزني على السناب", "مبتزني على الانستقرام",
    "يهددني ويرسل صوري", "يهددني بنشر صوري", "يهددني بنشر محادثاتي", "يهددني بفضحي",
    "يرسل لي تهديد", "وصلتني رسالة تهديد", "رسائل تهديد على الواتساب", "ابتزاز بالصور",
    "ابتزاز الكتروني", "تعرضت لابتزاز", "يطلب مني فلوس ويهددني", "يفضحني عند اهلي",
    "ينشر محادثاتي", "سرب صوري", "عنده صوري ويهددني", "اخترق جوالي", "اخترقوا جوالي",
    "هاك جوالي", "جوالي مخترق", "بياناتي مسربة", "ملفاتي مسروقة", "ايميلي مخترق",
    "جيميلي مخترق", "حسابي في ستيم مسروق", "حسابي في البلايستيشن تهكر",
    "حسابي في روبلوكس مسروق", "حسابي في ديسكورد مخترق", "حسابي في تلجرام مسروق",
    "اتسرق حسابي", "حسابي اتهكر", "اتقفل حسابي", "حسابي اتبند", "حسابي اتحظر",
    "سنابي اتقفل", "انستقرامي اتقفل", "تيك توكي اتبند", "حسابي في الانستا مسروق",
    "سرقوا حسابي في السناب", "هكروا سنابي", "سرقوا حسابي من الجوال",
    "حسابي مسروق ولا احد يساعدني", "حسابي مسروق وش اسوي تكفون", "حسابي مسروق اليوم",
    "حسابي مسروق من يومين", "حسابي مسروق قبل اسبوع", "حسابي مخترق اليوم",
    "حسابي مقفل بدون سبب", "قفلوا حسابي ظلم", "وقفوا حسابي ظلم", "حظروا حسابي",
    "حسابي موقوف وابغى ارجعه", "ابغى ارجع حسابي", "ابغى استعيد حسابي", "كيف ارجع سنابي",
    "كيف ارجع انستقرامي", "كيف ارجع تيك توكي", "كيف افك الحظر عن حسابي",
    "احد يقدر يفك الباند", "مين يفك الباند", "احد يرجع الحسابات", "شخص يرجع الحسابات",
    "ابحث عن شخص يهكر حساب", "ابي احد يهكر حساب سناب", "احتاج هاكر",
    "من يعرف شخص يسترجع حساب", "تعرفون احد يرجع الحسابات", "احد يساعدني ارجع حسابي",
]

SERVICES = ["حسابي", "سنابي", "انستقرامي", "انستا", "تيك توكي", "تلجرامي", "واتسابي",
            "ايميلي", "جيميلي", "حسابي في تويتر", "حسابي في انستقرام", "حسابي في سناب",
            "حسابي في التيك توك", "حسابي في تلجرام", "حساب البلايستيشن", "حسابي في ستيم",
            "حسابي في روبلوكس", "حسابي في فيسبوك", "حسابي في الفيس", "حسابي في كاشير",
            "حسابي في ديسكورد", "حسابي في لينكد ان", "حسابي في الاب ستو", "حسابي في قوقل بلاي"]
STATES = ["مسروق", "مخترق", "مقفل", "موقوف", "محظور", "مبند", "معلّق", "مهكر",
          "مسروق ومقفل", "تهكر", "انسرق", "اخترقوه", "قفلوه", "وقفلوه ظلم", "ما اقدر ادخل"]
ASKS = ["كيف ارجع حسابي المسروق", "كيف استرجع حسابي المخترق", "كيف افك الباند عن حسابي",
        "كيف ارجع سنابي المقفل", "كيف ارجع انستقرامي الموقوف", "كيف استعيد حسابي",
        "احد يقدر يرجع حسابي", "احد يفك لي باند", "ابحث عن شخص يسترجع الحسابات",
        "مين يساعدني في استرجاع حسابي", "وش حل الحساب المقفل", "حسابي موقوف ظلم كيف ارجعه",
        "سرقوا حسابي وش اسوي", "هكروا حسابي وش الحل", "مبتزني شخص وش اسوي",
        "يهددني بنشر صوري وش اسوي", "انتحل شخصيتي وسوى حساب مزيف",
        "حسابي مسروق من فترة ولا احد يساعدني", "الحقوني حسابي انسرق اليوم",
        "تكفون احد يساعدني حسابي مقفل", "حسابي انسرق قبل كم يوم",
        "حسابي تهكر وطلعت منه", "حسابي في الانستقرام انسرق", "سنابي تهكر اليوم"]


def build_queries_rss():
    """استعلامات مقتبسة دقيقة — الأنسب لمحرك Bing RSS (أعلى إنتاجية وجودة)."""
    qs = []

    def add(q):
        q = (q or "").strip()
        if q and q not in qs:
            qs.append(q)

    # 1) عبارات أساسية + لهجية (أعلى أولوية)
    for t in CORE: add(f'"{t}"')
    for t in DIALECT: add(f'"{t}"')
    # 2) خدمات × حالات — 24 × 15 = 360 توليفة (بعد التنقية)
    for s in SERVICES:
        for st in STATES:
            add(f'"{s} {st}"')
    # 3) العائلات عالية الإنتاجية
    for t in HIGH_YIELD: add(f'"{t}"')
    # 4) صيغ سؤال حقيقية
    for t in ASKS: add(f'"{t}"')
    # 4) هاشتاقات ومنشورات بلا تنصيص
    for h in HASHTAGS: add(h)
    for t in EXTRA: add(f'"{t}"')
    return qs


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
    "اتسرق": 18, "اتهكر": 18, "اتقفل": 16, "اتخترق": 18, "هكروه": 16, "سرقوه": 16,
    "قفلوه": 15, "وقفوه": 15, "بلوك": 13, "تهام": 10, "تشهير": 16, "يفضحني": 18,
    "فضحني": 16, "تسريب": 15, "يسرب": 15, "يبتزني": 22, "فديه": 18, "تلجرام": 8,
    "جيميل": 8, "ديسكورد": 8, "ستيم": 8, "بلايستيشن": 9, "روبلوكس": 8, "الاكونت": 10,
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
       "نخدمك", "أسعارنا", "الدفع بعد", "شغل مضمون", "ابعت رسالة", "كلمني خاص",
    # سبّ/شتائم وصراعات (ليست حالات عملاء)
    "امك", "ابوك", "قواد", "شرموط", "طيز", "زبي", "منيوك", "عرص", "خول", "نيك",
    # مقالات شرح ودلائل (ليست استغاثات)
    "كيف يمكنك", "خطوات استرجاع", "خطوات استعادة", "دليل", "شرح", "مقال", "تعلم",
    "افضل الطرق", "نصائح", "طريقه استرجاع", "طريقة استرجاع", "لماذا", "تعريف",
]
# مؤشرات أن الكاتب يتكلم عن مشكلته الشخصية (لا خبر ولا إعلان)
PERSONAL = ["حسابي", "اخترقوا", "سرقوا", "هكروا", "انسرق", "محتاج", "ابغى", "أبغى",
            "ابي ", "أبي ", "تكفون", "ساعدوني", "الحقوني", "ضايع", "ماراح اقدر",
            "ما اقدر ادخل", "يهددني", "مبتزني", "ينشر", "عندي مشكلة", "وش الحل",
            "احد يفيدني", "محتارة", "محبط", "مدري وش اسوي", "خصوصيتي",
            "اتسرق", "اتهكر", "اتقفل", "سرقوه", "هكروه", "قفلوه", "وقفوه", "بلوك",
            "افتح حسابي", "رجعوا", "ما اقدر افتح", "تعرفون احد", "احد يعرف", "من يعرف",
            "وش السوات", "لا حول", "حرام عليكم", "ساعدوني تكفون", "والله تعبت"]
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


ACCOUNT_WORDS = ["حسابي", "حسابه", "حسابها", "حساب ", "حساباتي", "الاكونت", "سنابي", "سناب",
                 "انستقرام", "انستغرام", "انستا", "تيك توك", "تيكتوك", "واتساب", "تويتر", "فيسبوك",
                 "الفيس", "تلجرام", "تليجرام", "ايميل", "بريدي", "الإيميل", "الايميل", "جيميل",
                 "رقمي", "جوالي", "صوري", "فيديوهاتي", "خصوصيتي", "بياناتي", "ملفاتي",
                 "بلايستيشن", "ستيم", "روبلوكس", "ديسكورد", "لينكد ان", "المهنه", "قناتي"]
DISTRESS = ["مسروق", "مخترق", "اختراق", "هكر", "تهكر", "انسرق", "سرقوا", "مبتز", "ابتزاز",
            "يهددني", "مقفل", "موقوف", "محظور", "باند", "حظر", "انتحال", "مزيف", "مجهول", "وهمي",
            # مرادفات دارجة/إملاءات مختلفة (تُطبَّع تلقائياً)
            "اتسرق", "اتهكر", "اتقفل", "اتخترق", "هاك", "هاكر", "هكره", "نهبوا", "سحبوا حسابي",
            "قفلوا", "وقفوا", "حظروا", "علقوا", "بلوك", "بان ", "مسروقه", "مخترقه", "موقفه",
            "استولى", "سيطروا", "تلاعب", "سرقه", "سرقت", "اخترقه", "اخترقوا",
            # ابتزاز وتشهير
            "يهدد", "تهديد", "تشهير", "يفضحني", "فضحني", "ينشر", "نشر صور", "يسرب", "تسريب",
            "يطلب فلوس", "فديه", "يبتزني", "مبتزني", "يرسل صوري", "يلعب بي", "على حسابي"]
# نسخ مطبّعة للقوائم (تُستخدم في المطابقة كلها)
NEG_N = _nlist(NEG)
STRONG_N = {ar_norm(k): v for k, v in STRONG.items()}
PERSONAL_N = _nlist(PERSONAL)
ACCOUNT_N = _nlist(ACCOUNT_WORDS)
DISTRESS_N = _nlist(DISTRESS)


def proximity_ok(text):
    """كلمة خطر + كلمة حساب ضمن ±70 حرفاً (على النص المطبَّع) — يمنع الأخبار والنكات."""
    t = ar_norm(text)
    for w in DISTRESS_N:
        if not w.strip():
            continue
        start = 0
        while True:
            i = t.find(w, start)
            if i < 0:
                break
            seg = t[max(0, i - 70): i + len(w) + 70]
            if any(a.strip() and a in seg for a in ACCOUNT_N):
                return True
            start = i + 1
    return False


def score_text(text, platform, hours_old=None):
    if not text or not is_arabic(text):
        return 0, []
    t = ar_norm(text)
    if any(n.strip() and n in t for n in NEG_N):
        return 0, []
    if not proximity_ok(text):
        return 0, []
    signals, score = [], 0
    for k, w in STRONG_N.items():
        if k and k in t:
            signals.append(k)
            score += w
    personal_hits = sum(1 for p in PERSONAL_N if p.strip() and p in t)
    strong_hits = len(signals)
    if personal_hits:
        score += min(18, personal_hits * 7)
        signals.append("ضمير شخصي")
    if strong_hits >= 2:
        score += 10
    if strong_hits >= 3:
        score += 8
    if platform and "X" in platform:
        score += 4
    if hours_old is not None and hours_old <= 72:
        score += 6
    elif hours_old is not None and hours_old <= 336:
        score += 3
    if "؟" in text or "?" in text:
        score += 4
    return min(100, score), signals[:8]


def service_of(text):
    t = ar_norm(text)
    if any(k in t for k in ["ابتزاز", "مبتز", "يهددني", "يهدد", "صوري", "تشهير", "يفضحني", "فديه", "ينشر"]):
        return "مكافحة ابتزاز"
    if any(k in t for k in ["موقوف", "مقفل", "باند", "حظر", "ايقاف", "اتقفل", "قفلوا", "وقفوا", "بلوك"]):
        return "استعادة حساب موقوف"
    if any(k in t for k in ["مجهول", "انتحال", "مزيف", "هويه", "وهمي", "انتحل"]):
        return "كشف هوية OSINT"
    if any(k in t for k in ["اختراق", "مخترق", "هكر", "تهكر", "اتهكر", "موقع", "متجر", "بياناتي", "جوالي"]):
        return "اختراق/تحصين"
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

    leads, expired, cands = [], 0, []

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
        cands.append({"id": tid, "author": author, "score": sc, "age": age, "signals": sig,
                      "text": (text or "")[:220], "title": (title or "")[:120]})
        if sc < SCORE_MIN:
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
        cands.append({"id": hashlib.md5(u.encode()).hexdigest()[:10], "author": "", "score": sc,
                      "age": hours, "signals": sig, "text": text[:220], "title": item["title"][:120], "web": True})
        if sc < SCORE_MIN_WEB: continue
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

    # ── النافذة الزمنية: تُحترم حرفياً ولا يُخلط شيء خارجها ──
    def in_window(l, w):
        a = l.get("age_hours")
        return a is not None and a <= w

    fresh = [l for l in uniq if in_window(l, WINDOW)]
    older = [l for l in uniq if l.get("age_hours") is not None and l["age_hours"] > WINDOW]
    undated = [l for l in uniq if l.get("age_hours") is None]

    def sk(x):
        return (x.get("age_hours") if x.get("age_hours") is not None else 10**6, -x["score"])

    fresh.sort(key=sk)
    older.sort(key=sk)
    for l in fresh:
        l["fresh"] = True
    for l in older + undated:
        l["fresh"] = False

    # الملف يحتفظ بالجميع بأعمار حقيقية؛ التصفية تحصل في الخادم/الواجهة بدقة
    final = fresh + older + undated
    dedup, seen_urls, seen_ids = [], set(), set()
    for l in final:
        u = norm(l["url"])
        t = re.search(r"/status/(\d+)", u)
        tid = t.group(1) if t else None
        if u in seen_urls or (tid and tid in seen_ids):
            continue
        seen_urls.add(u)
        if tid:
            seen_ids.add(tid)
        dedup.append(l)
    final = dedup

    # ── أرشيف تراكمي: لا نفقد نتائج الجولات السابقة (تُعاد أعمارها للآن) ──
    prev_path = os.path.join(DATA, "leads_raw.json")
    added_prev = 0
    if KEEP_ARCHIVE and os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path, encoding="utf-8"))
            pmeta = prev.get("meta", {})
            pgen = pmeta.get("generated_at")
            delta_h = 0.0
            if pgen:
                try:
                    delta_h = (NOW - datetime.fromisoformat(pgen)).total_seconds() / 3600
                except Exception:
                    delta_h = 0.0
            have = {norm(l["url"]) for l in final}
            have_ids = {re.search(r"/status/(\d+)", l["url"]).group(1)
                        for l in final if re.search(r"/status/(\d+)", l["url"])}
            pool_prev = []
            for l in prev.get("leads", []):
                u = norm(l.get("url", ""))
                if not u or u in have:
                    continue
                m2 = re.search(r"/status/(\d+)", u)
                if m2 and m2.group(1) in have_ids:
                    continue
                ca = l.get("created_at") or ""
                age = l.get("age_hours")
                if ca:
                    try:
                        age = (NOW - datetime.fromisoformat(ca.replace("Z", "+00:00"))).total_seconds() / 3600
                    except Exception:
                        pass
                elif age is not None:
                    age = age + delta_h
                if age is not None and age > 720:
                    continue
                l = dict(l)
                l["age_hours"] = round(age, 1) if age is not None else None
                l["fresh"] = bool(age is not None and age <= WINDOW)
                pool_prev.append(l)
            pool_prev.sort(key=lambda x: (x.get("age_hours") if x.get("age_hours") is not None else 10**6, -x.get("score", 0)))
            final = final + pool_prev[:KEEP_ARCHIVE]
            added_prev = len(pool_prev[:KEEP_ARCHIVE])
        except Exception as e:
            print("archive skip:", e, flush=True)

    meta = {
        "generated_at": NOW.isoformat(timespec="seconds"),
        "window_hours": WINDOW, "window_used_hours": WINDOW, "widened": False,
        "inside_window": sum(1 for l in final if l.get("fresh")),
        "older_count": sum(1 for l in final if l.get("age_hours") is not None and not l.get("fresh")),
        "undated_count": sum(1 for l in final if l.get("age_hours") is None),
        "focus": FOCUS,
        "queries": len(rss_queries) + len(queries),
        "raw_results": len(pool),
        "x_status_found": len(x_status), "x_profiles_found": len(x_profile),
        "unique_leads": len(final), "from_archive": added_prev, "hot": sum(1 for l in final if l["score"] >= 75),
        "x_leads": sum(1 for l in final if l["platform"] == "X (تويتر)"),
        "engine": "Bing RSS + Yahoo + Google News + X Syndication",
        "elapsed_s": round(time.time() - t0),
    }
    os.makedirs(DATA, exist_ok=True)
    json.dump({"meta": meta, "leads": final}, open(os.path.join(DATA, "leads_raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    cands.sort(key=lambda c: -c["score"])
    json.dump({"generated_at": NOW.isoformat(timespec="seconds"), "total": len(cands),
               "cands": cands[:600]}, open(os.path.join(DATA, "x_candidates.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(build_x_links(), open(os.path.join(DATA, "x_queries.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("✔", json.dumps(meta, ensure_ascii=False))
    for l in final[:8]:
        print(f'   {l["score"]:3} · {l["platform"][:10]:10} · {(l.get("age_hours") or "-")}س · {l["title"][:60]}')


if __name__ == "__main__":
    asyncio.run(main())
