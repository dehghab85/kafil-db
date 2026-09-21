"""
Alembic migration environment.

DB URL را از app.config می‌خواند تا با DATABASE_URL در .env سازگار باشد.

نکته‌ی مهم: آدرس دیتابیس را با config.set_main_option داخل alembic.ini
نمی‌گذاریم، چون configparser کاراکتر «%» را به‌عنوان interpolation تفسیر می‌کند
و رمزهای URL-encode شده (مثل %5B) خطای ValueError می‌دهند. در عوض مستقیماً از
engine ساخته‌شده در app.db استفاده می‌کنیم که connect_args درست (sslmode) و
ثبت pgvector مخصوص Supabase را هم به‌همراه دارد.
"""
from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.db import Base, engine

# Import all models so Alembic can detect them
from app.models import (
    Album,
    Artist,
    Genre,
    OTPCode,
    Playlist,
    Track,
    User,
    UserInteraction,
)

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output)."""
    # آدرس مستقیماً پاس داده می‌شود و از configparser عبور نمی‌کند.
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the app's configured engine."""
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
