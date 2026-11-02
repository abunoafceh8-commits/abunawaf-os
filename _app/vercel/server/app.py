# -*- coding: utf-8 -*-
"""
منصة فريق أبو نواف — خادم الأدوات (FastAPI)
يشغّل: محرك العملاء المحتملين، محرك الكلمات المفتاحية، مدقق SEO الحي، سجل الأدوات.
"""
import json, os, re, time, threading, csv, io, hashlib
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE_DIR, "data")
STATIC = os.path.join(BASE_DIR, "static")
SITE = "https://ant.xo.je"

app = FastAPI(title="AbuNawaf OS", docs_url="/api/docs", redoc_url=None)


def load(name, default=None):
    if name in MEM_OVERLAY:
        return MEM_OVERLAY[name]
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


MEM_OVERLAY = {}


def save(name, obj):
    """يحفظ في الملف إن كان القرص قابلاً للكتابة، وإلا في الذاكرة (بيئات serverless)."""
    MEM_OVERLAY[name] = obj
    try:
        p = os.path.join(DATA, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ─────────────────────────── محرك زحف ant.xo.je (يحل تحدي __test) ───────────────────────────
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"


def site_client():
    return httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ar-SA,ar;q=0.9"},
                        timeout=45, follow_redirects=True)


def solve_challenge(client, html):
    """يفك تشفير الكوكي __test (slowAES) الذي يفرضه استضافة InfinityFree"""
    try:
        from Crypto.Cipher import AES
        m = re.search(r'a=toNumbers\("(\w+)"\),b=toNumbers\("(\w+)"\),c=toNumbers\("(\w+)"\)', html)
        if not m:
            return False
        a, b, c = m.groups()
        pt = AES.new(bytes.fromhex(a), AES.MODE_CBC, bytes.fromhex(b)).decrypt(bytes.fromhex(c))
        client.cookies.set("__test", pt.hex(), domain="ant.xo.je")
        return True
    except Exception:
        return False


AUDIT_CACHE = {"at": 0, "data": None}
AUDIT_TTL = 600


