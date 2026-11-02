# النشر — الحالة والخطوات

## ✅ ما هو منشور الآن (حقيقي ويعمل)
| المكوّن | الحالة |
|---|---|
| الواجهة الكاملة (8 وحدات) | منشورة على **GitHub Pages** عبر HTTPS |
| البيانات (عملاء/كلمات/تدقيق SEO/أدوات) | ملفات JSON/CSV تُولَّد آلياً |
| **الخادم المجدول** | **GitHub Actions** يشغّل محرّكات الجمع والزحف كل 12 ساعة أو يدوياً، ثم ينشر |
| التحديث اليدوي الفوري | Actions → «Run workflow» |

الرابط: https://abunoafceh8-commits.github.io/abunawaf-os/

## ⚠️ ما لم يُنشر: خادم FastAPI المباشر
سببان تقنيان موثّقان:
1. **مفتاح Vercel المرفق غير صالح** — رفضه `api.vercel.com` بكل نقاط النهاية:
   `{"error":{"code":"forbidden","message":"Not authorized","invalidToken":true}}`
   (تم اختباره بـ3 صيغ ترويسة، وبـ`api.v0.dev` أيضاً.)
2. الميزات التي تحتاج خادماً دائماً (زحف لحظي، قراءة أي رابط، تشغيل صيد من الواجهة)
   لا تعمل على الاستضافة الثابتة — لكن **النتيجة نفسها متاحة** لأن Actions يشغّل نفس الكود.

## كيف تنشر الخادم في 3 دقائق (عند توفّر مفتاح صالح)
### Vercel
```bash
cd _app
npx vercel link --yes --token $VERCEL_TOKEN
npx vercel --prod --token $VERCEL_TOKEN
```
`vercel.json` جاهز (يتضمن `includeFiles` لكل البيانات والأصول).

### أو أي خادم Linux / Render / Railway / Fly
```bash
pip install -r requirements.txt
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### أو Cloudflare Tunnel (بدون استضافة جديدة)
```bash
python -m uvicorn server.app:app --port 8000 &
cloudflared tunnel --url http://localhost:8000
```

## ما الذي يتغيّر عند تشغيل الخادم؟
- زر «⚡ صيد جديد» يعمل لحظياً بدل توجيهك إلى Actions.
- «⌕ اقرأ وقيّم» يحلّل أي رابط عميل بـ trafilatura.
- «⟳ إعادة الزحف الآن» يفحص ant.xo.je لحظياً.
- الإضافة اليدوية تُخزَّن في قاعدة البيانات بدل `localStorage`.
