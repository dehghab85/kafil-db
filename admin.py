"""
Kafil Music - پنل مدیریت (Admin Panel)
مبتنی بر SQLAdmin - مستقیم روی مدل‌های SQLAlchemy کار می‌کند.
پس از راه‌اندازی، پنل روی مسیر /admin در دسترس است.
"""
import os

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from database import engine, SessionLocal, User, Artist, Album, Genre, Song, Playlist, UserInteraction


# ---------------------------------------------------------------------------
# احراز هویت پنل - فقط کاربرانی که is_admin=True دارند اجازه ورود دارند
# ---------------------------------------------------------------------------
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and user.is_admin and user.check_password(password):
                request.session.update({"admin_user": user.username})
                return True
            return False
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "admin_user" in request.session


# ---------------------------------------------------------------------------
# تعریف صفحات پنل برای هر مدل
# ---------------------------------------------------------------------------

class ArtistAdmin(ModelView, model=Artist):
    column_list = [Artist.id, Artist.name, Artist.avatar_url]
    column_searchable_list = [Artist.name]
    name = "هنرمند"
    name_plural = "هنرمندان"
    icon = "fa-solid fa-microphone"


class AlbumAdmin(ModelView, model=Album):
    column_list = [Album.id, Album.title, Album.artist, Album.release_date]
    column_searchable_list = [Album.title]
    name = "آلبوم"
    name_plural = "آلبوم‌ها"
    icon = "fa-solid fa-compact-disc"


class GenreAdmin(ModelView, model=Genre):
    column_list = [Genre.id, Genre.name]
    column_searchable_list = [Genre.name]
    name = "ژانر"
    name_plural = "ژانرها"
    icon = "fa-solid fa-music"


class SongAdmin(ModelView, model=Song):
    column_list = [
        Song.id, Song.title, Song.artist, Song.album,
        Song.view_count, Song.like_count, Song.skip_count,
    ]
    column_searchable_list = [Song.title]
    column_sortable_list = [Song.view_count, Song.like_count, Song.release_date]
    form_excluded_columns = [Song.interactions, Song.favorited_by]
    name = "آهنگ"
    name_plural = "آهنگ‌ها"
    icon = "fa-solid fa-headphones"


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id, User.username, User.email, User.phone_number,
        User.is_admin, User.created_at,
    ]
    column_searchable_list = [User.username, User.email]
    # ساخت کاربر از پنل غیرفعال است چون پسورد باید حتما هش شود
    # (فرم پیش‌فرض پنل مقدار را مستقیم و بدون هش ذخیره می‌کند)
    can_create = False
    form_excluded_columns = [
        User.password_hash, User.favorite_songs,
        User.interactions, User.playlists,
    ]
    name = "کاربر"
    name_plural = "کاربران"
    icon = "fa-solid fa-user"


class PlaylistAdmin(ModelView, model=Playlist):
    column_list = [
        Playlist.id, Playlist.name, Playlist.owner,
        Playlist.is_private, Playlist.is_auto_generated,
    ]
    name = "پلی‌لیست"
    name_plural = "پلی‌لیست‌ها"
    icon = "fa-solid fa-list"


class InteractionAdmin(ModelView, model=UserInteraction):
    column_list = [
        UserInteraction.id, UserInteraction.user, UserInteraction.song,
        UserInteraction.interaction_type, UserInteraction.timestamp,
    ]
    column_sortable_list = [UserInteraction.timestamp]
    # این داده‌ها فقط باید از طریق اپ ثبت شوند، نه دستی از پنل
    can_create = False
    can_edit = False
    name = "تعامل کاربر"
    name_plural = "تعاملات کاربران"
    icon = "fa-solid fa-chart-line"


def setup_admin(app: FastAPI) -> Admin:
    """پنل ادمین را به اپلیکیشن FastAPI متصل می‌کند"""
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY تنظیم نشده - برای امنیت پنل ادمین لازم است")

    authentication_backend = AdminAuth(secret_key=secret_key)

    admin = Admin(
        app,
        engine,
        authentication_backend=authentication_backend,
        title="پنل مدیریت کافیل موزیک",
    )

    admin.add_view(ArtistAdmin)
    admin.add_view(AlbumAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(SongAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(PlaylistAdmin)
    admin.add_view(InteractionAdmin)

    return admin
