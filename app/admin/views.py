"""
SQLAdmin model views — comprehensive CRUD with search, filters, and relationships.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from markupsafe import Markup, escape
from sqladmin import ModelView
from sqladmin.fields import FileField
from starlette.datastructures import UploadFile
from starlette.requests import Request

from app.config import get_settings
from app.models import (
    Album,
    Artist,
    Genre,
    Playlist,
    Song,
    Track,
    User,
    UserInteraction,
)
from app.services.storage import (
    STATIC_UPLOAD_DIR,
    delete_media_file,
    store_media_audio,
    store_media_image,
)

settings = get_settings()

#: پوشهٔ آپلود تصاویر مداح (نسبی به static/) — «کاور مداح».
ARTIST_UPLOAD_FOLDER = PurePosixPath(STATIC_UPLOAD_DIR, "artists").as_posix()
#: پوشهٔ آپلود فایل‌های نوحه (صوت/کاور).
SONG_UPLOAD_FOLDER = PurePosixPath(STATIC_UPLOAD_DIR, "songs").as_posix()

_IMAGE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp"
_AUDIO_ACCEPT = "audio/mpeg,audio/*,.mp3,.wav,.flac,.ogg,.m4a,.aac"


def _is_uploaded_file(value: Any) -> bool:
    """True when the form value is a real (non-empty) multipart upload."""
    if not isinstance(value, UploadFile):
        return False
    filename = (value.filename or "").strip()
    return bool(filename)


async def _read_upload(upload: UploadFile) -> bytes:
    await upload.seek(0)
    return await upload.read()


def _image_column_formatter(prop: str) -> Any:
    """
    سازندهٔ formatter ستون تصویر برای نمای لیست.

    یک تصویر بندانگشتیِ کلیک‌پذیر می‌سازد و اگر مقدار ستون خالی باشد،
    یک «—» کم‌رنگ نشان می‌دهد (به‌جای سلول خالی).
    """

    def formatter(model: Any, attribute: str, request: Request | None = None) -> Markup:
        url = getattr(model, prop, None)
        if not url or not isinstance(url, str):
            return Markup('<span class="text-muted">—</span>')
        escaped = escape(url)
        return Markup(
            '<a href="{url}" target="_blank" rel="noopener noreferrer">'
            '<img src="{url}" alt="{alt}" loading="lazy" '
            'style="height:48px;width:48px;object-fit:cover;'
            'border-radius:6px;border:1px solid rgba(127,127,127,.35);" />'
            "</a>"
        ).format(url=escaped, alt=escape(getattr(model, "name", "") or prop))

    return formatter


# ==================== User Management ====================

class UserAdmin(ModelView, model=User):
    """User management with search and filters."""
    
    name = "کاربر"
    name_plural = "کاربران"
    icon = "fa-solid fa-user"
    
    # List view
    column_list = [
        User.id,
        User.username,
        User.email,
        User.phone_number,
        User.is_admin,
        User.is_phone_verified,
        User.created_at,
    ]
    
    # Searchable fields
    column_searchable_list = ["username", "email", "phone_number"]

    # Sortable columns
    column_sortable_list = ["id", "username", "is_active"]

    # Filters
    column_filters = []
    
    # Detail view
    column_details_list = [
        User.id,
        User.username,
        User.email,
        User.phone_number,
        User.is_admin,
        User.is_phone_verified,
        User.created_at,
        User.preferred_genre_ids,
        User.preferred_artist_ids,
    ]
    
    # Form configuration
    form_columns = [
        User.username,
        User.email,
        User.phone_number,
        User.is_admin,
        User.is_phone_verified,
    ]

    # Read-only fields
    form_readonly_columns = [User.created_at]
    
    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]
    
    # Custom labels
    column_labels = {
        User.username: "نام کاربری",
        User.email: "ایمیل",
        User.phone_number: "شماره موبایل",
        User.is_admin: "ادمین",
        User.is_phone_verified: "شماره تأیید شده",
        User.created_at: "تاریخ ثبت‌نام",
    }


# ==================== Content Management ====================

class ArtistAdmin(ModelView, model=Artist):
    """
    Artist (مداح) management with search and cover upload.

    فایل کاور مستقیماً از فرم پنل ادمین آپلود می‌شود:
      - نام فایل با UUID جایگزین می‌شود و در ``static/uploads/artists``
        (یا فضای ابری، بسته به MEDIA_STORAGE_BACKEND) ذخیره می‌گردد؛
      - URL عمومی در ستون ``Artist.cover_url`` نگهداری می‌شود.
    """

    name = "هنرمند"
    name_plural = "هنرمندان"
    icon = "fa-solid fa-microphone"

    column_list = [
        Artist.id,
        Artist.cover_url,
        Artist.name,
        Artist.avatar_url,
        Artist.created_at,
    ]
    column_searchable_list = ["name"]
    column_sortable_list = ["id", "name", "created_at"]

    column_details_list = [
        Artist.id,
        Artist.name,
        Artist.cover_url,
        Artist.bio,
        Artist.avatar_url,
        Artist.created_at,
    ]

    form_columns = [
        Artist.name,
        Artist.bio,
        Artist.cover_url,
        Artist.avatar_url,
    ]

    # فیلدهای آپلود فایل به‌جای ورودی متنیِ URL
    form_overrides = {
        "cover_url": FileField,
        "avatar_url": FileField,
    }

    form_args = {
        "cover_url": {
            "label": "کاور/تصویر مداح",
            "validators": [],
            "render_kw": {"accept": _IMAGE_ACCEPT},
        },
        "avatar_url": {
            "label": "تصویر پروفایل (قدیمی)",
            "validators": [],
            "render_kw": {"accept": _IMAGE_ACCEPT},
        },
    }

    # نمایش بندانگشتی در نمای لیست و جزئیات
    column_formatters = {
        Artist.cover_url: _image_column_formatter("cover_url"),
        Artist.avatar_url: _image_column_formatter("avatar_url"),
    }
    column_formatters_detail = {
        Artist.cover_url: _image_column_formatter("cover_url"),
        Artist.avatar_url: _image_column_formatter("avatar_url"),
    }

    create_template = "admin/media_form.html"
    edit_template = "admin/media_form.html"

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_labels = {
        Artist.id: "شناسه",
        Artist.name: "نام هنرمند",
        Artist.bio: "بیوگرافی",
        Artist.cover_url: "کاور",
        Artist.avatar_url: "تصویر پروفایل",
        Artist.created_at: "تاریخ ایجاد",
    }

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """
        آپلود فایل‌های انتخابیِ فرم و تبدیل توکن «پاک‌کردن» به ``None``.

        اگر کاربر تصویرِ جدیدی انتخاب نکند، مقدار فعلیِ ستون دست‌نخورده می‌ماند
        (کلید از ``data`` حذف می‌شود تا SQLAdmin روی مدل مقداردهی نکند).
        در صورت خطا در هر مرحله، فایل‌های آپلودشدهٔ همان درخواست حذف می‌شوند
        (rollback اتمیک) و خطا دوباره raise می‌شود تا تراکنش commit نشود.
        """
        uploaded_keys: list[str] = []
        form_data = await request.form()

        def _clear_requested(column: str) -> bool:
            """آیا چک‌باکس «حذف تصویر فعلی» برای این ستون تیک خورده است؟"""
            return any(
                key in {f"{column}_checkbox", f"{column}_clear"}
                for key, _ in form_data.multi_items()
            )

        try:
            for column in ("cover_url", "avatar_url"):
                value = data.get(column)

                if _clear_requested(column):
                    data[column] = None
                    continue

                if _is_uploaded_file(value):
                    content = await _read_upload(value)
                    if not content:
                        raise ValueError("فایل تصویر خالی است.")
                    result = store_media_image(
                        file_content=content,
                        filename=value.filename or "cover.jpg",
                        content_type=value.content_type or "image/jpeg",
                        subfolder=ARTIST_UPLOAD_FOLDER,
                        max_mb=settings.media_image_max_mb,
                    )
                    uploaded_keys.append(result.key)
                    data[column] = result.url
                else:
                    # بدون فایل جدید → مقدار فعلیِ ستون حفظ شود.
                    data.pop(column, None)
        except Exception:
            for key in uploaded_keys:
                try:
                    delete_media_file(key)
                except Exception:
                    pass
            raise
        finally:
            for _, value in form_data.multi_items():
                if isinstance(value, UploadFile):
                    try:
                        await value.close()
                    except Exception:
                        pass


class AlbumAdmin(ModelView, model=Album):
    """Album management with artist relationship."""
    
    name = "آلبوم"
    name_plural = "آلبوم‌ها"
    icon = "fa-solid fa-compact-disc"
    
    column_list = [Album.id, Album.title, Album.artist, Album.release_date, Album.cover_url]
    column_searchable_list = ["title"]
    column_sortable_list = ["id", "title", "release_date"]
    column_filters = []
    
    form_columns = [
        Album.title,
        Album.artist,  # Relationship (select dropdown)
        Album.release_date,
        Album.cover_url,
    ]
    
    page_size = 50
    
    column_labels = {
        Album.title: "عنوان آلبوم",
        Album.artist: "هنرمند",
        Album.release_date: "تاریخ انتشار",
        Album.cover_url: "کاور",
    }


class GenreAdmin(ModelView, model=Genre):
    """Genre management."""
    
    name = "ژانر"
    name_plural = "ژانرها"
    icon = "fa-solid fa-music"
    
    column_list = [Genre.id, Genre.name]
    column_searchable_list = ["name"]
    column_sortable_list = ["id", "name"]
    
    form_columns = [Genre.name]
    
    page_size = 100
    
    column_labels = {Genre.name: "نام ژانر"}


class TrackAdmin(ModelView, model=Track):
    """
    Track management with local file upload → cloud storage (S3/ParsPack).
    """

    name = "آهنگ"
    name_plural = "آهنگ‌ها"
    icon = "fa-solid fa-headphones"

    # List view
    column_list = [
        Track.id,
        Track.title,
        Track.artist,
        Track.album,
        Track.duration_sec,
        Track.view_count,
        Track.like_count,
        Track.skip_count,
    ]

    # Search
    column_searchable_list = ["title"]

    # Sort
    column_sortable_list = [
        "id",
        "title",
        "artist_id",
        "view_count",
        "like_count",
        "release_date",
    ]

    # Filters
    column_filters = []

    # Detail view
    column_details_list = [
        Track.id,
        Track.title,
        Track.artist,
        Track.album,
        Track.audio_url,
        Track.cover_url,
        Track.duration_sec,
        Track.release_date,
        Track.lyrics,
        Track.view_count,
        Track.like_count,
        Track.skip_count,
    ]

    # Form — file pickers instead of raw URL text inputs
    form_columns = [
        Track.title,
        Track.artist,
        Track.album,
        Track.genres,
        Track.audio_url,
        Track.cover_url,
        Track.duration_sec,
        Track.release_date,
        Track.lyrics,
        Track.lyrics_timestamps,
    ]

    form_overrides = {
        "audio_url": FileField,
        "cover_url": FileField,
    }

    form_args = {
        "audio_url": {
            "label": "فایل صوتی",
            "validators": [],
            "render_kw": {
                "accept": "audio/mpeg,audio/*,.mp3,.wav,.flac,.ogg,.m4a,.aac",
                "class": "form-control-file",
            },
        },
        "cover_url": {
            "label": "کاور",
            "validators": [],
            "render_kw": {
                "accept": "image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp",
                "class": "form-control-file",
            },
        },
    }

    # Custom template with styled file picker + current-file preview
    create_template = "admin/media_form.html"
    edit_template = "admin/media_form.html"

    form_readonly_columns = []

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_labels = {
        Track.title: "عنوان",
        Track.artist: "هنرمند",
        Track.album: "آلبوم",
        Track.genres: "ژانرها",
        Track.audio_url: "فایل صوتی",
        Track.cover_url: "کاور",
        Track.duration_sec: "مدت (ثانیه)",
        Track.release_date: "تاریخ انتشار",
        Track.lyrics: "متن شعر",
        Track.view_count: "تعداد پخش",
        Track.like_count: "تعداد لایک",
        Track.skip_count: "تعداد اسکیپ",
    }

    # نمایش بندانگشتی کاور در نمای لیست
    column_formatters = {Track.cover_url: _image_column_formatter("cover_url")}
    column_formatters_detail = {Track.cover_url: _image_column_formatter("cover_url")}

    async def scaffold_form(self, rules: list[str] | None = None):
        """Replace URL text inputs with file pickers; require file only in on_model_change."""
        form_cls = await super().scaffold_form(rules)

        class TrackUploadForm(form_cls):
            audio_url = FileField(
                label="فایل صوتی",
                validators=[],
                render_kw={
                    "accept": "audio/mpeg,audio/*,.mp3,.wav,.flac,.ogg,.m4a,.aac",
                },
            )
            cover_url = FileField(
                label="کاور",
                validators=[],
                render_kw={
                    "accept": (
                        "image/jpeg,image/png,image/webp,image/gif,"
                        ".jpg,.jpeg,.png,.webp"
                    ),
                },
            )

        return TrackUploadForm

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """آپلود فایل‌های انتخابی (صوت/کاور) و ذخیرهٔ URL عمومی در ستون‌ها.

        Rollback: اگر هر آپلودی خطا بدهد، همهٔ فایل‌های آپلودشدهٔ همین درخواست
        (به‌صورت best-effort) حذف می‌شوند و خطا دوباره raise می‌شود تا تراکنش
        دیتابیس با فایل‌های یتیم commit نشود.
        """
        uploaded_keys: list[str] = []
        form_data: Any = None

        try:
            # Parse multipart form once; reused for checkbox detection below.
            form_data = await request.form()
            audio_value = data.get("audio_url")
            cover_value = data.get("cover_url")

            # ---- Audio file upload ----
            if _is_uploaded_file(audio_value):
                content = await _read_upload(audio_value)
                if not content:
                    raise ValueError("فایل صوتی خالی است.")
                result = store_media_audio(
                    file_content=content,
                    filename=audio_value.filename or "audio.mp3",
                    content_type=audio_value.content_type or "audio/mpeg",
                    subfolder=SONG_UPLOAD_FOLDER,
                    max_mb=settings.media_audio_max_mb,
                )
                uploaded_keys.append(result.key)
                data["audio_url"] = result.url
            elif is_created:
                raise ValueError("انتخاب فایل صوتی الزامی است.")
            else:
                # Edit mode without a new file — keep existing URL by removing
                # the empty UploadFile placeholder so SQLAdmin does not overwrite
                # the current audio_url value on the model instance.
                data.pop("audio_url", None)

            # ---- Cover file upload ----
            # Check if user ticked "clear cover" checkbox
            clear_cover = bool(form_data) and any(
                k in {"cover_url_checkbox", "cover_url_clear"}
                for k, _ in form_data.multi_items()
            )

            if clear_cover:
                # Explicitly clear cover — set to None so the column is NULL'd.
                data["cover_url"] = None
            elif _is_uploaded_file(cover_value):
                content = await _read_upload(cover_value)
                if content:
                    result = store_media_image(
                        file_content=content,
                        filename=cover_value.filename or "cover.jpg",
                        content_type=cover_value.content_type or "image/jpeg",
                        subfolder=SONG_UPLOAD_FOLDER,
                        max_mb=settings.media_image_max_mb,
                    )
                    uploaded_keys.append(result.key)
                    data["cover_url"] = result.url
            else:
                # No new cover uploaded — keep existing (or leave null on create).
                data.pop("cover_url", None)

            # Safety: never let UploadFile objects reach SQLAlchemy
            for key in ("audio_url", "cover_url"):
                if isinstance(data.get(key), UploadFile):
                    data.pop(key, None)

        except Exception:
            # Atomic rollback: delete any files already uploaded
            for key in uploaded_keys:
                try:
                    delete_media_file(key)
                except Exception:
                    pass
            raise
        finally:
            # Release any file handles held by UploadFile objects
            if form_data is not None:
                for _, value in form_data.multi_items():
                    if isinstance(value, UploadFile):
                        try:
                            await value.close()
                        except Exception:
                            pass

# ==================== Songs (نوحه‌ها) ====================

class SongAdmin(ModelView, model=Song):
    """
    مدیریت نوحه‌ها (Song) — آپلود صوت/کاور و نمایش خوانای نام مداح.

    نکته: در ستون «مداح» مقدار ``Song.artist`` نمایش داده می‌شود که با
    ``Artist.__str__`` به «نام مداح» تبدیل می‌شود (نه نام کلاس/آدرس حافظه).
    """

    name = "نوحه"
    name_plural = "نوحه‌ها"
    icon = "fa-solid fa-music"

    # --- List view ---
    column_list = [
        Song.id,
        Song.cover_url,
        Song.title,
        Song.artist,
        Song.occasion,
        Song.style,
        Song.year,
        Song.duration,
        Song.created_at,
    ]

    # --- Search ---
    column_searchable_list = ["title", "occasion", "style"]

    # --- Sort ---
    column_sortable_list = [
        "id",
        "title",
        "artist_id",
        "occasion",
        "style",
        "year",
        "duration",
        "created_at",
    ]

    column_filters = []

    # --- Detail view ---
    column_details_list = [
        Song.id,
        Song.title,
        Song.artist,
        Song.audio_url,
        Song.cover_url,
        Song.lyrics,
        Song.occasion,
        Song.style,
        Song.year,
        Song.duration,
        Song.created_at,
    ]

    # --- Form (file pickers instead of raw URL inputs) ---
    form_columns = [
        Song.title,
        Song.artist,
        Song.audio_url,
        Song.cover_url,
        Song.lyrics,
        Song.occasion,
        Song.style,
        Song.year,
        Song.duration,
    ]

    form_overrides = {
        "audio_url": FileField,
        "cover_url": FileField,
    }

    form_args = {
        "audio_url": {
            "label": "فایل صوتی",
            "validators": [],
            "render_kw": {"accept": _AUDIO_ACCEPT},
        },
        "cover_url": {
            "label": "کاور",
            "validators": [],
            "render_kw": {"accept": _IMAGE_ACCEPT},
        },
    }

    column_formatters = {Song.cover_url: _image_column_formatter("cover_url")}
    column_formatters_detail = {Song.cover_url: _image_column_formatter("cover_url")}

    create_template = "admin/media_form.html"
    edit_template = "admin/media_form.html"

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_labels = {
        Song.title: "عنوان",
        Song.artist: "مداح",
        Song.audio_url: "فایل صوتی",
        Song.cover_url: "کاور",
        Song.lyrics: "متن نوحه",
        Song.occasion: "مناسبت",
        Song.style: "سبک",
        Song.year: "سال",
        Song.duration: "مدت (ثانیه)",
        Song.created_at: "تاریخ ایجاد",
    }

    async def scaffold_form(self, rules: list[str] | None = None):
        """جایگزینی ورودی‌های متنی URL با فیلدهای آپلود فایل."""
        form_cls = await super().scaffold_form(rules)

        class SongUploadForm(form_cls):
            audio_url = FileField(
                label="فایل صوتی",
                validators=[],
                render_kw={"accept": _AUDIO_ACCEPT},
            )
            cover_url = FileField(
                label="کاور",
                validators=[],
                render_kw={"accept": _IMAGE_ACCEPT},
            )

        return SongUploadForm

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """آپلود صوت/کاور نوحه و ذخیرهٔ URL عمومی در ستون‌ها.

        مثل TrackAdmin، در صورت خطا فایل‌های آپلودشدهٔ همین درخواست حذف
        می‌شوند تا رکورد یتیم باقی نماند.
        """
        uploaded_keys: list[str] = []
        form_data: Any = None

        try:
            form_data = await request.form()
            audio_value = data.get("audio_url")
            cover_value = data.get("cover_url")

            # ---- Audio file upload (اجباری فقط در زمان ساخت) ----
            if _is_uploaded_file(audio_value):
                content = await _read_upload(audio_value)
                if not content:
                    raise ValueError("فایل صوتی خالی است.")
                result = store_media_audio(
                    file_content=content,
                    filename=audio_value.filename or "song.mp3",
                    content_type=audio_value.content_type or "audio/mpeg",
                    subfolder=SONG_UPLOAD_FOLDER,
                    max_mb=settings.media_audio_max_mb,
                )
                uploaded_keys.append(result.key)
                data["audio_url"] = result.url
            elif is_created:
                raise ValueError("انتخاب فایل صوتی الزامی است.")
            else:
                data.pop("audio_url", None)

            # ---- Cover file upload ----
            clear_cover = any(
                k in {"cover_url_checkbox", "cover_url_clear"}
                for k, _ in form_data.multi_items()
            )

            if clear_cover:
                data["cover_url"] = None
            elif _is_uploaded_file(cover_value):
                content = await _read_upload(cover_value)
                if content:
                    result = store_media_image(
                        file_content=content,
                        filename=cover_value.filename or "cover.jpg",
                        content_type=cover_value.content_type or "image/jpeg",
                        subfolder=SONG_UPLOAD_FOLDER,
                        max_mb=settings.media_image_max_mb,
                    )
                    uploaded_keys.append(result.key)
                    data["cover_url"] = result.url
            else:
                data.pop("cover_url", None)

            # هرگز اجازه ندهیم UploadFile به SQLAlchemy برسد.
            for key in ("audio_url", "cover_url"):
                if isinstance(data.get(key), UploadFile):
                    data.pop(key, None)

        except Exception:
            for key in uploaded_keys:
                try:
                    delete_media_file(key)
                except Exception:
                    pass
            raise
        finally:
            if form_data is not None:
                for _, value in form_data.multi_items():
                    if isinstance(value, UploadFile):
                        try:
                            await value.close()
                        except Exception:
                            pass


# ==================== Playlists ====================

class PlaylistAdmin(ModelView, model=Playlist):
    """Curated playlist management."""

    name = "پلی‌لیست"
    name_plural = "پلی‌لیست‌ها"
    icon = "fa-solid fa-list"

    column_list = [
        Playlist.id,
        Playlist.title,
        Playlist.artist,
        Playlist.is_featured,
        Playlist.created_at,
    ]

    column_searchable_list = ["title"]
    column_sortable_list = ["id", "title", "is_featured", "created_at"]
    column_filters = []

    form_columns = [
        Playlist.title,
        Playlist.description,
        Playlist.artist,
        Playlist.cover_url,
        Playlist.is_featured,
        Playlist.songs,
    ]

    page_size = 50

    column_labels = {
        Playlist.title: "عنوان",
        Playlist.description: "توضیحات",
        Playlist.artist: "مداح",
        Playlist.cover_url: "کاور",
        Playlist.is_featured: "ویژه",
        Playlist.created_at: "تاریخ ایجاد",
        Playlist.songs: "نوحه‌ها",
    }

    # نمایش بندانگشتی کاور در نمای جزئیات
    column_formatters_detail = {
        Playlist.cover_url: _image_column_formatter("cover_url")
    }


# ==================== Analytics ====================

class InteractionAdmin(ModelView, model=UserInteraction):
    """
    User interaction viewer (read-only for analytics).
    """
    
    name = "تعامل کاربر"
    name_plural = "تعاملات کاربران"
    icon = "fa-solid fa-chart-line"
    
    # List view
    column_list = [
        UserInteraction.id,
        UserInteraction.user,
        UserInteraction.track,
        UserInteraction.interaction_type,
        UserInteraction.listen_duration,
        UserInteraction.weight,
        UserInteraction.timestamp,
    ]
    
    # Filters for analytics
    column_filters = []

    # Sort
    column_sortable_list = [
        "id",
        "timestamp",
        "weight",
        "listen_duration",
    ]
    
    # Detail view
    column_details_list = [
        UserInteraction.id,
        UserInteraction.user,
        UserInteraction.track,
        UserInteraction.interaction_type,
        UserInteraction.listen_duration,
        UserInteraction.search_query,
        UserInteraction.weight,
        UserInteraction.timestamp,
    ]
    
    # Read-only (interactions logged by app, not created manually)
    can_create = False
    can_edit = False
    can_delete = True  # Allow cleanup of old data
    
    page_size = 100
    page_size_options = [50, 100, 200, 500]
    
    column_labels = {
        UserInteraction.user: "کاربر",
        UserInteraction.track: "آهنگ",
        UserInteraction.interaction_type: "نوع تعامل",
        UserInteraction.listen_duration: "مدت شنیدن (ثانیه)",
        UserInteraction.search_query: "جستجو",
        UserInteraction.weight: "وزن",
        UserInteraction.timestamp: "زمان",
    }