def crawl_site():
    from bs4 import BeautifulSoup
    cl = site_client()
    r = cl.get(SITE + "/")
    challenge_seen = "slowAES" in r.text
    if challenge_seen:
        solve_challenge(cl, r.text)
        r = cl.get(SITE + "/?i=1")

    pages = {}
    queue = ["/", "/pages/services.html", "/pages/tools.html", "/pages/problems.html",
             "/pages/terms.html", "/pages/contact.html"]
    for path in queue:
        url = SITE + path
        try:
            resp = cl.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            for t in soup(["script", "style"]):
                t.decompose()
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            desc_tag = soup.find("meta", attrs={"name": "description"})
            desc = desc_tag.get("content", "") if desc_tag else ""
            h1 = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
            h2 = [h.get_text(" ", strip=True) for h in soup.find_all("h2")]
            imgs = soup.find_all("img")
            text = soup.get_text(" ", strip=True)
            ld = resp.text.count('application/ld+json')
            pages[path] = {
                "url": url, "status": resp.status_code, "bytes": len(resp.content),
                "latency_ms": round(resp.elapsed.total_seconds() * 1000),
                "title": title, "title_len": len(title),
                "desc": desc, "desc_len": len(desc),
                "h1": h1, "h2_count": len(h2), "h2": h2[:8],
                "imgs": len(imgs), "img_no_alt": len([i for i in imgs if not i.get("alt")]),
                "words": len(text.split()), "ldjson": ld,
                "canonical": (soup.find("link", rel="canonical") or {}).get("href"),
                "noindex": "noindex" in resp.text.lower()[:4000],
            }
        except Exception as e:
            pages[path] = {"url": url, "error": str(e)[:200]}

    # فحوص البنية والأمان
    checks = {}
    try:
        root = cl.get(SITE + "/")
        h = {k.lower(): v for k, v in root.headers.items()}
        checks["server"] = h.get("server", "?")
        checks["hsts"] = "strict-transport-security" in h
        checks["csp"] = "content-security-policy" in h
        checks["x_frame"] = "x-frame-options" in h
        checks["referrer_policy"] = h.get("referrer-policy", "—")
        checks["gzip"] = h.get("content-encoding") == "gzip"
        checks["cache"] = h.get("cache-control", "—")
        checks["js_challenge"] = challenge_seen
        checks["html_bytes"] = len(root.content)
        checks["ttfb_ms"] = round(root.elapsed.total_seconds() * 1000)
        checks["last_modified"] = h.get("last-modified", "—")
        nf = cl.get(SITE + "/pages/__nope__" + str(int(time.time())) + ".html")
        checks["soft404"] = (nf.status_code == 200)
        checks["notfound_status"] = nf.status_code
        rob = cl.get(SITE + "/robots.txt")
        sm = cl.get(SITE + "/sitemap.xml")
        checks["robots_ok"] = rob.status_code == 200
        checks["sitemap_ok"] = sm.status_code == 200
        checks["sitemap_urls"] = sm.text.count("<loc>")
        checks["sitemap_has_tools"] = "/pages/tools.html" in sm.text
        pr = cl.get(SITE + "/pages/tools.html")
        checks["tools_page_indexable"] = "noindex" not in pr.text.lower()[:5000]
        checks["tools_password_in_html"] = "correctPassword" in pr.text
        checks["tools_pw_pattern"] = "YYYYMMDD+0878" if "correctPassword" in pr.text else None
        # حجم الأصول
        total_assets = 0
        for path in ["/css/main.css", "/js/main.js", "/assets/images/logo.jpg"]:
            try:
                ar = cl.get(SITE + path)
                total_assets += len(ar.content)
            except Exception:
                pass
        checks["assets_bytes"] = total_assets
    except Exception as e:
        checks["error"] = str(e)[:200]

    # الدرجات
    seo, perf, sec, content = 100, 100, 100, 100
    issues = []

    def issue(sev, area, title, detail, fix):
        issues.append({"severity": sev, "area": area, "title": title, "detail": detail, "fix": fix})

    # SEO
    for path, p in pages.items():
        if p.get("error"):
            issue("high", "SEO", f"تعذّر الوصول للصفحة {path}", p["error"], "تحقق من الصفحة")
            seo -= 8
            continue
        if p["title_len"] > 60:
            issue("medium", "SEO", f"عنوان أطول من 60 حرفاً — {path}",
                  f"الطول {p['title_len']} حرفاً؛ جوجل يعرض ~580 بكسل فقط.",
                  "قصّر العنوان إلى 50-58 حرفاً مع الكلمة المفتاحية في البداية.")
            seo -= 4
        if p["desc_len"] > 160:
            issue("medium", "SEO", f"وصف ميتا أطول من 160 حرفاً — {path}",
                  f"الطول {p['desc_len']} حرفاً.",
                  "اضبط الوصف بين 140-158 حرفاً مع دعوة لاتخاذ إجراء.")
            seo -= 3
        if p["desc_len"] < 70:
            issue("low", "SEO", f"وصف ميتا قصير — {path}", f"{p['desc_len']} حرفاً.", "أضف وصفاً 140+ حرفاً.")
            seo -= 2
        if p["h2_count"] == 0:
            issue("medium", "SEO", f"لا توجد عناوين H2 — {path}", "بنية محتوى مسطّحة.", "قسّم المحتوى بعناوين H2/H3 دلالية.")
            seo -= 4
        if p["words"] < 300:
            issue("medium", "محتوى", f"محتوى رقيق ({p['words']} كلمة) — {path}", "أقل من الحد المفيد للتصدر.",
                  "وسّع الصفحة إلى 600+ كلمة أو ادمجها.")
            content -= 5
        if not p["canonical"]:
            issue("high", "SEO", f"لا يوجد canonical — {path}", "خطر تكرار المحتوى.", "أضف <link rel=canonical>.")
            seo -= 5
    if not checks.get("sitemap_ok"):
        issue("high", "SEO", "sitemap.xml غير متاح", "الزواحف تفقد خريطة الموقع.", "أصلح الملف وأعد إرساله في Search Console.")
        seo -= 6
    if checks.get("tools_page_indexable") and checks.get("tools_password_in_html"):
        issue("high", "SEO/أمان", "صفحة محمية بكلمة سر لكنها index,follow",
              "جوجل يفهرس محتوى محمياً، وكلمة السر ظاهرة داخل HTML.",
              "أضف noindex أو انقل الحماية إلى الخادم (HTTP auth).")
        seo -= 5
        sec -= 15
    if checks.get("js_challenge"):
        issue("high", "SEO/أداء", "تحدٍّ JavaScript (كوكي __test) قبل تحميل الصفحة",
              "أي زاحف لا ينفّذ JS يحصل على 836 بايت فقط بدل 66KB من المحتوى، ويضيف طلباً كاملاً قبل أول بايت محتوى.",
              "ارفع الموقع على استضافة بلا تحديات (Cloudflare Pages/Vercel) أو استخدم Cache Everything.")
        seo -= 10
        perf -= 10
    if checks.get("soft404"):
        issue("medium", "SEO", "صفحة 404 ترجع 200", "Soft 404 يستهلك ميزانية الزحف.", "اجعل الاستجابة 404 فعلياً.")
        seo -= 3
    else:
        issue("info", "SEO", "صفحة 404 ترجع كود 404 صحيحاً ✔", "سلوك سليم.", "—")

    # أمان
    if not checks.get("hsts"):
        issue("high", "أمان", "لا يوجد HSTS", "لا إجبار على HTTPS، وعرضة لهجمات SSL-strip.",
              "أضف Strict-Transport-Security: max-age=31536000; includeSubDomains.")
        sec -= 12
    if not checks.get("csp"):
        issue("medium", "أمان", "لا يوجد Content-Security-Policy", "لا حماية من XSS وحقن السكربتات.",
              "ابدأ بـ CSP report-only ثم شدّدها.")
        sec -= 8
    if not checks.get("x_frame"):
        issue("low", "أمان", "لا يوجد X-Frame-Options", "احتمال Clickjacking.", "أضف SAMEORIGIN.")
        sec -= 4
    if checks.get("tools_password_in_html"):
        issue("critical", "أمان", "كلمة مرور صفحة الأدوات مكشوفة في HTML",
              "النمط: تاريخ اليوم + 0878، وقيمة sessionStorage يمكن تعيينها يدوياً.",
              "احذف الحماية من العميل واستخدم خادماً وسيطاً + جلسات موقّعة.")
        sec -= 20

    # أداء
    if checks.get("assets_bytes", 0) > 90_000:
        issue("medium", "أداء", "أصول ثقيلة (CSS+JS+شعار)",
              f"{round(checks.get('assets_bytes',0)/1024)}KB قبل الصور.",
              "صغّر CSS/JS (minify) وحوّل الشعار إلى WebP بأبعاد مضبوطة.")
        perf -= 6
    if checks.get("ttfb_ms", 0) > 500:
        issue("low", "أداء", "TTFB مرتفع", f"{checks.get('ttfb_ms')}ms.", "استخدم CDN.")
    else:
        issue("info", "أداء", f"TTFB ممتاز ({checks.get('ttfb_ms')}ms) ✔", "استجابة الخادم سريعة.", "—")
    issue("info", "SEO", f"Schema متقدم موجود ({sum(p.get('ldjson',0) for p in pages.values() if isinstance(p,dict))} كتل JSON-LD) ✔",
          "Organization/Person/Service/FAQ/Breadcrumb — أفضل من معظم المنافسين.", "أضف Review/AggregateRating.")

    # دمج المشكلات المتكررة (نفس النوع لعدة صفحات) في بند واحد
    grouped, order = {}, []
    for it in issues:
        key = (it["severity"], it["area"], it["title"].split("—")[0].strip())
        if key in grouped:
            grouped[key]["paths"].append(it["title"].split("—")[-1].strip())
            grouped[key]["detail"] = f"الطول: {it['detail']}"
        else:
            it["paths"] = [it["title"].split("—")[-1].strip()]
            grouped[key] = it
            order.append(key)
    merged = []
    for k in order:
        it = grouped[k]
        if len(it["paths"]) > 1:
            it["title"] = f"{k[2]} ({len(it['paths'])} صفحات)"
            it["paths"] = sorted(set(it["paths"]))
        merged.append(it)
    issues = merged

    scores = {"seo": max(0, min(100, seo)), "performance": max(0, min(100, perf)),
              "security": max(0, min(100, sec)), "content": max(0, min(100, content))}
    scores["overall"] = round(sum(scores.values()) / 4)

    return {"crawled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checks": checks, "pages": pages, "issues": issues, "scores": scores}


