# منصة فريق أبو نواف — AbuNawaf OS

مركز العمليات الرقمي لفريق أبو نواف: **صيد عملاء محتملين + ذكاء كلمات بحث + مدقق SEO حي لموقع ant.xo.je**.
الموقع منشور على GitHub Pages، والبيانات تُحدَّث آلياً بواسطة GitHub Actions (خادم حقيقي مجدول).

## 🔗 الروابط
| ماذا | أين |
|---|---|
| المنصة (النسخة الحيّة) | https://abunoafceh8-commits.github.io/abunawaf-os/ |
| تشغيل تحديث فوري | https://github.com/abunoafceh8-commits/abunawaf-os/actions/workflows/refresh.yml |
| البيانات الخام (JSON) | `/data/leads.json` · `/data/keywords.json` · `/data/audit.json` |
| تصدير CSV | `/data/leads.csv` · `/data/keywords.csv` |
| التقرير الشامل | `/data/report.md` (وداخل المنصة) |

## كيف تعمل؟
```
GitHub Actions (كل 12 ساعة أو يدوياً)
   ├── harvest_leads.py      → 70 استعلام بحث حقيقي → data/leads_raw.json
   ├── harvest_keywords.py   → Google+Bing Suggest (أسبوعياً) → data/keywords.json
   ├── build_static.py       → يستدعي واجهات FastAPI داخلياً ويولّد كل ملفات JSON/CSV
   └── commit + push         → GitHub Pages ينشر النسخة الجديدة تلقائياً
```
- **النسخة الثابتة** (`index.html` + `data/*.json`) تعمل بلا خادم عبر `static-api.js`
  الذي يحاكي واجهات الـAPI نفسها (فلاتر، فرز، تصدير، إضافة عملاء محلياً في `localStorage`).
- **نسخة الخادم الكامل** (FastAPI) موجودة في `_app/` وتشمل ما لا يعمل في المتصفح:
  الزحف الحي وحل تحدي `__test`، قراءة أي رابط بـ trafilatura، والتشغيل المباشر للصيد.

## تشغيل نسخة الخادم محلياً
```bash
cd _app
pip install -r requirements.txt
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
# http://localhost:8000
```

## النشر على Vercel (عند توفّر مفتاح صالح)
```bash
cd _app && npx vercel --prod --token $VERCEL_TOKEN
```
`vercel.json` جاهز ويضمّن ملفات البيانات والأصول.

## وحدات المنصة
1. **لوحة القيادة** — درجات الموقع (SEO/أداء/أمان/محتوى) + توزيع نوايا الكلمات + أهم المشكلات + أعلى العملاء.
2. **صيد العملاء** — 26 عميلاً مؤهلاً (11 ساخن) مع رابط مباشر لكل حالة، فلاتر، إضافة يدوية، تصدير.
3. **كلمات البحث** — 1,212 كلمة بدرجات الرواج/الصعوبة/نية الشراء/الفرصة + 6 مجموعات دلالية (TF-IDF+KMeans) + فلترة صلة.
4. **مدقق SEO الحي** — 14 مشكلة مرتبة بالخطورة + عناوين/أوصاف مقترحة + Schema جاهز.
5. **المنافسون** — 7 منافسين بقوتهم وثغرتهم.
6. **الأدوات** — فحص صحة 17 أداة + كتالوج الملفات السبعة.
7. **القنوات الرسمية** — فحص حي للحسابات + ملف GitHub.
8. **التقرير الشامل** — 16 قسماً + خطة 30 يوماً.

## بنية المستودع
```
/                     ← الموقع المنشور (GitHub Pages)
├── index.html  app.css  app.js  static-api.js  404.html
├── data/             ← كل البيانات (JSON + CSV + التقرير) تُولَّد آلياً
└── _app/             ← الكود المصدري (FastAPI + محرّكات الجمع + بناء النسخة الثابتة)
    ├── server/app.py
    ├── harvest_leads.py  harvest_keywords.py  build_static.py  refresh_data.py
    └── data/          ← بيانات المصدر (تُحدَّث بالتشغيل)
```

## ضوابط
- لا اختراق ولا تجاوز لأي حماية — قراءة صفحات **عامة** فقط، مع احترام `rate limit` وأوقات الانتظار.
- كل نتيجة عميل تأتي مع رابطها المباشر + درجة ثقة + إشارات — والتحقق النهائي بشري.
- الحدود: X/إنستقرام/تيك توك/ريديت تحجب الطلبات الآلية (429/403)، لذلك التغطية جزئية وتظهر حالة كل مصدر.
