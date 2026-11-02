# -*- coding: utf-8 -*-
"""
build_static.py — يبني نسخة ثابتة كاملة من المنصة (تعمل على GitHub Pages):
1) يستدعي واجهات FastAPI داخلياً (TestClient) ويحفظ كل الردود كـ JSON.
2) يولّد CSV للعملاء والكلمات.
3) يجمع توسيعات حيّة لبذور مختارة (Google+Bing Suggest).
4) ينسخ الواجهة ويحقن وضع STATIC_MODE.
"""
import json, os, shutil, csv, io, sys, datetime, re

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
SITE = os.environ.get("SITE_OUT") or os.path.join(BASE, "site")
SITE = os.path.abspath(SITE)
DATA_OUT = os.path.join(SITE, "data")
STATIC_SRC = os.path.join(BASE, "static")

os.makedirs(DATA_OUT, exist_ok=True)

from fastapi.testclient import TestClient
from server.app import app

cl = TestClient(app)
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get(path, **params):
    r = cl.get(path, params=params)
    if r.status_code != 200:
        print("!!", path, r.status_code, r.text[:160])
        return None
    return r.json()


print("→ overview")
ov = get("/api/overview")
ov["built_at"] = STAMP
json.dump(ov, open(f"{DATA_OUT}/overview.json", "w"), ensure_ascii=False)

print("→ leads (qualified + raw)")
leads = get("/api/leads", limit=1000)
raw = get("/api/leads", limit=800, include_raw="true")
merged = {"meta": leads["meta"], "sources": leads["sources"],
          "leads": leads["leads"], "all": raw["leads"] if raw else []}
json.dump(merged, open(f"{DATA_OUT}/leads.json", "w"), ensure_ascii=False)

print("→ keywords")
kw = get("/api/keywords", limit=2000)
json.dump({"meta": kw["meta"], "keywords": kw["keywords"]}, open(f"{DATA_OUT}/keywords.json", "w"), ensure_ascii=False)

print("→ clusters")
clusters = get("/api/keywords/clusters", k=6)
json.dump(clusters, open(f"{DATA_OUT}/clusters.json", "w"), ensure_ascii=False)

print("→ expansions (حي)")
seeds = ["استرجاع حساب", "حسابي مخترق", "فك باند سناب", "ابتزاز الكتروني",
         "هكر اخلاقي سعودي", "كشف هوية حساب", "استرجاع حساب انستقرام", "حسابي موقوف",
         "اختراق واتساب", "حذف حساب شخص متوفي"]
exp = {}
for s in seeds:
    d = get("/api/keywords/expand", seed=s)
    if d:
        exp[s] = d
json.dump(exp, open(f"{DATA_OUT}/expansions.json", "w"), ensure_ascii=False)

print("→ seo audit (حي)")
audit = get("/api/seo/audit")
if audit:
    json.dump(audit, open(f"{DATA_OUT}/audit.json", "w"), ensure_ascii=False)

print("→ seo fixes")
fixes = get("/api/seo/fixes")
json.dump(fixes, open(f"{DATA_OUT}/fixes.json", "w"), ensure_ascii=False)

print("→ tools / social / competitors")
json.dump(get("/api/tools"), open(f"{DATA_OUT}/tools.json", "w"), ensure_ascii=False)
json.dump(get("/api/social"), open(f"{DATA_OUT}/social.json", "w"), ensure_ascii=False)
shutil.copy(os.path.join(BASE, "data", "competitors.json"), f"{DATA_OUT}/competitors.json")

# ── التقرير ──
for cand in [os.path.join(BASE, "report_source.md"),
             os.path.join(BASE, "..", "تقرير_ابونواف_الشامل.md"),
             os.path.join(BASE, "..", "..", "تقرير_ابونواف_الشامل.md")]:
    if os.path.exists(cand):
        shutil.copy(cand, f"{DATA_OUT}/report.md")
        print("report ←", cand)
        break

# ── CSV ──
def write_csv(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    open(f"{DATA_OUT}/{name}", "w", encoding="utf-8-sig").write(buf.getvalue())


write_csv("leads.csv", ["الأولوية", "الدرجة", "المنصة", "الخدمة", "العنوان", "الرابط المباشر", "إشارات", "الإجراء المقترح"],
          [[l.get("tier"), l.get("score"), l.get("platform"), l.get("service"), l.get("title"),
            l.get("url"), " | ".join(l.get("signals") or []), l.get("action", "")]
           for l in sorted(merged["leads"], key=lambda x: -x.get("score", 0))])

write_csv("keywords.csv", ["الكلمة", "النية", "الرواج", "الصعوبة", "نية الشراء", "الفرصة", "الصلة", "ظهور جوجل", "ظهور بينج"],
          [[k["keyword"], k["intent"], k["popularity"], k["difficulty"], k["buyer_intent"],
            k["opportunity"], k.get("relevance", ""), k["google_hits"], k["bing_hits"]]
           for k in kw["keywords"]])

# ── الواجهة ──
for f in ["index.html", "app.css", "app.js", "static-api.js"]:
    shutil.copy(os.path.join(STATIC_SRC, f), os.path.join(SITE, f))

html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
inject = (
    '<script>window.STATIC_MODE=true;'
    'window.BUILD_STAMP="' + STAMP + '";'
    'window.ACTIONS_URL="https://github.com/abunoafceh8-commits/abunawaf-os/actions";</script>\n'
    '<script src="static-api.js"></script>\n'
    '<script src="app.js"></script>'
)
html = html.replace('<script src="app.js"></script>', inject)
open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html)

# .nojekyll حتى لا يتجاهل Jekyll أي ملفات
open(os.path.join(SITE, ".nojekyll"), "w").write("")
# 404 → الصفحة الرئيسية (تطبيق صفحة واحدة)
shutil.copy(os.path.join(SITE, "index.html"), os.path.join(SITE, "404.html"))

# manifest + robots للأرشفة
json.dump({
    "name": "منصة فريق أبو نواف — مركز العمليات", "short_name": "أبو نواف OS",
    "start_url": "./", "display": "standalone", "background_color": "#050912", "theme_color": "#0a1120",
    "icons": []
}, open(os.path.join(SITE, "manifest.json"), "w"), ensure_ascii=False)
open(os.path.join(SITE, "robots.txt"), "w").write("User-agent: *\nDisallow: /\n")

print("✔ تم بناء النسخة الثابتة في", SITE, "|", STAMP)