@app.get("/api/seo/audit")
def api_audit(refresh: bool = False):
    now = time.time()
    if refresh or not AUDIT_CACHE["data"] or now - AUDIT_CACHE["at"] > AUDIT_TTL:
        try:
            AUDIT_CACHE["data"] = crawl_site()
            AUDIT_CACHE["at"] = now
            save("audit_last.json", AUDIT_CACHE["data"])
        except Exception as e:
            cached = load("audit_last.json")
            if cached:
                cached["stale"] = True
                cached["error"] = str(e)[:200]
                return cached
            raise HTTPException(503, f"فشل الزحف: {e}")
    return AUDIT_CACHE["data"]


# ─────────────────────────── SEO: مقترحات الإصلاح الجاهزة ───────────────────────────
SEED_KEYWORDS = ["استرجاع حساب مخترق", "استعادة حساب موقوف", "هكر أخلاقي سعودي",
                 "فك باند سناب شات", "مكافحة الابتزاز الإلكتروني", "كشف هوية حساب مجهول"]


@app.get("/api/seo/fixes")
def api_seo_fixes():
    kw = load("keywords.json", {"keywords": []})["keywords"]
    top = [k["keyword"] for k in kw[:8]] if kw else SEED_KEYWORDS
    titles = {
        "/": ("استرجاع حساب مخترق وموقوف خلال ساعات | فريق أبو نواف", "استعادة حسابك المخترق أو الموقوف في سناب وإنستقرام وX وتيك توك خلال 2-6 ساعات، ومكافحة الابتزاز وكشف الهوية — دفع بعد الإنجاز وسرية تامة."),
        "/pages/services.html": ("خدمات استعادة الحسابات ومكافحة الابتزاز | أبو نواف", "8 خدمات متخصصة: استرجاع حساب مسروق، فك إيقاف، مكافحة ابتزاز، OSINT، حذف حسابات المتوفين. تقرير قبل البدء ودفع بعد الإنجاز."),
        "/pages/problems.html": ("حلول فورية: تم اختراق حسابي — ماذا أفعل؟ | أبو نواف", "10 أدلة عملية خطوة بخطوة لاستعادة الحساب المخترق والموقوف، وإيقاف الابتزاز، وتأمين حساباتك — من فريق أمن سيبراني سعودي."),
        "/pages/tools.html": ("أدوات OSINT وأدوات X المتقدمة | فريق أبو نواف", "17 أداة استخبارات رقمية وتحليل حسابات X وسناب وتيك توك — للاستخدام التعليمي والأمني المصرّح به."),
        "/pages/contact.html": ("تواصل مع فريق أبو نواف — تيليجرام وسناب مباشرة", "قنوات التواصل الرسمية والموثقة لفريق أبو نواف: تيليجرام @KSA_hack01 وسناب ant_ceh، وأوقات العمل 2:30م–12ص."),
        "/pages/terms.html": ("الشروط والأحكام وطريقة العمل والدفع | أبو نواف", "بنود واضحة: تقرير قبل التنفيذ، دفع بعد الإنجاز أو 50% في منتصف العمل، سرية تامة، وسياسة إلغاء عادلة."),
    }
    new_pages = [
        {"slug": "/pages/recover-snapchat.html", "title": "استرجاع حساب سناب شات مقفل أو مسروق (دليل 2026)",
         "kw": "استرجاع حساب سناب شات", "why": "أعلى نية شرائية وأعلى حجم — المنافس yahyaplus يتصدرها بمقال واحد فقط"},
        {"slug": "/pages/recover-instagram.html", "title": "استرجاع حساب إنستقرام مخترق أو معطل نهائياً",
         "kw": "استرجاع حساب انستقرام", "why": "نية شرائية عالية + لا يوجد منافس سعودي بصفحة مخصصة"},
        {"slug": "/pages/recover-tiktok.html", "title": "حسابي في تيك توك موقوف — خطوات الاستعادة",
         "kw": "استرجاع حساب تيك توك", "why": "ظهور قوي في اقتراحات جوجل العربية"},
        {"slug": "/pages/recover-x.html", "title": "استعادة حساب X (تويتر) المخترق والموقوف",
         "kw": "حسابي موقوف في اكس", "why": "عبارة طلب خدمة حقيقية رصدناها في بحث مباشر"},
        {"slug": "/pages/blackmail-help.html", "title": "أتعرض للابتزاز الإلكتروني — دليل التدخل السريع",
         "kw": "ابتزاز الكتروني", "why": "منافس altahonos يجمع آلاف الزيارات من صفحة واحدة"},
        {"slug": "/pages/osint-hub.html", "title": "كشف هوية حساب مجهول — ما المسموح قانوناً؟",
         "kw": "كشف هوية حساب", "why": "يبني الثقة ويقلل المخاطر القانونية في نفس الوقت"},
    ]
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "كم تستغرق استعادة الحساب؟",
             "acceptedAnswer": {"@type": "Answer", "text": "من 2 إلى 6 ساعات للحساب المسروق، ومن 6 إلى 24 ساعة للموقوف."}},
            {"@type": "Question", "name": "هل الدفع بعد الإنجاز؟",
             "acceptedAnswer": {"@type": "Answer", "text": "نعم، بعد التأكد من النتائج. العملاء الجدد يدفعون 50% عند منتصف العمل مع توثيقه."}},
        ],
    }
    return {"current_vs_suggested": [{"path": p, "suggested_title": t[0],
                                      "title_len": len(t[0]), "suggested_desc": t[1],
                                      "desc_len": len(t[1])} for p, t in titles.items()],
            "top_keywords": top,
            "new_pages": new_pages,
            "schema_example": schema,
            "quick_wins": [
                "أضف AggregateRating + Review إلى صفحة الخدمات (يظهر نجوم في نتائج البحث).",
                "أضف hreflang للنسخة الإنجليزية إن أُنشئت، وأبقِ ar-SA كأساس.",
                "اربط كل خدمة برابط داخلي من الصفحة الرئيسية + من قسم الأسئلة الشائعة.",
                "أنشئ ملف Google Business Profile باسم «فريق أبو نواف» في الرياض (ظهور في الخرائط).",
                "أرسل sitemap.xml في Search Console و Bing Webmaster بعد رفع الاستضافة.",
                "أضف صوراً حقيقية بامتداد WebP مع alt وصفي لكل صورة خدمة.",
            ]}


