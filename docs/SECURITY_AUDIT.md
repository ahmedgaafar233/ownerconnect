# تدقيق كود ومراجعة أمنية — مشروع OwnerConnect

تاريخ المراجعة: 2026-09-05
نطاق المراجعة: كل الـ Django apps (core, users, billing, collections_app, support, messenger, imports)، إعدادات النشر (Docker/Nginx)، ملفات البيئة، اللوجات، وتغطية الاختبارات. المراجعة اعتمدت على قراءة الكود الفعلي + سجلات الأخطاء الحقيقية (`django_errors.log`)، مش تخمين.

---

## الخلاصة

المشروع مبني كويس ومفيه وعي أمني واضح في أجزاء منه (خصوصًا الدفع الأونلاين عبر Paymob)، لكن فيه **ثغرة معمارية متكررة** بتضرب فكرة "multi-tenant" اللي المشروع مبني عليها: عزل البيانات بين المنتجعات (Resorts) مش متطبق بشكل متسق. بالإضافة لباج مؤكد (مش نظري) بيكسر صفحة تسجيل التحصيل، وكذلك إعدادات بيئة حالية (DEBUG=1، مفاتيح placeholder) لازم متتنقلش للإنتاج زي ما هي.

---

## 1) الأهم: عزل المستأجرين (Tenant Isolation) مش متسق — خطورة عالية

المشروع بيوصف نفسه "Multi-Tenant SaaS" وفيه `TenantMiddleware` مخصص لده، لكن التطبيق الفعلي غير مكتمل:

**أ. `core/middleware.py` (`TenantMiddleware`, أسطر 30-39):**
لو المستخدم موظف (`is_staff`) ومش superuser، الميدل وير بيقبل أي قيمة في هيدر `X-Resort-ID` ويحمّل الـ Resort المطلوب **من غير ما يتأكد إن الموظف ده أصلاً تابع للريزورت ده**:
```python
if user.is_staff or getattr(user, "is_superuser", False):
    if resort_id_header and resort_id_header.isdigit():
        try:
            request.tenant = Resort.objects.get(id=int(resort_id_header), is_active=True)
        ...
```
بالمقارنة، نفس الميدل وير بيتحقق صح من ملكية الوحدة للـ Owners (سطر 44-47). يعني أي موظف (Data Entry / Reception / Supervisor...) يقدر يبعت هيدر `X-Resort-ID` بقيمة ريزورت تاني ويقرا بياناته — و`nginx.conf` (سطر 45، 58) بيمرر الهيدر ده زي ما هو من العميل (`$http_x_resort_id`) من غير أي تحقق على مستوى الـ proxy.

