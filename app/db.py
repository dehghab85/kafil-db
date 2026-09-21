"""
لایه اتصال به دیتابیس: engine، session factory و Base مشترک.

- در حالت توسعه با SQLite کار می‌کند (بدون نیاز به نصب چیزی).
- در پروداکشن با PostgreSQL + pgvector؛ افزونه‌ی برداری در migration فعال می‌شود.
- با Supabase: نیاز به SSL و تنظیمات pooler دارد.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# --- Engine configuration ---

if settings.is_sqlite:
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

elif "supabase" in settings.database_url.lower() or "pooler.supabase" in settings.database_url.lower():
    # Supabase: SSL required, pool settings tuned for the Supavisor pooler.
    # NOTE: use the IPv4 session-mode pooler host (aws-0-<region>.pooler.supabase.com:5432)
    # with username postgres.<PROJECT_REF>. The direct host db.<REF>.supabase.co is IPv6-only.
    connect_args = {
        "sslmode": "require",
    }
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=5,          # Fewer connections to respect pooler limits
        max_overflow=2,
        pool_recycle=300,    # Recycle connections before pgbouncer times out
        future=True,
    )

    # pgvector registration for Supabase
    @event.listens_for(engine, "connect")
    def _register_pgvector_supabase(dbapi_connection, _connection_record):  # pragma: no cover
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(dbapi_connection)
        except ImportError:
            # pgvector not installed — Supabase has it built-in, just needs the adapter
            pass
        except Exception:
            # Vector type not available yet (extension not created)
            pass

else:
    # Standard PostgreSQL (self-hosted, Railway, Render, etc.)
    connect_args = {"sslmode": "prefer"}
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _register_pgvector_postgres(dbapi_connection, _connection_record):  # pragma: no cover
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(dbapi_connection)
        except Exception:
            pass


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base مشترک تمام مدل‌های ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependency استاندارد FastAPI برای تزریق session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()