"""
Endpoints آپلود و مدیریت فایل — فضای ابری ParsPack (S3-compatible).

POST /upload/audio        — آپلود فایل صوتی (mp3, wav, flac, ...)
POST /upload/cover        — آپلود تصویر کاور (jpg, png, webp, ...)
POST /upload/generic      — آپلود هر نوع فایلی (با محدودیت حجم)
DELETE /upload/{key}      — حذف فایل با کلید آن
"""
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import get_settings
from app.services.storage import (
    delete_file,
    generate_presigned_download_url,
    upload_audio,
    upload_cover,
    upload_file,
)

router = APIRouter(prefix="/upload", tags=["Storage"])
settings = get_settings()


# ---- Response schemas ----

class UploadResponse(BaseModel):
    """پاسخ موفق آپلود."""
    url: str
    key: str
    size: int
    content_type: str
    filename: str


class PresignedResponse(BaseModel):
    """پاسخ URL امضا شده برای دانلود."""
    url: str
    expires_in: int


class DeleteResponse(BaseModel):
    """پاسخ حذف فایل."""
    deleted: bool
    key: str


# ---- Error helper ----

def _require_storage_enabled():
    if not settings.s3_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "فضای ابری فعال نیست",
                "hint": "S3_ENABLED=true را در .env فعال کنید و S3_ENDPOINT_URL، "
                        "S3_BUCKET_NAME، S3_ACCESS_KEY و S3_SECRET_KEY را تنظیم کنید.",
            },
        )


# ---- Endpoints ----

@router.post(
    "/audio",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="آپلود فایل صوتی",
    description="آپلود فایل صوتی (mp3, wav, flac, ogg, m4a, aac, opus) به باکت S3. حداکثر حجم: ۱۰۰MB.",
)
async def upload_audio_endpoint(
    file: UploadFile = File(..., description="فایل صوتی"),
):
    """
    آپلود فایل صوتی.

    پاسخ شامل:
    - **url**: آدرس عمومی فایل (قابل پخش مستقیم)
    - **key**: کلید فایل در باکت (مثل audio/upload_...mp3)
    - **size**: حجم فایل به بایت
    - **content_type**: MIME type فایل
    """
    _require_storage_enabled()

    content = await file.read()

    result = upload_audio(
        file_content=content,
        filename=file.filename or "audio.mp3",
        content_type=file.content_type or "audio/mpeg",
    )

    return UploadResponse(
        url=result.url,
        key=result.key,
        size=result.size,
        content_type=result.content_type,
        filename=file.filename or "audio.mp3",
    )


@router.post(
    "/cover",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="آپلود تصویر کاور",
    description="آپلود تصویر کاور آلبوم/آهنگ (jpg, png, webp, gif) به باکت S3. حداکثر حجم: ۱۰MB.",
)
async def upload_cover_endpoint(
    file: UploadFile = File(..., description="تصویر کاور"),
):
    """
    آپلود تصویر کاور.

    پاسخ شامل:
    - **url**: آدرس عمومی تصویر (قابل نمایش مستقیم)
    - **key**: کلید فایل در باکت (مثل cover/upload_...jpg)
    - **size**: حجم فایل به بایت
    - **content_type**: MIME type تصویر
    """
    _require_storage_enabled()

    content = await file.read()

    result = upload_cover(
        file_content=content,
        filename=file.filename or "cover.jpg",
        content_type=file.content_type or "image/jpeg",
    )

    return UploadResponse(
        url=result.url,
        key=result.key,
        size=result.size,
        content_type=result.content_type,
        filename=file.filename or "cover.jpg",
    )


@router.post(
    "/generic",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="آپلود فایل عمومی",
    description="آپلود هر نوع فایلی (audio/image/other) — دسته‌بندی خودکار بر اساس پسوند و content-type. حداکثر حجم: ۱۰۰MB.",
)
async def upload_generic_endpoint(
    file: UploadFile = File(..., description="فایل دلخواه"),
    max_mb: int = 100,
):
    """
    آپلود عمومی فایل با تشخیص خودکار نوع محتوا.

    فایل‌ها به پوشه‌های موضوعی می‌روند:
    - audio/  (فایل‌های صوتی)
    - cover/  (تصاویر)
    - misc/   (بقیه)
    """
    _require_storage_enabled()

    content = await file.read()

    result = upload_file(
        file_content=content,
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        max_mb=max_mb,
    )

    return UploadResponse(
        url=result.url,
        key=result.key,
        size=result.size,
        content_type=result.content_type,
        filename=file.filename or "file",
    )


@router.get(
    "/presigned/{path:path}",
    response_model=PresignedResponse,
    summary="ساخت لینک دانلود امضا شده",
    description="یک URL امضا شده (presigned URL) برای دانلود فایل private تولید می‌کند. فقط برای فایل‌هایی که عمومی نیستند.",
)
def get_presigned_url(path: str, expires_in: int = 3600):
    """
    ساخت URL امضا شده برای دانلود (private files only).

    - **path**: کلید فایل در باکت (مثل audio/upload_abc123.mp3)
    - **expires_in**: مدت اعتبار لینک به ثانیه (پیش‌فرض: ۳۶۰۰ = ۱ ساعت)
    """
    _require_storage_enabled()

    url = generate_presigned_download_url(key=path, expires_in=expires_in)
    return PresignedResponse(url=url, expires_in=expires_in)


@router.delete(
    "/{key:path}",
    response_model=DeleteResponse,
    summary="حذف فایل",
    description="حذف یک فایل از باکت S3 با کلید آن.",
)
def delete_uploaded_file(key: str):
    """
    حذف فایل از فضای ابری.

    - **key**: کلید فایل در باکت (مثل audio/upload_abc123.mp3)
    """
    _require_storage_enabled()

    deleted = delete_file(key=key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "فایل پیدا نشد یا حذف نشد", "key": key},
        )

    return DeleteResponse(deleted=True, key=key)