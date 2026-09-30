"""
Admin panel setup — wires all ModelView classes and custom views together.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from sqladmin import Admin
from starlette.datastructures import FormData, UploadFile
from starlette.requests import Request

from app.admin.auth import AdminAuth
from app.admin.custom_views import BulkUploadView, DashboardView, MLPipelineView, UserProfilerView
from app.admin.views import (
    AlbumAdmin,
    ArtistAdmin,
    GenreAdmin,
    InteractionAdmin,
    PlaylistAdmin,
    SongAdmin,
    TrackAdmin,
    UserAdmin,
)
from app.config import get_settings
from app.db import SessionLocal, engine


class KafilAdmin(Admin):
    """
    SQLAdmin subclass that safely handles FileField on URL/string columns.

    Stock SQLAdmin assumes file columns are local FileType objects with
    ``.name`` / ``.open()``. Our audio_url/cover_url store public CDN URLs,
    so empty uploads on edit must not try to re-open the existing value.
    """

    async def _handle_form_data(self, request: Request, obj: Any = None) -> FormData:
        """Parse multipart form, handling empty file uploads vs. existing URL strings."""
        form = await request.form()
        form_data: list[tuple[str, str | UploadFile]] = []

        # Build a quick lookup set: {key for (key, value) in multi_items()}
        form_keys = {k for k, _ in form.multi_items()}

        for key, value in form.multi_items():
            if not isinstance(value, UploadFile):
                form_data.append((key, value))
                continue

            should_clear = key + "_checkbox" in form_keys
            empty_upload = len(await value.read(1)) != 1
            await value.seek(0)

            if should_clear:
                form_data.append((key, UploadFile(io.BytesIO(b""))))
                continue

            if empty_upload and obj is not None:
                existing = getattr(obj, key, None)
                # Only re-bind real local storage files (fastapi-storages style)
                if (
                    existing is not None
                    and hasattr(existing, "open")
                    and hasattr(existing, "name")
                ):
                    form_data.append(
                        (key, UploadFile(filename=existing.name, file=existing.open()))
                    )
                else:
                    # URL string / missing attr — keep empty upload; view keeps old URL
                    form_data.append((key, value))
                continue

            form_data.append((key, value))

        return FormData(form_data)


def setup_admin(app):
    """Configure and mount the complete admin panel."""
    settings = get_settings()
    admin = KafilAdmin(
        app,
        engine,
        session_maker=SessionLocal,
        title="کافیل موزیک — پنل مدیریت",
        logo_url="https://img.icons8.com/fluency/96/music.csv",
        favicon_url="https://img.icons8.com/fluency/96/music.csv",
        # Must match SessionMiddleware's secret key to keep the admin session valid.
        authentication_backend=AdminAuth(secret_key=settings.jwt_secret_key),
        templates_dir=str(Path(__file__).parent / "templates"),
    )

    # — Users section —
    admin.add_view(UserAdmin)

    # — Content section —
    admin.add_view(TrackAdmin)
    admin.add_view(ArtistAdmin)
    admin.add_view(AlbumAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(PlaylistAdmin)

    # — Songs section (پلتفرم نوحه) —
    admin.add_view(SongAdmin)

    # — Analytics section —
    admin.add_view(InteractionAdmin)

    # — ML Pipeline section —
    admin.add_view(DashboardView)
    admin.add_view(MLPipelineView)
    admin.add_view(UserProfilerView)

    # — Upload section —
    admin.add_view(BulkUploadView)

    return admin
