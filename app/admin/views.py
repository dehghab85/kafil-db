"""
SQLAdmin model views — comprehensive CRUD with search, filters, and relationships.
"""
from sqladmin import ModelView
from sqlalchemy import func, select

from app.models import Album, Artist, Genre, Playlist, Track, User, UserInteraction


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
    column_searchable_list = [User.username, User.email, User.phone_number]
    
    # Sortable columns
    column_sortable_list = [User.id, User.username, User.created_at]
    
    # Filters
    column_filters = [User.is_admin, User.is_phone_verified, User.created_at]
    
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
    
    # Exclude sensitive/computed fields
    form_excluded_columns = [
        User.password_hash,
        User.taste_vector,
        User.favorite_tracks,
        User.interactions,
        User.playlists,
        User.preferred_genre_ids,
        User.preferred_artist_ids,
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
    """Artist management with search."""
    
    name = "هنرمند"
    name_plural = "هنرمندان"
    icon = "fa-solid fa-microphone"
    
    column_list = [Artist.id, Artist.name, Artist.avatar_url]
    column_searchable_list = [Artist.name]
    column_sortable_list = [Artist.id, Artist.name]
    
    form_columns = [Artist.name, Artist.bio, Artist.avatar_url]
    
    page_size = 50
    
    column_labels = {
        Artist.name: "نام هنرمند",
        Artist.bio: "بیوگرافی",
        Artist.avatar_url: "تصویر",
    }


class AlbumAdmin(ModelView, model=Album):
    """Album management with artist relationship."""
    
    name = "آلبوم"
    name_plural = "آلبوم‌ها"
    icon = "fa-solid fa-compact-disc"
    
    column_list = [Album.id, Album.title, Album.artist, Album.release_date, Album.cover_url]
    column_searchable_list = [Album.title]
    column_sortable_list = [Album.id, Album.title, Album.release_date]
    column_filters = [Album.artist_id, Album.release_date]
    
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
    column_searchable_list = [Genre.name]
    column_sortable_list = [Genre.id, Genre.name]
    
    form_columns = [Genre.name]
    
    page_size = 100
    
    column_labels = {Genre.name: "نام ژانر"}


class TrackAdmin(ModelView, model=Track):
    """
    Track management with image preview, relationships, and filters.
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
    column_searchable_list = [Track.title]
    
    # Sort
    column_sortable_list = [
        Track.id,
        Track.title,
        Track.view_count,
        Track.like_count,
        Track.release_date,
    ]
    
    # Filters
    column_filters = [
        Track.artist_id,
        Track.album_id,
        Track.release_date,
        Track.view_count,
        Track.like_count,
    ]
    
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
    
    # Form
    form_columns = [
        Track.title,
        Track.artist,  # Relationship select
        Track.album,   # Relationship select
        Track.genres,  # Multi-select
        Track.audio_url,
        Track.cover_url,
        Track.duration_sec,
        Track.release_date,
        Track.lyrics,
        Track.lyrics_timestamps,
    ]
    
    # Exclude computed/internal fields
    form_excluded_columns = [
        Track.interactions,
        Track.favorited_by,
        Track.content_vector,
        Track.audio_features,
        Track.view_count,
        Track.like_count,
        Track.skip_count,
    ]
    
    # Read-only (stats updated by interactions)
    form_readonly_columns = []
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]
    
    # Custom labels
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


# ==================== Playlists ====================

class PlaylistAdmin(ModelView, model=Playlist):
    """Playlist management."""
    
    name = "پلی‌لیست"
    name_plural = "پلی‌لیست‌ها"
    icon = "fa-solid fa-list"
    
    column_list = [
        Playlist.id,
        Playlist.name,
        Playlist.owner,
        Playlist.is_private,
        Playlist.is_auto_generated,
        Playlist.created_at,
    ]
    
    column_searchable_list = [Playlist.name]
    column_sortable_list = [Playlist.id, Playlist.name, Playlist.created_at]
    column_filters = [Playlist.owner_id, Playlist.is_private, Playlist.is_auto_generated]
    
    form_columns = [
        Playlist.name,
        Playlist.owner,
        Playlist.is_private,
        Playlist.is_auto_generated,
        Playlist.tracks,  # Multi-select
    ]
    
    page_size = 50
    
    column_labels = {
        Playlist.name: "نام پلی‌لیست",
        Playlist.owner: "مالک",
        Playlist.is_private: "خصوصی",
        Playlist.is_auto_generated: "خودکار",
        Playlist.created_at: "تاریخ ایجاد",
        Playlist.tracks: "آهنگ‌ها",
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
    column_filters = [
        UserInteraction.user_id,
        UserInteraction.track_id,
        UserInteraction.interaction_type,
        UserInteraction.timestamp,
    ]
    
    # Sort
    column_sortable_list = [
        UserInteraction.id,
        UserInteraction.timestamp,
        UserInteraction.weight,
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
