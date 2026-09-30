"""
پیکربندی متمرکز برنامه (Application settings).

تمام تنظیمات از متغیرهای محیطی / فایل .env خوانده می‌شوند تا هیچ مقدار حساسی
در کد هاردکد نشود. از pydantic-settings برای اعتبارسنجی و type-safety استفاده شده.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    # ---- Security / Auth ----
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_hours: int = 24
    otp_expiry_minutes: int = Field(5, alias="OTP_EXPIRY_MINUTES")
    otp_length: int = 6

    # ---- Database ----
    database_url: str = Field("sqlite:///./kafil_music.db", alias="DATABASE_URL")
    # Supabase: direct connection (uses port 5432, bypasses pooler)
    # Use the "Connection URI" from Supabase Dashboard → Settings → Database
    # Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
    use_supabase_pooler: bool = Field(False, alias="USE_SUPABASE_POOLER")
    # Supabase connection pooler (port 6543) — enables connection pooling
    # Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

    # ---- Recommender ----
    content_dim: int = Field(48, alias="RECO_CONTENT_DIM")
    cf_dim: int = Field(32, alias="RECO_CF_DIM")
    w_collab: float = Field(0.5, alias="RECO_W_COLLAB")
    w_content: float = Field(0.35, alias="RECO_W_CONTENT")
    w_popularity: float = Field(0.15, alias="RECO_W_POPULARITY")
    realtime_lr: float = Field(0.15, alias="RECO_REALTIME_LR")
    candidate_pool: int = Field(400, alias="RECO_CANDIDATE_POOL")
    cf_backend: str = Field("numpy", alias="RECO_CF_BACKEND")
    ann_backend: str = Field("numpy", alias="RECO_ANN_BACKEND")
    artifact_dir: str = Field("./artifacts", alias="RECO_ARTIFACT_DIR")
    half_life_days: float = 30.0

    # ---- CORS ----
    cors_origins: str = Field("*", alias="CORS_ORIGINS")

    # ---- Cloud Storage (S3-compatible, e.g. ParsPack) ----
    # فعال‌سازی: S3_ENABLED=true در .env
    s3_enabled: bool = Field(False, alias="S3_ENABLED")
    # آدرس endpoint — برای پارس‌پک معمولاً: https://c872409.parspack.net
    # برای AWS S3: https://s3.<region>.amazonaws.com
    # برای MinIO محلی: http://localhost:9000
    s3_endpoint_url: str = Field("https://s3.amazonaws.com", alias="S3_ENDPOINT_URL")
    # نام باکت (باکت باید از قبل در پنل پارس‌پک ساخته شده باشد)
    s3_bucket_name: str = Field("", alias="S3_BUCKET_NAME")
    # کلید دسترسی و کلید مخفی — از پنل پارس‌پک / AWS
    s3_access_key: str = Field("", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field("", alias="S3_SECRET_KEY")
    # ناحیه (region) — برای AWS مهم است؛ برای پارس‌پک معمولاً خالی یا یک ناحیه‌ی پیش‌فرض
    s3_region: str = Field("us-east-1", alias="S3_REGION")
    # آیا از path-style (/) به‌جای virtual-hosted-style استفاده شود (برای پارس‌پک لازم است)
    s3_path_style: bool = Field(True, alias="S3_PATH_STYLE")

    # ---- Media storage for the admin panel ----
    # backend: local | s3 | auto
    #   local → فایل‌ها در static/uploads ذخیره و روی /static سرو می‌شوند
    #   s3    → فایل‌ها روی فضای ابری (ParsPack/S3) آپلود می‌شوند
    #   auto  → اگر S3_ENABLED=true باشد S3، وگرنه محلی
    media_storage_backend: str = Field("auto", alias="MEDIA_STORAGE_BACKEND")
    # حداکثر حجم مجاز آپلود کاور از پنل ادمین (مگابایت)
    media_image_max_mb: int = Field(10, alias="MEDIA_IMAGE_MAX_MB")
    # حداکثر حجم مجاز آپلود فایل صوتی از پنل ادمین (مگابایت)
    media_audio_max_mb: int = Field(100, alias="MEDIA_AUDIO_MAX_MB")

    # ---- Derived helpers ----
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings را فقط یک‌بار می‌سازد و کش می‌کند (singleton)."""
    return Settings()
