# اتصال Supabase به Kafil Music

این راهنما تمام مراحل اتصال Supabase (PostgreSQL + pgvector) به بک‌اند Kafil Music را پوشش می‌دهد.

---

## پیش‌نیازها

- یک پروژه Supabase با دسترسی به داشبورد
- نصب `psycopg2-binary` برای اتصال PostgreSQL:

```bash
pip install psycopg2-binary
```

---

## مرحله ۱ — فعال‌سازی pgvector در Supabase

در Supabase، افزونه `vector` باید فعال شود. از طریق **SQL Editor** در داشبورد Supabase:

```sql
-- فعال‌سازی pgvector (فقط یک‌بار لازم است)
CREATE EXTENSION IF NOT EXISTS vector;

-- بررسی: باید نسخه pgvector نمایش داده شود
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

> اگر این دستور خطا داد، احتمالاً پروژه Supabase شما از نسخه قدیمی‌تر است. در آن صورت از **Connection Pooler** استفاده کنید یا از پشتیبانی Supabase بخواهید pgvector را فعال کنند.

---

## مرحله ۲ — دریافت Connection String

از داشبورد Supabase:

```
Settings → Database → Connection String
```

دو گزینه دارید:

### گزینه A: اتصال مستقیم (توصیه‌شده برای توسعه)

از بخش **Connection String → URI** کپی کنید. فرمت:

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

### گزینه B: Connection Pooler (توصیه‌شده برای پروداکشن / Serverless)

از بخش **Connection Pooler → Connection String → URI** کپی کنید:

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

> از Connection Pooler زمانی استفاده کنید که روی **Vercel، Cloudflare Workers، Railway، Render** یا هر محیط serverless مستقر می‌کنید. برای توسعه محلی، اتصال مستقیم (گزینه A) بهتر است.

---

## مرحله ۳ — به‌روزرسانی فایل `.env`

فایل `.env` موجود در ریشه پروژه را ویرایش کنید:

```bash
# پاک کردن تنظیمات قبلی SQLite
# DATABASE_URL=sqlite:///./kafil_music.db   ← این خط را کامنت یا حذف کنید

# اتصال مستقیم Supabase:
DATABASE_URL=postgresql://postgres.XXXXXXXXXXXX:YOUR_PASSWORD@db.XXXXXXXXXXXX.supabase.co:5432/postgres

# یا با Connection Pooler:
# DATABASE_URL=postgresql://postgres.XXXXXXXXXXXX:YOUR_PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
# USE_SUPABASE_POOLER=true
```

### نکات مهم:

- به جای `XXXXXX` مقادیر واقعی پروژه Supabase خود را بگذارید
- رمز عبور پایگاه‌داده: `Settings → Database → Database Password`
- مطمئن شوید که **هیچ فاصله‌ای** در URL وجود ندارد

---

## مرحله ۴ — نصب وابستگی‌ها

```bash
pip install psycopg2-binary
pip install pgvector       # برای پشتیبانی از vector type در Python
```

> `pgvector` فقط برای توسعه محلی لازم است. Supabase خودش pgvector را دارد.

اگر از macOS یا Linux استفاده می‌کنید و `psycopg2-binary` کار نکرد:

```bash
# macOS
brew install postgresql
pip install psycopg2

# Ubuntu/Debian
sudo apt install libpq-dev
pip install psycopg2
```

---

## مرحله ۵ — اجرای Migration

```bash
# اعمال schema روی Supabase
python -m alembic upgrade head
```

اگر خطای `permission denied` گرفتید، در Supabase Dashboard:

```
SQL Editor → New Query → اجرا کنید:
ALTER DATABASE postgres OWNER TO postgres;
```

یا در `Settings → Database → Replication` اطمینان حاصل کنید که کاربر `postgres` دسترسی کافی دارد.

---

## مرحله ۶ — راه‌اندازی سرور

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

برای بررسی اتصال:

```
GET /health
→ {"status": "ok"}
```

---

## عیب‌یابی

### خطای SSL Certificate

```
sslmode=require is not supported
```

**راه‌حل:** مطمئن شوید `pg` یا `psycopg2` به‌روز هستند:

```bash
pip install --upgrade psycopg2-binary pgvector
```

### خطای `operator does not exist: vector <=> vector`

```
پیام: operator does not exist: vector <=> vector
```

**راه‌حل:** افزونه `vector` در Supabase فعال نیست. در SQL Editor اجرا کنید:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### خطای `relation "users" does not exist`

**راه‌حل:** Migration هنوز اجرا نشده:

```bash
python -m alembic upgrade head
```

### خطای `permission denied for schema pgvector`

**راه‌حل:** در Supabase Dashboard → SQL Editor:

```sql
GRANT USAGE ON SCHEMA pg_catalog TO postgres;
GRANT ALL ON SCHEMA pg_vector TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA pg_vector GRANT ALL ON TABLES TO postgres;
```

### خطای `pgvector.psycopg2 not found`

```bash
pip install pgvector
```

---

## متداول

**آیا می‌توانم از Supabase Auth به جای سیستم OTP فعلی استفاده کنم؟**

بله، اما نیاز به یکپارچه‌سازی جداگانه دارد. سیستم OTP فعلی مستقل کار می‌کند و با Supabase Auth تداخلی ندارد.

**آیا با Supabase Edge Functions می‌توان ML Pipeline را اجرا کرد؟**

Edge Functions برای workloads کوتاه‌مدت (۵۰ms-۶۰s) طراحی شده‌اند. پایپلاین ML باید روی یک سرور مجزا یا از طریق یک endpoint API اجرا شود. می‌توانید `POST /api/recommendations/admin/pipeline/trigger` را از Supabase Edge Functions فراخوانی کنید.

**Connection Pooler چه تفاوتی با اتصال مستقیم دارد؟**

| ویژگی | اتصال مستقیم (5432) | Connection Pooler (6543) |
|---|---|---|
| تعداد کانکشن مجاز | ۶۰ | نامحدود |
| مناسب برای | توسعه محلی | Serverless / سرور |
| سرعت | کمی سریع‌تر | کمی کندتر |
| pgvector | ✅ همیشه | ⚠️ ممکن است نیاز به تنظیم داشته باشد |