# ─────────────────────────── العملاء المحتملون ───────────────────────────
LEADS_LOCK = threading.Lock()
LEAD_JOB = {"running": False, "started": None, "log": [], "error": None}


def merge_manual(leads):
    manual = load("leads_manual.json", [])
    ids = {l["id"] for l in leads}
    urls = {(l.get("url") or "").split("?")[0].rstrip("/") for l in leads}
    for m in manual:
        mu = (m.get("url") or "").split("?")[0].rstrip("/")
        if mu and mu in urls:
            continue
        if m.get("id") not in ids:
            m.setdefault("kind", "مُضاف يدوياً")
            m.setdefault("signals", [])
            m.setdefault("snippet", m.get("note", ""))
            m.setdefault("title", m.get("name", "عميل محتمل"))
            m.setdefault("tier", "ساخن" if m.get("score", 0) >= 75 else "دافئ")
            m.setdefault("action", "تواصل مباشرة عبر القناة المذكورة")
            m.setdefault("platform", m.get("platform", "مباشر"))
            m.setdefault("service", m.get("service", "—"))
            m.setdefault("query", "إدخال يدوي")
            m["manual"] = True
            leads.append(m)
    return leads


@app.get("/api/leads")
def api_leads(tier: Optional[str] = None, platform: Optional[str] = None,
              service: Optional[str] = None, q: Optional[str] = None,
              min_score: int = 0, limit: int = 500, include_raw: bool = False):
    d = load("leads_raw.json", {"meta": {}, "leads": [], "all": [], "sources": []})
    base = d.get("leads", [])
    if include_raw:
        base = d.get("all", base)
    base = merge_manual(list(base))
    for l in base:
        if "tier" not in l:
            l["tier"] = "ساخن" if l["score"] >= 75 else ("دافئ" if l["score"] >= 55 else "مراقبة")
    res = base
    if tier:
        res = [l for l in res if l["tier"] == tier]
    if platform:
        res = [l for l in res if l["platform"] == platform]
    if service:
        res = [l for l in res if l["service"] == service]
    if q:
        qq = q.lower()
        res = [l for l in res if qq in (l.get("title", "") + l.get("snippet", "") + l.get("url", "")).lower()]
    res = [l for l in res if l.get("score", 0) >= min_score]
    res.sort(key=lambda x: -x.get("score", 0))
    facets = {
        "platforms": sorted({l["platform"] for l in base}),
        "services": sorted({l["service"] for l in base}),
        "tiers": {"ساخن": sum(1 for l in base if l["tier"] == "ساخن"),
                  "دافئ": sum(1 for l in base if l["tier"] == "دافئ"),
                  "مراقبة": sum(1 for l in base if l["tier"] == "مراقبة")},
        "total": len(base), "raw_total": len(d.get("all", [])),
    }
    return {"meta": d.get("meta", {}), "sources": d.get("sources", []),
            "facets": facets, "count": len(res), "leads": res[:limit]}


