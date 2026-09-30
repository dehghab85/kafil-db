"""
سرویس ذخیره‌سازی ابری — S3-compatible (ParsPack / AWS S3 / MinIO).

از boto3 برای ارتباط با Object Storage استفاده می‌شود. فایل‌ها با نام یکتا
(upload_<timestamp>_<uuid>) در پوشه‌های موضوعی آپلود می‌شوند:
  audio/   → فایل‌های صوتی (mp3, wav, flac, ogg, m4a, aac)
  cover/   → تصاویر کاور آلبوم/آهنگ (jpg, jpeg, png, webp, gif)
  misc/    → هر فایل دیگری که در دسته‌بندی بالا نباشد

هر متد یک URL عمومی (Public URL) برمی‌گرداند. اگر S3 فعال نباشد
(s3_enabled=False) یک خطای مناسب برمی‌گرداند.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings

settings = get_settings()


# ---- Allowed MIME types & extensions per category ----
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
AUDIO_MIME_TYPES = {
    "audio/mpeg",       # .mp3
    "audio/wav",        # .wav
    "audio/flac",      # .flac
    "audio/ogg",       # .ogg
    "audio/mp4",       # .m4a
    "audio/aac",       # .aac
    "audio/opus",      # .opus
    "audio/x-ms-wma",  # .wma
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/svg+xml",
}


@dataclass
class StorageResult:
    """نتیجه‌ی یک عملیات آپلود."""
    url: str          # URL عمومی فایل آپلود شده
    key: str          # کلید/مسیر فایل در باکت (مثلاً audio/abc123.mp3)
    size: int         # حجم فایل به بایت
    content_type: str # MIME type
    filename: str = ""  # نام اصلی فایلِ آپلودشده (برای نمایش/لاگ)


def _classify_file(filename: str, content_type: str, fallback_ext: str = "") -> str:
    """تعیین پوشه‌ی مقصد بر اساس پسوند فایل یا content-type."""
    ext = (PurePosixPath(filename).suffix or fallback_ext).lower()
    if ext in AUDIO_EXTENSIONS or content_type in AUDIO_MIME_TYPES:
        return "audio"
    if ext in IMAGE_EXTENSIONS or content_type in IMAGE_MIME_TYPES:
        return "cover"
    return "misc"


def _validate_file(
    file_content: bytes,
    filename: str,
    content_type: str,
    max_mb: int = 100,
) -> None:
    """اعتبارسنجی اولیه‌ی فایل: حجم و نوع محتوا."""
    size_mb = len(file_content) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"فایل بیش از حد بزرگ است: {size_mb:.1f}MB > {max_mb}MB"
        )

    # بررسی نوع با محتوای باینری
    if not content_type:
        return

    is_audio = (
        content_type in AUDIO_MIME_TYPES
        or PurePosixPath(filename).suffix.lower() in AUDIO_EXTENSIONS
    )
    is_image = (
        content_type in IMAGE_MIME_TYPES
        or PurePosixPath(filename).suffix.lower() in IMAGE_EXTENSIONS
    )

    if not is_audio and not is_image:
        # هشدار می‌دهیم ولی رد نمی‌کنیم (fallback به misc)
        pass


def _generate_key(prefix: str, original_filename: str) -> str:
    """ساخت کلید یکتا: prefix/uuid_timestamp.ext"""
    ext = PurePosixPath(original_filename).suffix or ""
    unique = f"upload_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
    return str(PurePosixPath(prefix, unique))


# ---------------------------------------------------------------------------
# ذخیره‌سازی محلی (static) — همان مسیری که FastAPI روی /static سرو می‌کند
# ---------------------------------------------------------------------------

#: پوشهٔ ریشهٔ فایل‌های استاتیک (در app/main.py روی «/static» mount شده است).
STATIC_DIR = Path("static")
#: پوشهٔ ریشهٔ فایل‌های آپلودیِ محلی — «ریشهٔ مجاز» برای حذف ایمن.
STATIC_UPLOAD_DIR = "uploads"
#: پیشوند URL عمومیِ فایل‌های استاتیک.
STATIC_URL_PREFIX = "/static"

_MIME_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
}


def _guess_extension(filename: str, content_type: str) -> str:
    """پسوند مناسب فایل را از نام اصلی یا MIME type حدس می‌زند."""
    ext = PurePosixPath(filename or "").suffix.lower()
    if ext in IMAGE_EXTENSIONS or ext in AUDIO_EXTENSIONS:
        return ext
    return _MIME_TO_EXTENSION.get((content_type or "").lower(), "")


def _static_relative_path(key_or_url: str, url_prefix: str = STATIC_URL_PREFIX) -> str:
    """مسیر نسبیِ یک فایل استاتیک را از URL عمومی یا کلید استخراج می‌کند."""
    candidate = (key_or_url or "").replace("\\", "/").lstrip("/")
    for prefix in (f"{STATIC_DIR.as_posix().strip('/')}/", f"{url_prefix.strip('/')}/"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    return candidate


def save_local_file(
    file_content: bytes,
    filename: str,
    *,
    folder: str = STATIC_UPLOAD_DIR,
    content_type: str = "",
    max_mb: int = 10,
    url_prefix: str = STATIC_URL_PREFIX,
) -> StorageResult:
    """
    ذخیرهٔ فایل روی فایل‌سیستم محلی و برگرداندن URL عمومیِ آن.

    نام فایل به «UUID» تبدیل می‌شود تا نام‌های تکراری/غیرمجاز (فارسی، فاصله‌دار،
    پیمایش مسیر) هرگز نوشته نشوند و آپلود مجدد، فایل قدیمی را بازنویسی نکند.

    مسیر نهایی: ``<STATIC_DIR>/<folder>/<uuid><ext>``
    URL نهایی:  ``<url_prefix>/<folder>/<uuid><ext>``
    """
    _validate_file(file_content, filename, content_type, max_mb=max_mb)

    ext = _guess_extension(filename, content_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    relative = PurePosixPath(folder, unique_name)

    target_dir = STATIC_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / relative).write_bytes(file_content)

    return StorageResult(
        url=f"{url_prefix.rstrip('/')}/{relative.as_posix()}",
        key=relative.as_posix(),
        size=len(file_content),
        content_type=content_type or "application/octet-stream",
        filename=filename,
    )


def delete_local_file(key_or_url: str, *, url_prefix: str = STATIC_URL_PREFIX) -> bool:
    """
    حذف فایلِ ذخیره‌شدهٔ محلی بر اساس URL عمومی یا مسیر نسبی.

    برای جلوگیری از حذف تصادفیِ سایر فایل‌های پروژه، فقط فایل‌های داخل
    ``<STATIC_DIR>/<STATIC_UPLOAD_DIR>`` حذف می‌شوند.
    """
    relative = _static_relative_path(key_or_url, url_prefix)
    if not relative:
        return False

    candidate = (STATIC_DIR / relative).resolve()
    uploads_root = (STATIC_DIR / STATIC_UPLOAD_DIR).resolve()
    if candidate == uploads_root or not candidate.is_relative_to(uploads_root):
        return False

    try:
        candidate.unlink()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# سرویس اصلی
# ---------------------------------------------------------------------------

def _get_client():
    """ساخت client با تنظیمات مناسب (path-style، region، SSL)."""
    if not settings.s3_enabled:
        raise RuntimeError(
            "S3 غیرفعال است. S3_ENABLED=true را در .env فعال کنید."
        )

    boto_config = BotoConfig(
        region_name=settings.s3_region or "us-east-1",
        signature_version="s3v4",
        s3={"addressing_style": "path" if settings.s3_path_style else "virtual"},
    )

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=boto_config,
    )
    return client


def upload_file(
    file_content: bytes,
    filename: str,
    content_type: str,
    *,
    max_mb: int = 100,
    acl: str = "public-read",
) -> StorageResult:
    """
    آپلود یک فایل به باکت S3 و برگرداندن URL عمومی.

    پارامترها:
        file_content: محتوای باینری فایل
        filename:    نام اصلی فایل (برای تعیین پسوند و پوشه)
        content_type: MIME type فایل (مثل audio/mpeg)
        max_mb:      حداکثر حجم مجاز (پیش‌فرض ۱۰۰MB)
        acl:         دسترسی ACL فایل (پیش‌فرض public-read)

    برمی‌گرداند:
        StorageResult شامل url، key، size و content_type

    خطاها:
        ValueError    — حجم فایل بیش از حد مجاز
        RuntimeError  — S3 غیرفعال است
        ClientError    — خطای boto3
    """
    _validate_file(file_content, filename, content_type, max_mb=max_mb)

    folder = _classify_file(filename, content_type)
    key = _generate_key(folder, filename)

    client = _get_client()

    extra_args = {"ContentType": content_type} if content_type else {}
    if acl:
        extra_args["ACL"] = acl

    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_content,
        **extra_args,
    )

    # ساخت URL عمومی
    if settings.s3_path_style:
        # path-style: https://endpoint/bucket/key
        public_url = f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket_name}/{key}"
    else:
        # virtual-hosted: https://bucket.endpoint/key
        # (برای پارس‌پک معمولاً path-style کار می‌کند)
        public_url = (
            f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket_name}/{key}"
        )

    return StorageResult(
        url=public_url,
        key=key,
        size=len(file_content),
        content_type=content_type or "application/octet-stream",
        filename=filename,
    )


def upload_audio(
    file_content: bytes,
    filename: str,
    content_type: str = "audio/mpeg",
    *,
    max_mb: int = 100,
) -> StorageResult:
    """آپلود فایل صوتی در پوشه‌ی audio/."""
    _validate_file(file_content, filename, content_type, max_mb=max_mb)
    folder = "audio"
    key = _generate_key(folder, filename)
    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_content,
        ContentType=content_type,
        ACL="public-read",
    )
    public_url = (
        f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket_name}/{key}"
    )
    return StorageResult(
        url=public_url,
        key=key,
        size=len(file_content),
        content_type=content_type,
        filename=filename,
    )


def upload_cover(
    file_content: bytes,
    filename: str,
    content_type: str = "image/jpeg",
    *,
    max_mb: int = 10,
) -> StorageResult:
    """آپلود تصویر کاور در پوشه‌ی cover/."""
    _validate_file(file_content, filename, content_type, max_mb=max_mb)
    original_filename = filename
    # پسوند نادرست را اصلاح کن (بعضی کلاینت‌ها content-type اشتباه می‌فرستند)
    actual_type = content_type
    if content_type.startswith("image/"):
        actual_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(content_type)
        if actual_ext and not filename.lower().endswith(actual_ext):
            stem = PurePosixPath(filename).stem
            filename = f"{stem}{actual_ext}"
            key = _generate_key("cover", filename)
        else:
            key = _generate_key("cover", filename)
    else:
        key = _generate_key("cover", filename)

    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_content,
        ContentType=actual_type,
        ACL="public-read",
    )
    public_url = (
        f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket_name}/{key}"
    )
    return StorageResult(
        url=public_url,
        key=key,
        size=len(file_content),
        content_type=actual_type,
        filename=original_filename,
    )


def delete_file(key_or_url: str) -> bool:
    """
    حذف یک فایل از باکت.

    ورودی می‌تواند «کلید» (مثل audio/upload_x.mp3) یا «URL عمومیِ کامل»
    (مثل https://endpoint/bucket/audio/upload_x.mp3) باشد؛ در هر دو حالت کلید
    استخراج و فایل حذف می‌شود. برای rollback اتمیک در endpointها لازم است.
    """
    key = _extract_key(key_or_url)
    if not key:
        return False
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
        return True
    except ClientError:
        return False


def _extract_key(key_or_url: str) -> str:
    """از یک URL عمومی، کلیدِ داخل باکت را بیرون می‌کشد؛ اگر خودش کلید باشد بی‌تغییر برمی‌گردد."""
    if not key_or_url:
        return ""
    if key_or_url.startswith("http://") or key_or_url.startswith("https://"):
        from urllib.parse import urlparse, unquote

        path = unquote(urlparse(key_or_url).path).lstrip("/")
        # path-style: bucket/key...  → کلید = هر چه بعد از «bucket/» است
        bucket_prefix = f"{settings.s3_bucket_name}/"
        if path.startswith(bucket_prefix):
            return path[len(bucket_prefix):]
        return path
    return key_or_url


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """ساخت URL دانلود با امضا (presigned URL) — برای فایل‌های private."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )


# ---------------------------------------------------------------------------
# انتخاب بک‌اند رسانه (محلی / ابری) — برای پنل ادمین
# ---------------------------------------------------------------------------

def resolve_media_backend() -> str:
    """
    بک‌اندِ ذخیره‌سازی فایل‌های رسانه‌ای پنل ادمین: ``local`` یا ``s3``.

    مقدار ``MEDIA_STORAGE_BACKEND`` در .env تصمیم می‌گیرد:
      - ``local`` → فایل‌ها در ``static/uploads`` ذخیره و روی ``/static`` سرو می‌شوند.
      - ``s3``    → فایل‌ها روی فضای ابری (ParsPack/S3) آپلود می‌شوند.
      - ``auto`` (پیش‌فرض) → اگر ``S3_ENABLED=true`` باشد S3، وگرنه محلی.
    """
    backend = (settings.media_storage_backend or "auto").strip().lower()
    if backend in {"local", "s3"}:
        return backend
    return "s3" if settings.s3_enabled else "local"


def store_media_image(
    file_content: bytes,
    filename: str,
    content_type: str = "image/jpeg",
    *,
    subfolder: str = STATIC_UPLOAD_DIR,
    max_mb: int = 10,
) -> StorageResult:
    """
    ذخیرهٔ یک تصویر رسانه‌ای (کاور مداح/پلی‌لیست/…) در بک‌اندِ فعال.

    خروجی همیشه یک URL عمومی است (نسبی برای حالت محلی، مطلق برای S3) که
    مستقیماً در ستون ``*_url`` ذخیره می‌شود.
    """
    if resolve_media_backend() == "s3":
        return upload_cover(file_content, filename, content_type, max_mb=max_mb)
    return save_local_file(
        file_content,
        filename,
        folder=subfolder,
        content_type=content_type,
        max_mb=max_mb,
    )


def store_media_audio(
    file_content: bytes,
    filename: str,
    content_type: str = "audio/mpeg",
    *,
    subfolder: str = STATIC_UPLOAD_DIR,
    max_mb: int = 100,
) -> StorageResult:
    """ذخیرهٔ فایل صوتی در بک‌اندِ فعال (محلی یا S3)."""
    if resolve_media_backend() == "s3":
        return upload_audio(file_content, filename, content_type, max_mb=max_mb)
    return save_local_file(
        file_content,
        filename,
        folder=subfolder,
        content_type=content_type,
        max_mb=max_mb,
    )


def delete_media_file(url_or_key: str) -> bool:
    """
    حذف فایل رسانه‌ای از بک‌اندی که در آن ذخیره شده است.

    ورودی می‌تواند URL محلی (``/static/uploads/...``)، URL کاملِ S3، یا کلید
    فایل باشد. برای rollback اتمیک هنگام خطا در پنل ادمین استفاده می‌شود.
    """
    if not url_or_key:
        return False
    if url_or_key.startswith(("http://", "https://")):
        return delete_file(url_or_key)
    return delete_local_file(url_or_key)