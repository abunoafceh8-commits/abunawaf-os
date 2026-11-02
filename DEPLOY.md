# النشر — الحالة الفعلية (محدّثة)

## ✅ يعمل الآن على الإنترنت (رابط حقيقي)
| المكوّن | المكان | الحالة |
|---|---|---|
| الواجهة (8 وحدات) | GitHub Pages → `https://abunoafceh8-commits.github.io/abunawaf-os/` | ✅ |
| المحرّك المجدول (صيد + كلمات + بناء) | GitHub Actions كل 12 ساعة / يدوياً | ✅ نُفِّذ فعلياً |
| **قاعدة البيانات الحيّة** | Supabase Postgres `kneluxgbulzvnedjarsf` | ✅ 26 عميلاً · 1,212 كلمة |
| **خادم Deno Edge** | `.../functions/v1/api/{health,expand,read-url,stats}` | ✅ يعمل |
| النسخ الاحتياطي المحلي | FastAPI + Uvicorn (`_app/server/app.py`) | ✅ يعمل على أي جهاز |

## مفتاح الفريق
`abunawaf-2026` — يُطلب عند أول كتابة، ويُخزَّن في المتصفح. غيّره من `SUPABASE.md`.

## ⚠️ Vercel
مفتاح Vercel المرفق مرفوض من Vercel: `{"error":{"code":"forbidden","invalidToken":true}}`
(جُرِّب على `/v2/user`, `/v9/projects`, `/v3/user`, `?token=`, و`api.v0.dev`).
لتفعيل Vercel لاحقاً: أنشئ توكن جديداً ثم:
```bash
cd _app && npx vercel --prod --token $NEW_TOKEN
```
`vercel.json` جاهز. لكن **لا حاجة له** — الخادم الديناميكي يعمل الآن عبر Supabase Edge Functions،
وقاعدة البيانات عبر PostgREST، والجدولة عبر GitHub Actions.

## أوامر مفيدة
```bash
# إعادة بناء المخطط كاملاً
python3 supabase_setup.py
# تحديث البيانات ثم إعادة بناء الموقع
SITE_OUT=/path/to/repo python3 refresh_data.py
# تشغيل الخادم المحلي الكامل
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```