@app.post("/api/leads/refresh")
def api_leads_refresh():
    if os.environ.get("VERCEL"):
        return {"status": "serverless",
                "message": "الصيد الكامل يعمل على GitHub Actions — سأفتح لك صفحة التشغيل",
                "actions": "https://github.com/abunoafceh8-commits/abunawaf-os/actions/workflows/refresh.yml"}
    if LEAD_JOB["running"]:
        return {"status": "already_running", "started": LEAD_JOB["started"]}
    script = os.path.join(BASE_DIR, "harvest_leads.py")

    def run():
        LEAD_JOB.update({"running": True, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "log": [], "error": None})
        try:
            import subprocess, sys
            p = subprocess.run([sys.executable, script], cwd=BASE_DIR, capture_output=True, text=True, timeout=1800)
            LEAD_JOB["log"] = (p.stdout or "").strip().splitlines()[-40:]
            if p.returncode != 0:
                LEAD_JOB["error"] = (p.stderr or "")[-500:]
        except Exception as e:
            LEAD_JOB["error"] = str(e)[:300]
        finally:
            LEAD_JOB["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


@app.get("/api/leads/status")
def api_leads_status():
    meta = load("leads_raw.json", {}).get("meta", {})
    return {"job": LEAD_JOB, "last_run": meta.get("generated_at")}


@app.post("/api/leads/add")
def api_leads_add(payload: dict):
    manual = load("leads_manual.json", [])
    url = (payload.get("url") or "").strip()
    if not url.startswith("http"):
        raise HTTPException(400, "أدخل رابطاً صحيحاً يبدأ بـ http")
    item = {
        "id": "m" + hashlib.md5((url + str(time.time())).encode()).hexdigest()[:9],
        "title": payload.get("name") or url[:80],
        "name": payload.get("name"),
        "url": url, "platform": payload.get("platform") or "أخرى",
        "service": payload.get("service") or "استعادة حساب مسروق",
        "score": int(payload.get("score") or 70),
        "note": payload.get("note", ""), "snippet": payload.get("note", ""),
        "signals": [], "query": "إدخال يدوي", "kind": "مُضاف يدوياً",
    }
    manual.append(item)
    save("leads_manual.json", manual)
    return {"ok": True, "item": item}


@app.get("/api/leads/export.csv")
def api_leads_csv(tier: Optional[str] = None):
    d = load("leads_raw.json", {"leads": []})
    leads = merge_manual(list(d.get("leads", [])))
    if tier:
        leads = [l for l in leads if l.get("tier") == tier]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["الأولوية", "الدرجة", "المنصة", "الخدمة", "العنوان", "الرابط المباشر", "إشارات", "الإجراء المقترح"])
    for l in sorted(leads, key=lambda x: -x.get("score", 0)):
        w.writerow([l.get("tier"), l.get("score"), l.get("platform"), l.get("service"),
                    l.get("title"), l.get("url"), " | ".join(l.get("signals", [])), l.get("action", "")])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="abunawaf_leads.csv"'})


