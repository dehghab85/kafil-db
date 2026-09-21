"""
Tracks (Songs) endpoints — catalog browsing, search, CRUD.

Maintains backward compatibility with v3 `/songs` paths.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Album, Artist, Genre, Track, User
from app.schemas import TrackCreate, TrackOut
from app.security import get_current_user

router = APIRouter(tags=["Tracks"])


@router.get("/songs", response_model=list[TrackOut])
@router.get("/tracks", response_model=list[TrackOut])
def get_tracks(
    genre: Optional[str] = None,
    artist_id: Optional[int] = None,
    q: Optional[str] = Query(None, description="جستجو در عنوان آهنگ"),
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """دریافت لیست آهنگ‌ها با فیلترهای اختیاری."""
    query = db.query(Track).options(
        joinedload(Track.artist), joinedload(Track.album), joinedload(Track.genres)
    )

    if genre:
        query = query.join(Track.genres).filter(Genre.name == genre)
    if artist_id:
        query = query.filter(Track.artist_id == artist_id)
    if q:
        query = query.filter(Track.title.ilike(f"%{q}%"))

    return query.offset(skip).limit(limit).all()


@router.get("/songs/{track_id}", response_model=TrackOut)
@router.get("/tracks/{track_id}", response_model=TrackOut)
def get_track(track_id: int, db: Session = Depends(get_db)):
    """دریافت جزئیات یک آهنگ."""
    track = (
        db.query(Track)
        .options(joinedload(Track.artist), joinedload(Track.album), joinedload(Track.genres))
        .filter(Track.id == track_id)
        .first()
    )
    if not track:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")
    return track


@router.post("/songs", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
@router.post("/tracks", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
def create_track(track_in: TrackCreate, db: Session = Depends(get_db)):
    """ثبت آهنگ جدید (برای پنل مدیریت محتوا)."""
    artist = db.query(Artist).filter(Artist.id == track_in.artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="هنرمند پیدا نشد")

    if track_in.album_id and not db.query(Album).filter(Album.id == track_in.album_id).first():
        raise HTTPException(status_code=404, detail="آلبوم پیدا نشد")

    genres = []
    if track_in.genre_ids:
        genres = db.query(Genre).filter(Genre.id.in_(track_in.genre_ids)).all()

    track = Track(
        title=track_in.title,
        artist_id=track_in.artist_id,
        album_id=track_in.album_id,
        audio_url=track_in.audio_url,
        cover_url=track_in.cover_url,
        duration_sec=track_in.duration_sec,
        lyrics=track_in.lyrics,
        lyrics_timestamps=track_in.lyrics_timestamps,
        genres=genres,
    )

    # Audio features (JSON)
    if track_in.audio_features:
        import json
        track.audio_features = json.dumps(track_in.audio_features)

    db.add(track)
    db.commit()
    db.refresh(track)
    return track


# ---- Favorites ----

@router.post("/songs/{track_id}/favorite")
@router.post("/tracks/{track_id}/favorite")
def add_favorite(track_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """افزودن به علاقه‌مندی‌ها."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if track not in current_user.favorite_tracks:
        current_user.favorite_tracks.append(track)
        db.commit()

    return {"message": f"آهنگ «{track.title}» به علاقه‌مندی‌ها اضافه شد"}


@router.delete("/songs/{track_id}/favorite")
@router.delete("/tracks/{track_id}/favorite")
def remove_favorite(track_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """حذف از علاقه‌مندی‌ها."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if track in current_user.favorite_tracks:
        current_user.favorite_tracks.remove(track)
        db.commit()

    return {"message": f"آهنگ «{track.title}» از علاقه‌مندی‌ها حذف شد"}


@router.get("/users/me/favorites", response_model=list[TrackOut])
def get_favorites(current_user: User = Depends(get_current_user)):
    """دریافت لیست علاقه‌مندی‌های کاربر."""
    return current_user.favorite_tracks


# ---- Metadata ----

@router.get("/artists")
def get_artists(db: Session = Depends(get_db)):
    """دریافت لیست هنرمندان."""
    return db.query(Artist).all()


@router.get("/genres")
def get_genres(db: Session = Depends(get_db)):
    """دریافت لیست ژانرها."""
    return db.query(Genre).all()
