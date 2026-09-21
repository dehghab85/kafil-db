# فضای ابری ParsPack — راه‌اندازی و استفاده

این راهنما نحوه‌ی اتصال فضای ابری **پارس‌پک** (Object Storage سازگار با S3) به بک‌اند Kafil Music را توضیح می‌دهد. برای آپلود فایل‌های صوتی و تصاویر کاور استفاده می‌شود.

---

## ۱. نصب وابستگی

```bash
pip install boto3
# یا کل وابستگی‌ها:
pip install -r requirements.txt
```

---

## ۲. تنظیمات `.env`

مقادیر زیر در فایل `.env` تنظیم شده‌اند:

```bash
S3_ENABLED=true
S3_ENDPOINT_URL=https://c872409.parspack.net
S3_ACCESS_KEY=EQVoggvaxbqX2ThK
S3_SECRET_KEY=6L54bvyltU0rsE8XV2Y75FoJSBylAxK1
S3_BUCKET_NAME=kafil-music
S3_REGION=us-east-1
S3_PATH_STYLE=true
```

> **مهم:** مقدار `S3_BUCKET_NAME` باید نامِ یک باکت باشد که **از قبل در پنل پارس‌پک ساخته‌اید**. مقدار پیش‌فرض `kafil-music` است؛ اگر نام باکت شما فرق دارد، همین‌جا اصلاحش کنید.

---

## ۳. ساخت باکت در پنل پارس‌پک

۱. وارد پنل پارس‌پک شوید → بخش **Object Storage**.
۲. یک باکت جدید بسازید (مثلاً `kafil-music`).
۳. برای اینکه فایل‌ها با URL عمومی قابل دسترسی باشند، سطح دسترسی باکت را روی **Public** بگذارید (یا در ACL هر آبجکت `public-read` که کد به‌صورت خودکار ست می‌کند).

---

## ۴. تست اتصال

قبل از استفاده، اتصال را تست کنید:

```bash
python scripts/test_parspack.py
```

این اسکریپت به‌ترتیب: وجود باکت، آپلود، دانلود، URL عمومی و حذف را بررسی می‌کند. اگر همه‌ی مراحل ✓ شدند، آماده‌اید.

---

## ۵. Endpointهای API

پس از اجرای سرور (`uvicorn app.main:app --reload`)، این مسیرها در `/docs` در دسترس‌اند:

| متد | مسیر | کاربرد | حداکثر حجم |
|---|---|---|---|
| POST | `/upload/audio` | آپلود فایل صوتی | ۱۰۰MB |
| POST | `/upload/cover` | آپلود تصویر کاور | ۱۰MB |
| POST | `/upload/generic` | آپلود فایل دلخواه (دسته‌بندی خودکار) | ۱۰۰MB |
| GET | `/upload/presigned/{key}` | لینک دانلود امضاشده (private) | — |
| DELETE | `/upload/{key}` | حذف فایل | — |

### نمونه با `curl`

```bash
# آپلود آهنگ
curl -X POST http://localhost:8000/upload/audio \
  -F "file=@song.mp3"

# پاسخ:
# {
#   "url": "https://c872409.parspack.net/kafil-music/audio/upload_1737000000_ab12cd34.mp3",
#   "key": "audio/upload_1737000000_ab12cd34.mp3",
#   "size": 4823012,
#   "content_type": "audio/mpeg",
#   "filename": "song.mp3"
# }
```

### نمونه با پایتون (requests)

```python
import requests

with open("cover.jpg", "rb") as f:
    r = requests.post(
        "http://localhost:8000/upload/cover",
        files={"file": ("cover.jpg", f, "image/jpeg")},
    )
print(r.json()["url"])   # URL عمومی تصویر
```

---

## ۶. اتصال به ثبت آهنگ

`url` برگشتی از آپلود را در فیلد `audio_url` یا `cover_url` هنگام ساخت آهنگ قرار دهید:

```python
# ۱) اول فایل را آپلود کن
audio = requests.post(".../upload/audio", files={"file": ...}).json()
cover = requests.post(".../upload/cover", files={"file": ...}).json()

# ۲) بعد آهنگ را با URLها بساز
requests.post(".../tracks", json={
    "title": "آهنگ من",
    "artist_id": 1,
    "audio_url": audio["url"],
    "cover_url": cover["url"],
    "duration_sec": 210,
})
```

---

## معماری کد

- **`app/config.py`** — تنظیمات `S3_*` (خوانده‌شده از `.env`)
- **`app/services/storage.py`** — سرویس اصلی (boto3): `upload_audio`، `upload_cover`، `upload_file`، `delete_file`، `generate_presigned_download_url`
- **`app/api/routers/storage.py`** — endpointهای `/upload/*`
- **`scripts/test_parspack.py`** — تست اتصال end-to-end

فایل‌ها با نام یکتا (`upload_<timestamp>_<uuid>.<ext>`) در پوشه‌های `audio/`، `cover/` یا `misc/` باکت ذخیره می‌شوند.

---

## عیب‌یابی

| خطا | علت | راه‌حل |
|---|---|---|
| `503 فضای ابری فعال نیست` | `S3_ENABLED` روشن نیست | در `.env` مقدار `S3_ENABLED=true` بگذارید |
| `NoSuchBucket` / باکت پیدا نشد | باکت ساخته نشده | باکت را در پنل پارس‌پک بسازید |
| `SignatureDoesNotMatch` / `403` | کلید اشتباه یا path-style غلط | Access/Secret Key و `S3_PATH_STYLE=true` را بررسی کنید |
| `ConnectionError` | endpoint اشتباه | `S3_ENDPOINT_URL` را با `https://` بررسی کنید |
| فایل آپلود می‌شود ولی URL باز نمی‌شود | باکت Public نیست | سطح دسترسی باکت را Public کنید |