# ─────────────────────────── الكلمات المفتاحية ───────────────────────────
KW_CACHE = {}


@app.get("/api/keywords")
def api_keywords(intent: Optional[str] = None, q: Optional[str] = None,
                 sort: str = "opportunity", limit: int = 300):
    d = load("keywords.json", {"meta": {}, "keywords": []})
    kws = d["keywords"]
    res = kws
    if intent:
        res = [k for k in res if k["intent"] == intent]
    if q:
        res = [k for k in res if q.lower() in k["keyword"].lower()]
    keymap = {"opportunity": "opportunity", "popularity": "popularity",
              "difficulty": "difficulty", "buyer_intent": "buyer_intent"}
    res = sorted(res, key=lambda k: -k.get(keymap.get(sort, "opportunity"), 0))
    intents = {}
    for k in kws:
        intents[k["intent"]] = intents.get(k["intent"], 0) + 1
    return {"meta": d["meta"], "intents": intents, "total": len(kws),
            "count": len(res), "keywords": res[:limit]}


@app.get("/api/keywords/clusters")
def api_kw_clusters(k: int = 6):
    if "clusters" in KW_CACHE:
        return KW_CACHE["clusters"]
    d = load("keywords.json", {"keywords": []})
    kws = d["keywords"][:600]
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        texts = [x["keyword"] for x in kws]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2)
        X = vec.fit_transform(texts)
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)
        clusters = []
        for i in range(k):
            idx = [j for j, lab in enumerate(km.labels_) if lab == i]
            items = sorted([kws[j] for j in idx], key=lambda z: -z["opportunity"])
            clusters.append({
                "id": i, "size": len(items),
                "label": items[0]["keyword"] if items else f"مجموعة {i}",
                "avg_opportunity": round(sum(x["opportunity"] for x in items) / max(1, len(items)), 1),
                "avg_difficulty": round(sum(x["difficulty"] for x in items) / max(1, len(items)), 1),
                "top": items[:12],
            })
        clusters.sort(key=lambda c: -c["avg_opportunity"])
        KW_CACHE["clusters"] = {"k": k, "method": "TF-IDF (char 2-4) + KMeans", "clusters": clusters}
    except Exception as e:
        KW_CACHE["clusters"] = {"error": str(e)[:200], "clusters": []}
    return KW_CACHE["clusters"]


