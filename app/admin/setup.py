"""
Admin panel setup — wires all ModelView classes and custom views together.
"""
from admin.auth import AdminAuth
from admin.views import (
    AlbumAdmin,
    ArtistAdmin,
    GenreAdmin,
    InteractionAdmin,
    PlaylistAdmin,
    TrackAdmin,
    UserAdmin,
)
from admin.custom_views import DashboardView, MLPipelineView, UserProfilerView
from app.db import engine
from sqladmin import Admin


def setup_admin(app):
    """Configure and mount the complete admin panel."""
    # Create admin with custom auth and dark theme
    admin = Admin(
        app,
        engine,
        title="کافیل موزیک — پنل مدیریت",
        logo_url="https://img.icons8.com/fluency/96/music.csv",
        favicon_url="https://img.icons8.com/fluency/96/music.csv",
        authentication_backend=AdminAuth(secret_key="kafil-ml-recommender-2024"),
        templates_dir="app/admin/templates",
    )

    # — Users section —
    admin.add_view(UserAdmin)

    # — Content section —
    admin.add_view(TrackAdmin)
    admin.add_view(ArtistAdmin)
    admin.add_view(AlbumAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(PlaylistAdmin)

    # — Analytics section —
    admin.add_view(InteractionAdmin)

    # — ML Pipeline section —
    admin.add_view(DashboardView)
    admin.add_view(MLPipelineView)
    admin.add_view(UserProfilerView)

    return admin
