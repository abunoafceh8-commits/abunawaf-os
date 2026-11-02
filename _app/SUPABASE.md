# قاعدة البيانات الحيّة + الخادم الحقيقي (Supabase)

## ما يعمل الآن فعلياً

| المكوّن | التفاصيل |
|---|---|
| **قاعدة البيانات** | Supabase Postgres 17 — مشروع `abunawaf-platform` (`kneluxgbulzvnedjarsf`, منطقة `eu-central-1`) |
| **الجداول** | `os_leads` (26 عميلاً) · `os_keywords` (1,212 كلمة) · `os_notes` · `os_events` · `os_config` |
| **الأمان** | RLS مفعّل: قراءة عامة فقط، **كل الكتابة عبر دوال `SECURITY DEFINER`** بمفتاح فريق |
| **الواجهة البرمجية** | PostgREST جاهز: `https://kneluxgbulzvnedjarsf.supabase.co/rest/v1/os_leads` |
| **خادم Deno Edge** | `https://kneluxgbulzvnedjarsf.supabase.co/functions/v1/api` |

## مفتاح الفريق
```
abunawaf-2026
```
- الواجهة تطلبه مرة واحدة عند أول عملية كتابة وتخزّنه في المتصفح.
- لتغييره:
```sql
update public.os_config
set value = encode(extensions.digest('المفتاح-الجديد','sha256'),'hex')
where key = 'team_hash';
```

## نقاط النهاية
### PostgREST (قراءة)
```
GET  /rest/v1/os_leads?select=*&order=score.desc&limit=50
GET  /rest/v1/os_keywords?select=keyword,opportunity&order=opportunity.desc&limit=20
GET  /rest/v1/os_notes?lead_id=eq.<id>&order=created_at.desc
```
### دوال RPC (كتابة)
```
POST /rest/v1/rpc/os_add_lead     { p:{url,title,platform,service,score,...}, p_key }
POST /rest/v1/rpc/os_set_status   { p_id, p_status, p_key, p_owner?, p_notes? }
POST /rest/v1/rpc/os_add_note     { p_lead, p_body, p_key, p_author? }
POST /rest/v1/rpc/os_stats        {}
```
### Edge Function
```
GET  /functions/v1/api/health
GET  /functions/v1/api/expand?seed=استرجاع حساب      → اقتراحات Google + Bing حيّة
GET  /functions/v1/api/read-url?url=https://…        → استخراج + تقييم نية العميل
GET  /functions/v1/api/stats
```
جميعها تحتاج ترويسة `apikey: <anon key>`.

## إعادة بناء كل شيء من الصفر
```bash
python3 supabase_setup.py                     # المخطط + RLS + الدوال + بذر البيانات
# نشر دالة الحافة:
curl -X PATCH -H "Authorization: Bearer $SUPABASE_PAT" -H "Content-Type: application/json" \
  https://api.supabase.com/v1/projects/kneluxgbulzvnedjarsf/functions/api \
  -d "$(python3 -c 'import json;print(json.dumps({"slug":"api","name":"api","verify_jwt":False,"body":open("edge/api.ts").read()}))')"
```
المخطط الكامل محفوظ في `supabase/schema.sql`.

## ملاحظات أمنية
- مفتاح `anon` عام بطبيعته (موجود في صفحة الموقع) — محمي بـ RLS.
- مفتاح `service_role` **لا يُوضع في الواجهة أبداً**؛ يُستخدم فقط داخل دالة الحافة عبر متغيّرات البيئة.
- أي كتابة بدون مفتاح الفريق تُرفض: `{"ok": false, "error": "مفتاح الفريق غير صحيح"}`.
