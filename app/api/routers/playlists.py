"""
Playlist endpoints — user playlists + personalized recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Playlist, Track, User
from app.schemas import PlaylistAddTrack, PlaylistCreate, PlaylistOut, TrackOut
from app.security import get_current_user
from app.services.recommendation import get_recommendations

router = APIRouter(prefix="/playlists", tags=["Playlists"])


@router.get("/recommended", response_model=list[TrackOut])
def get_recommended_playlist(
    limit: int = Query(30, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    پلی‌لیست پویا و شخصی‌سازی‌شده بر اساس تاریخچه تعاملات.

    این endpoint از موتور ML استفاده می‌کند (v4 hybrid recommender).
    """
    tracks = get_recommendations(db, current_user.id, limit)
    return tracks


@router.post("", response_model=PlaylistOut, status_code=status.HTTP_201_CREATED)
def create_playlist(
    playlist_in: PlaylistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ایجاد پلی‌لیست جدید."""
    playlist = Playlist(
        name=playlist_in.name,
        is_private=playlist_in.is_private,
        owner_id=current_user.id,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist


@router.get("/me", response_model=list[PlaylistOut])
def get_my_playlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """دریافت پلی‌لیست‌های کاربر جاری."""
    return db.query(Playlist).filter(Playlist.owner_id == current_user.id).all()


@router.post("/{playlist_id}/songs")
@router.post("/{playlist_id}/tracks")
def add_track_to_playlist(
    playlist_id: int,
    payload: PlaylistAddTrack,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """افزودن آهنگ به پلی‌لیست."""
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.owner_id == current_user.id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="پلی‌لیست پیدا نشد یا متعلق به شما نیست")

    track = db.query(Track).filter(Track.id == payload.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    if track not in playlist.tracks:
        playlist.tracks.append(track)
        db.commit()

    return {"message": f"آهنگ «{track.title}» به پلی‌لیست «{playlist.name}» اضافه شد"}


@router.delete("/{playlist_id}/songs/{track_id}")
@router.delete("/{playlist_id}/tracks/{track_id}")
def remove_track_from_playlist(
    playlist_id: int,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حذف آهنگ از پلی‌لیست."""
    playlist = (
        db.query(Playlist)
        .filter(Playlist.id == playlist_id, Playlist.owner_id == current_user.id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="پلی‌لیست پیدا نشد یا متعلق به شما نیست")

    track = db.query(Track).filter(Track.id == track_id).first()
    if track and track in playlist.tracks:
        playlist.tracks.remove(track)
        db.commit()

    return {"message": "آهنگ از پلی‌لیست حذف شد"}
