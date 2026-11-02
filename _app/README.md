# منصة فريق أبو نواف — AbuNawaf OS

منصة تشغيل داخلية للفريق: صيد العملاء المحتملين، ذكاء كلمات البحث، مدقق SEO حي لموقع `ant.xo.je`،
وسجل أدوات مع فحص صحة فعلي. كل البيانات المعروضة **مُجمّعة حقيقياً** من مصادر عامة، لا أمثلة ثابتة.

## التشغيل
```bash
cd abunawaf
pip install fastapi "uvicorn[standard]" httpx beautifulsoup4 pycryptodome scikit-learn trafilatura
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 8000
# ثم افتح http://localhost:8000
```

## تحديث البيانات
```bash
python3 harvest_keywords.py   # كلمات البحث (Google + Bing Suggest) → data/keywords.json
python3 harvest_leads.py      # العملاء المحتملون (Bing SERP عبر r.jina.ai) → data/leads_raw.json
```
أو من الواجهة: زر «⚡ صيد جديد» و«⟳ إعادة الزحف الآن».

## البنية
```
abunawaf/
├── server/app.py            # FastAPI: كل الـAPIs
├── static/                  # الواجهة (HTML/CSS/JS) — عربي RTL بلا أي مكتبات خارجية
├── harvest_keywords.py      # محرك جمع الكلمات
├── harvest_leads.py         # محرك صيد العملاء
├── data/
│   ├── keywords.json        # 1,212 كلمة + درجات + فلترة الصلة
│   ├── leads_raw.json       # النتائج الخام + المؤهلة + حالة المصادر
│   ├── leads_manual.json    # القائمة المُتحقَّق منها يدوياً (26 عميلاً)
│   ├── tools.json           # 17 أداة + كتالوج الملفات السبعة
│   ├── accounts.json        # القنوات الرسمية
│   ├── competitors.json     # 7 منافسين
│   └── audit_last.json      # آخر نتيجة زحف (كاش)
└── shots/                   # صور فحص الواجهة (Playwright)
```

## نقاط API
| المسار | الوظيفة |
|---|---|
| `/api/overview` | مؤشرات اللوحة |
| `/api/leads` | القائمة + الفلاتر + مصادر الصيد |
| `/api/leads/refresh` | تشغيل محرك الصيد في الخلفية |
| `/api/leads/add` | إضافة عميل يدوياً |
| `/api/leads/export.csv` | تصدير |
| `/api/keywords` · `/clusters` · `/expand` · `/export.csv` | محرك الكلمات |
| `/api/seo/audit?refresh=true` | زحف حي لـ ant.xo.je (يحل تحدي __test) |
| `/api/seo/fixes` | عناوين/أوصاف/Schema جاهزة |
| `/api/read-url?url=` | قراءة أي رابط + تقييم النية (trafilatura) |
| `/api/tools` · `/api/social` · `/api/competitors` · `/api/report` | باقي الوحدات |

## ملاحظات صحة/أمان
- المنصة **لا تخترق** أي منصة ولا تتجاوز أي حماية؛ تقرأ صفحات عامة فقط.
- المنصات الكبرى (X/Instagram/TikTok/Reddit) تحجب الطلبات الآلية — لذلك المحرك يعمل بطبقة قارئ صفحات،
  وبعض الاستعلامات قد ترجع 429/503 ويظهر ذلك في «حالة مصادر الصيد».
- صفحة الأدوات في `ant.xo.je` محميّة بكلمة سر داخل HTML — التفاصيل في التقرير الشامل.