@app.get("/api/keywords/expand")
def api_kw_expand(seed: str = Query(..., min_length=2)):
    """توسيع حي لأي بذرة عبر Google/Bing Suggest — نفس محرك الملفات السبعة"""
    out = {}
    cl = httpx.Client(headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
    try:
        g = cl.get("https://suggestqueries.google.com/complete/search",
                   params={"client": "firefox", "hl": "ar", "gl": "sa", "q": seed})
        out["google"] = json.loads(g.text)[1]
    except Exception as e:
        out["google"] = []
        out["google_error"] = str(e)[:80]
    try:
        b = cl.get("https://api.bing.com/osjson.aspx", params={"query": seed, "market": "ar-SA"})
        out["bing"] = b.json()[1]
    except Exception as e:
        out["bing"] = []
        out["bing_error"] = str(e)[:80]
    merged = list(dict.fromkeys(out.get("google", []) + out.get("bing", [])))
    return {"seed": seed, "merged": merged, "count": len(merged), "raw": out}


@app.get("/api/keywords/export.csv")
def api_kw_csv():
    d = load("keywords.json", {"keywords": []})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["الكلمة", "النية", "الرواج", "الصعوبة", "نية الشراء", "الفرصة", "ظهور جوجل", "ظهور بينج"])
    for k in d["keywords"]:
        w.writerow([k["keyword"], k["intent"], k["popularity"], k["difficulty"],
                    k["buyer_intent"], k["opportunity"], k["google_hits"], k["bing_hits"]])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="abunawaf_keywords.csv"'})


# ─────────────────────────── الأدوات والحسابات ───────────────────────────
HEALTH = {"at": 0, "data": None}