**ب. أماكن تانية معندهاش فلترة على مستوى الريزورت خالص (مش حتى من الهيدر):**
- `collections_app/views.py` → `record_payment_view`: `selected_unit = Unit.objects.filter(id=unit_id).first()` (سطر 204) — من غير `resort=`. أي موظف تحصيل يقدر يسجل دفعة على وحدة في ريزورت تاني تمامًا لو عرف الـ unit_id.
- `collections_app/views.py` → `daily_collections_view`: الاستعلام الأساسي `payments_qs = Payment.objects.filter(**date_filter)` (سطر 55-56) من غير فلتر ريزورت خالص — فالموظف بيشوف تحصيلات كل المنتجعات في اليوم/الشهر، مش بتاعه بس. (فلتر الريزورت مطبق جزئيًا بس على "original_debt" في سطر 84-86، مش على قائمة الدفعات نفسها).
- `support/views.py` → `TicketDetailView.get_queryset`: للموظفين، `return qs` من غير أي فلتر (سطر 68-74) — أي موظف يقدر يفتح/يعدّل/**يحذف** أي تذكرة دعم من أي ريزورت بمجرد معرفة الـ id.
- `support/views.py` → `TicketMessageListCreateView`: الـ`get_queryset` بتتحقق من ملكية الـ Owner للتذكرة، لكن `perform_create` (سطر 92-96) **بتجيب التذكرة من غير أي تحقق** وتسمح لأي مستخدم مسجّل بإضافة رسالة على أي تذكرة أيًا كان مالكها.
- `imports/views.py`: `handle_upload` (سطر 53) و`handle_commit` (سطر 87) بيجيبوا `ImportSource`/`ExcelUpload` بالـ id من غير التحقق إنهم تابعين لريزورت المستخدم.
- Django Admin: `core/admin.py` (`UnitAdmin`, `OwnerUnitAdmin`, `ResortAdmin`)، `billing/admin.py` (`ChargeAdmin.get_queryset`)، `collections_app/admin.py` (`PaymentAdmin.get_queryset`)، `support/admin.py` (`TicketAdmin.get_queryset`) — كلهم بيتحكموا في **مين يقدر يستخدم النموذج** حسب الدور، لكن محدش منهم بيفلتر **الصفوف** حسب `resort`. يعني أي Financial Manager أو Supervisor من أي ريزورت، من شاشة الـ admin العادية، يشوف/يعدّل بيانات كل المنتجعات المالية.

**التوصية:** إصلاح `TenantMiddleware` بحيث الموظف (غير superuser) ميقدرش ياخد tenant غير `user.resort` بتاعه (تجاهل الهيدر تمامًا لغير الـ superadmin)، وبعدين إضافة `resort=request.user.resort` (أو `request.tenant`) كفلتر إجباري في كل الأماكن المذكورة فوق، بما فيها `get_queryset` بتاعة الـ admin classes.

---

## 2) باج مؤكّد (موجود فعلًا في اللوج) — `record_payment_view` بيقع بـ 500

من `django_errors.log`:
```
UnboundLocalError: cannot access local variable 'Payment' where it is not associated with a value
File "collections_app/views.py", line 235, in record_payment_view
    payment_history = Payment.objects.filter(...)
```
السبب: الملف فيه `from collections_app.models import Payment` في الأعلى، لكن جوه نفس الفانكشن فيه إعادة استيراد محلي `from collections_app.models import Payment, PaymentAllocation` داخل شرط الـ POST الناجح. بايثون بمجرد ما يلاقي `import` جوه الفانكشن بيعتبر الاسم "local" **لكل الفانكشن كلها**، فأي استخدام لـ `Payment` قبل سطر الـ import المحلي (زي `payment_history` في القسم اللي بيحصل عادي مع أي GET فيه `unit_id`) بيرمي `UnboundLocalError`. يعني الميزة دي — عرض تاريخ دفعات وحدة عند البحث عنها — بتكسر باستمرار.

**الحل:** شيل الـ import المحلي (سطر ~279) واعتمد على الـ import اللي فوق الملف بس.

ملاحظة إضافية: نفس الملف فيه `payment_history if 'payment_history' in locals() else []` (سطر ~169) في `daily_collections_view` — متغير مش متعرّف أصلاً في الفانكشن دي، بقية من كود مش مكتمل (مش خطر لكنه يدل على كود ناقص).

---

## 3) إعدادات البيئة الحالية لو راحت للإنتاج زي ما هي — خطورة عالية

من `.env` الحالي:
```
DEBUG=1
SECRET_KEY=dev-secret-change-me-local
PAYMENT_HMAC_KEY=replace-with-paymob-hmac-secret
PAYMOB_API_KEY=replace-with-paymob-api-key
```
- `DEBUG=1` معناه: أي استثناء في الكود هيطلع traceback كامل (مسارات، إعدادات، أحيانًا قيم متغيرات) لأي حد بره. `settings.py` بيوقف كل هيدرز الأمان (HSTS, secure cookies, SSL redirect...) لما `DEBUG=True` (سطر 52-65) — يعني النظام دلوقتي شغال من غيرهم.
- **الأخطر:** `users/views.py` → `FirebaseAuthView` (سطر 59-67) فيها استثناء صريح: `if settings.DEBUG and id_token.startswith("dev_test_token_"): phone_number = ...`. طالما `DEBUG=1`، أي حد يقدر يسجّل دخول كأي رقم تليفون (حتى لو مش بتاعه) من غير أي تحقق فعلي من Firebase، فقط بإرسال `id_token = "dev_test_token_<الرقم>"`. لازم القفلة دي متعتمدش على `DEBUG` بس، ولازم `DEBUG` يبقى `0` في أي بيئة متاحة لغير المطورين.
- `PAYMENT_HMAC_KEY`/`PAYMOB_API_KEY` لسه قيم placeholder — يعني تكامل الدفع مش شغال فعليًا بمفاتيح حقيقية حتى الآن (تفصيل إضافي تحت في القسم 4).
- `docker-compose.yml` بيحمّل نفس ملف `.env` في كل الخدمات (`web`, `celery_worker`, `celery_beat`) عن طريق `env_file: .env` (أسطر 41-42, 61-62, 78-79) — مفيش فصل بين إعدادات التطوير والإنتاج؛ لو الـ `.env` الحالي هو اللي هيتنقل للسيرفر، القيم الضعيفة فوق هتشتغل هناك زي ما هي.

**التوصية:** ملف `.env` منفصل تمامًا للإنتاج (`DEBUG=0`, `SECRET_KEY` عشوائي طويل، مفاتيح Paymob حقيقية)، ومراجعة إن الـ dev bypass بتاع Firebase مش هيشتغل غير في بيئة تطوير معزولة فعليًا.

---

## 4) الدفع الأونلاين (Paymob) — الأساس قوي، لكن ناقص جزء مهم

الحاجة الإيجابية: `collections_app/api_views.py` مكتوبة كويس جدًا أمنيًا — HMAC-SHA512 بيتحقق بـ`hmac.compare_digest`، المبلغ و charge_ids بيتقفلوا في `PaymentSession` قبل التحويل لـ Paymob وميتاخدوش من الـ webhook body، فيه `select_for_update()` لمنع التنفيذ المزدوج، وفيه idempotency check على `receipt_no`. ده تصميم سليم.

**لكن الناقص:** `checkout_url` (سطر 205-209) بيتبني بقيمة ثابتة:
```python
checkout_url = f"https://accept.paymob.com/api/acceptance/iframes/{paymob_iframe_id}?payment_token=REPLACE_WITH_PAYMOB_TOKEN"
```
يعني استدعاء Paymob الفعلي (Order Registration API + Payment Key Request) لسه مش متكتوب — الـ endpoint بيرجع رابط دفع مش هيشتغل فعليًا. ده أهم حاجة "ناقصة" علشان الدفع الأونلاين يشتغل بشكل حقيقي.

---

## 5) نقاط أمان تانية تستاهل تتعالج

- **JWT بدون revocation:** `SIMPLE_JWT` (settings.py سطر 172-175): access token 12 ساعة، refresh token 30 يوم، ومفيش `rest_framework_simplejwt.token_blacklist` مُفعّل. يعني لو توكن اتسرق، مفيش طريقة تلغيه قبل ما ينتهي لوحده.
- **Brute-force على كود التفعيل:** كود التفعيل 6 أرقام مع throttle "auth" = 5 محاولات/دقيقة (settings.py سطر 164) — تحسّن كبير لكن لسه مفيش قفل حساب بعد عدد محاولات فاشلة معيّن.
- **Docker/DB مكشوفين:** `docker-compose.yml` بينشر بورت Postgres (`5432:5432`) و Redis (`6379:6379`) على الـ host مباشرة (أسطر 9-10، 22-23) — دول مش محتاجين ينشروا خالص لأن `web`/`celery` بيوصلولهم من جوه شبكة Docker الداخلية. ده بيوسّع سطح الهجوم لو السيرفر مكشوف.
- **باسورد Postgres افتراضي مكتوب في الكود:** `ownerconnect_secure_pass` كـ fallback لو `POSTGRES_PASSWORD` مش متظبط (أسطر 8, 44, 64, 81).
- **حسابات تجريبية بباسورد ضعيف:** `setup_test_users.py` بيعمل حسابات (منها SUPERADMIN) بباسورد ثابت `password123`. لازم تتأكد إن السكريبت ده ما اتشغلش على قاعدة بيانات إنتاج، أو تتغير الباسوردات دي فورًا لو اتشغل.

---

## 6) نسخة Django وتحديث الاعتمادية (Dependencies)

`requirements.txt` مثبت `Django==5.1.5`. بالرجوع لإعلانات Django الأمنية الرسمية في 2026، كل التحديثات الأمنية اللي صدرت (فبراير، أبريل، مايو، أغسطس 2026) كانت لسلاسل **6.0.x / 5.2.x / 4.2.x** فقط — ولا واحدة منها ذكرت 5.1.x. ده مؤشر قوي إن فرع 5.1 (مش LTS) خرج من الدعم الأمني خلاصًا. التوصية: الترقية لـ Django 5.2 (LTS).

مفيش حاليًا أي أداة فحص اعتمادية آلية (زي `pip-audit` أو Dependabot) على الـ ~90 باكيدج المثبتين — يفضّل إضافتها للـ CI.

Sources:
- [Django security releases issued: 6.0.4, 5.2.13, and 4.2.30](https://www.djangoproject.com/weblog/2026/apr/07/security-releases/)
- [Django security releases issued: 6.0.8 and 5.2.17](https://www.djangoproject.com/weblog/2026/aug/04/security-releases/)
- [Django security releases issued: 6.0.5 and 5.2.14](https://www.djangoproject.com/weblog/2026/may/05/security-releases/)
- [Django security releases issued: 6.0.2, 5.2.11, and 4.2.28](https://www.djangoproject.com/weblog/2026/feb/03/security-releases/)
- [Django EOL Guide: Dates, Risks & Solutions in 2026](https://tuxcare.com/blog/django-eol-guide-2026/)

---

## 7) جودة الكود وجاهزية "الكمال"

- **صفر اختبارات فعلية:** كل ملف `tests.py` في كل الـ apps (billing, collections_app, core, users, support, messenger, imports) هو stub فاضي (60 بايت). مفيش أي اختبار آلي — حتى على منطق مالي حساس زي توزيع الدفعات (FIFO allocation) أو الـ webhook idempotency، واللي أخطر جزء لو فيه باج.
- **بقايا تطوير في الريبو:** لقطات شاشة (`*.png`)، `.dev_server.pid`، `dev_server.log`، `settings.py.save` (فاضي)، `db.sqlite3` — موجودين فعليًا على القرص (بعضهم متجاهل في `.gitignore` بس لسه موجودين ويستحقوا تنضيف).
- **كود ميت:** `users/services.py::validate_activation_code` دالة فاضية (`pass`) والمنطق الفعلي اتكرر في الـ Serializer بدالها.
- **تناقض في نمط الكود:** بعض الأماكن (core/views.py، messenger app بالكامل، billing API الخاص بالـ Owner) مطبقة عزل البيانات صح ومكتوبة بعناية، بينما أماكن تانية (القسم 1) ناقصة — يدل على إن المراجعة الأمنية اتعملت جزئيًا مش شاملة.

---

## قائمة أولويات للإصلاح (الأهم أولًا)

1. إصلاح `TenantMiddleware` — الموظف (غير superuser) ميقدرش يتجاوز `user.resort` بتاعه عبر الهيدر.
2. إضافة فلتر `resort` في: `record_payment_view`, `daily_collections_view`, `TicketDetailView`, `TicketMessageListCreateView.perform_create`, `ImportWizardView` (upload/commit)، وكل `get_queryset` في الـ admin classes المذكورة.
3. إصلاح الـ `UnboundLocalError` في `record_payment_view` (شيل الـ import المحلي المكرر).
4. فصل `.env` إنتاج عن تطوير: `DEBUG=0`، `SECRET_KEY` حقيقي عشوائي، مفاتيح Paymob حقيقية — وتأكيد إن Firebase dev-bypass معزول تمامًا عن أي بيئة حقيقية.
5. استكمال استدعاء Paymob الفعلي (Order Registration / Payment Key) بدل الـ placeholder token.
6. تفعيل `token_blacklist` في SimpleJWT لإمكانية إلغاء التوكنات.
7. عدم نشر بورتات Postgres/Redis على الـ host في `docker-compose.yml`، وشيل الباسورد الافتراضي المكتوب بالكود.
8. ترقية Django لـ 5.2 LTS، وإضافة فحص اعتمادية آلي (pip-audit/Dependabot).
9. كتابة اختبارات آلية على الأقل لمنطق التحصيل والدفع (allocation FIFO + webhook idempotency).
10. تنضيف بقايا التطوير من الريبو، والتأكد (بمراجعة تاريخ Git) إن `.env` أو `db.sqlite3` ما اتعملهملوش commit قبل إضافتهم لـ `.gitignore`.