@app.get("/api/tools")
def api_tools(refresh: bool = False):
    if not refresh and HEALTH["data"] and time.time() - HEALTH["at"] < 900:
        return HEALTH["data"]
    d = load("tools.json", {"tools": []})
    cl = httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
    for t in d["tools"]:
        try:
            r = cl.get(t["url"])
            t["http"] = r.status_code
            t["latency_ms"] = round(r.elapsed.total_seconds() * 1000)
            t["alive"] = r.status_code < 500
            if "تسجيل الدخول" in r.text[:3000] or "login" in str(r.url).lower():
                t["note"] = "يتطلب تسجيل دخول Google"
        except Exception as e:
            t["http"] = None
            t["alive"] = False
            t["error"] = str(e)[:80]
    alive = sum(1 for t in d["tools"] if t.get("alive"))
    d["summary"] = {"total": len(d["tools"]), "alive": alive, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    HEALTH.update({"at": time.time(), "data": d})
    return d


@app.get("/api/social")
def api_social():
    d = load("accounts.json", {"accounts": []})
    cl = httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
    for a in d["accounts"]:
        try:
            r = cl.get(a["url"])
            a["http"] = r.status_code
            a["ok"] = r.status_code == 200
        except Exception as e:
            a["http"] = None
            a["ok"] = False
            a["error"] = type(e).__name__
    try:
        gh = cl.get("https://api.github.com/users/elias0878").json()
        repos = cl.get("https://api.github.com/users/elias0878/repos",
                       params={"per_page": 100, "sort": "updated"}).json()
        d["github"] = {"followers": gh.get("followers"), "public_repos": gh.get("public_repos"),
                       "created_at": gh.get("created_at", "")[:10], "updated_at": gh.get("updated_at", "")[:10],
                       "recent_repos": [{"name": r["name"], "desc": (r.get("description") or "")[:90],
                                         "updated": r["updated_at"][:10], "url": r["html_url"]} for r in repos[:8]]}
    except Exception as e:
        d["github"] = {"error": str(e)[:100]}
    return d


# ─────────────────────────── نظرة عامة ───────────────────────────
@app.get("/api/overview")
def api_overview():
    kw = load("keywords.json", {"meta": {}, "keywords": []})
    leads = load("leads_raw.json", {"meta": {}, "leads": [], "all": []})
    audit = load("audit_last.json", {})
    tools = load("tools.json", {"tools": []})
    social = load("accounts.json", {"accounts": []})
    intents = {}
    for k in kw["keywords"]:
        intents[k["intent"]] = intents.get(k["intent"], 0) + 1
    merged = merge_manual(list(leads.get("leads", [])))
    return {
        "site": {"url": SITE, "pages": len(audit.get("pages", {})) or 7,
                 "scores": audit.get("scores", {}),
                 "crawled_at": audit.get("crawled_at")},
        "leads": {"total": len(merged), "raw": len(leads.get("all", [])),
                  "hot": sum(1 for l in merged if l.get("score", 0) >= 75),
                  "generated_at": leads.get("meta", {}).get("generated_at")},
        "keywords": {"total": len(kw["keywords"]), "queries_used": kw["meta"].get("queries_used"),
                     "intents": intents, "generated_at": kw["meta"].get("generated_at")},
        "tools": {"total": len(tools["tools"])},
        "accounts": {"total": len(social["accounts"])},
    }




# ─────────────────────────── قارئ المصادر (Trafilatura + تقييم النية) ───────────────────────────
READ_CACHE = {}


@app.get("/api/read-url")
def api_read_url(url: str = Query(..., min_length=8)):
    """يقرأ أي رابط عام، يستخرج النص (trafilatura)، ويقيّم نية العميل تلقائياً."""
    if not url.startswith("http"):
        raise HTTPException(400, "أدخل رابطاً يبدأ بـ http")
    if url in READ_CACHE:
        return READ_CACHE[url]
    text, title, method = "", "", ""
    cl = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ar,en;q=0.8"},
                      timeout=45, follow_redirects=True)
    try:
        r = cl.get(url)
    except Exception as e:
        # محاولة أخيرة عبر قارئ صفحات خارجي
        try:
            r = cl.get("https://r.jina.ai/" + url)
            text = r.text
            method = "r.jina.ai reader"
        except Exception:
            raise HTTPException(502, f"تعذر الوصول للرابط: {str(e)[:120]}")
    if not text:
        html = r.text
        try:
            import trafilatura
            text = trafilatura.extract(html, include_comments=True, include_tables=False,
                                       favor_recall=True, deduplicate=True) or ""
            method = "trafilatura"
        except Exception:
            text = ""
        if not text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for t in soup(["script", "style", "nav", "footer"]):
                t.decompose()
            text = soup.get_text(" ", strip=True)
            method = "html fallback"
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else ""

    STRONG = ["مخترق", "مسروق", "موقوف", "مقفل", "مبتز", "ابتزاز", "يهددني", "استرجاع", "استعادة",
              "فك باند", "فك حظر", "ساعدوني", "أحتاج", "محتاج", "تم اختراق", "سرقوا"]
    REQ = ["ساعدوني", "مساعدة", "محتاج", "أحتاج", "اريد", "أريد", "كيف", "وش الحل", "هل من"]
    found = [w for w in STRONG if w in text]
    score = min(96, 30 + len(found) * 9 + (15 if any(w in text for w in REQ) else 0))
    service = "استعادة حساب مسروق"
    if "ابتزاز" in text or "يهددني" in text:
        service = "مكافحة ابتزاز"
    elif any(w in text for w in ["موقوف", "مقفل", "فك باند", "فك حظر"]):
        service = "استعادة حساب موقوف"
    elif any(w in text for w in ["كشف هوية", "مجهول", "انتحال", "ينتحل"]):
        service = "كشف هوية OSINT"
    out = {"url": url, "status": r.status_code, "method": method, "title": title,
           "chars": len(text), "signals": found[:8], "score": score,
           "suggested_service": service,
           "excerpt": re.sub(r"\s+", " ", text)[:1200]}
    READ_CACHE[url] = out
    return out


@app.get("/api/competitors")
def api_competitors():
    return load("competitors.json", {"competitors": [], "gaps_for_abunawaf": []})


@app.get("/api/report", response_class=PlainTextResponse)
def api_report():
    for cand in [
        os.path.join(BASE_DIR, "report.md"),
        os.path.join(BASE_DIR, "..", "تقرير_ابونواف_الشامل.md"),
        os.path.join(BASE_DIR, "data", "report.md"),
    ]:
        if os.path.exists(cand):
            return open(cand, encoding="utf-8").read()
    return "التقرير غير متوفر بعد."


@app.get("/healthz")
def healthz():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
