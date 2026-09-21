"""
Recommendation service — high-level API-facing interface to the ML pipeline.

این سرویس:
  - Pipeline را load می‌کند (از artifact ذخیره‌شده یا می‌سازد).
  - Endpoint برای run کامل pipeline ارائه می‌دهد (admin).
  - Endpoint برای recommendation query (runtime) ارائه می‌دهد.
  - Real-time feedback loop را handle می‌کند.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.config import get_settings
from app.ml import RecommendationPipeline
from app.models import Track

if TYPE_CHECKING:
    from app.schemas import RecommendationDebug, TrackOut

settings = get_settings()


def run_full_pipeline(db: Session) -> dict:
    """
    اجرای کامل pipeline و ذخیره artifacts.

    Returns:
        dict با آمار pipeline.
    """
    from app.ml import run_pipeline

    result = run_pipeline(db)

    # Save artifacts
    artifact_dir = settings.artifact_dir
    os.makedirs(artifact_dir, exist_ok=True)

    cf_path = os.path.join(artifact_dir, "cf_model.npz")
    ann_path = os.path.join(artifact_dir, "ann_index.npz")

    if result.cf_model:
        result.cf_model.save(cf_path)
    result.ann_index.save(ann_path)

    return {
        "status": "completed",
        "users_with_vectors": result.users_with_vectors,
        "items_with_vectors": result.items_with_vectors,
        "total_tracks": len(result.tracks_by_id),
    }


def get_recommendations(
    db: Session,
    user_id: int,
    limit: int = 30,
    w_collab: float | None = None,
    w_content: float | None = None,
    w_popularity: float | None = None,
) -> list[Track]:
    """
    دریافت آهنگ‌های پیشنهادی برای یک کاربر.

    Returns:
        list[Track] (ORM objects با relations loaded).
    """
    pipeline = RecommendationPipeline(db)

    # Load artifacts if exist
    artifact_dir = settings.artifact_dir
    cf_path = os.path.join(artifact_dir, "cf_model.npz")

    if os.path.exists(cf_path):
        from app.ml.collaborative import CFModel
        pipeline._cf_model = CFModel.load(cf_path)

    # Get scored recommendations
    scored = pipeline.recommend_for_user(
        user_id, limit, w_collab, w_content, w_popularity
    )

    # Fetch Track ORM objects
    track_ids = [tid for tid, _ in scored]
    if not track_ids:
        return []

    from sqlalchemy.orm import joinedload
    tracks = (
        db.query(Track)
        .filter(Track.id.in_(track_ids))
        .options(
            joinedload(Track.artist),
            joinedload(Track.album),
            joinedload(Track.genres),
        )
        .all()
    )

    # Re-order by scored order
    track_map = {t.id: t for t in tracks}
    return [track_map[tid] for tid in track_ids if tid in track_map]


def get_recommendations_with_debug(
    db: Session,
    user_id: int,
    limit: int = 30,
    w_collab: float | None = None,
    w_content: float | None = None,
    w_popularity: float | None = None,
) -> list[dict]:
    """
    دریافت recommendation همراه با اطلاعات debug (برای admin panel).

    Returns:
        list[{"track": TrackOut, "score": float, "collab_score": ..., ...}]
    """
    pipeline = RecommendationPipeline(db)

    # Load artifacts if exist
    artifact_dir = settings.artifact_dir
    cf_path = os.path.join(artifact_dir, "cf_model.npz")

    if os.path.exists(cf_path):
        from app.ml.collaborative import CFModel
        pipeline._cf_model = CFModel.load(cf_path)

    # Get scored recommendations
    scored = pipeline.recommend_for_user(
        user_id, limit, w_collab, w_content, w_popularity
    )

    # Fetch Track ORM objects
    track_ids = [tid for tid, _ in scored]
    if not track_ids:
        return []

    from sqlalchemy.orm import joinedload
    tracks = (
        db.query(Track)
        .filter(Track.id.in_(track_ids))
        .options(
            joinedload(Track.artist),
            joinedload(Track.album),
            joinedload(Track.genres),
        )
        .all()
    )
    track_map = {t.id: t for t in tracks}

    # Build result with debug info
    results = []
    for tid, scores in scored:
        if tid not in track_map:
            continue
        from app.schemas import TrackOut
        results.append({
            "track": TrackOut.model_validate(track_map[tid]),
            "score": scores["score"],
            "collab_score": scores["collab_score"],
            "content_score": scores["content_score"],
            "pop_score": scores["pop_score"],
        })

    return results


def handle_feedback(
    db: Session,
    user_id: int,
    track_id: int,
    interaction_type: str,
    listen_duration: int = 0,
) -> dict:
    """
    Real-time feedback: به‌روزرسانی taste vector کاربر بعد از یک تعامل.

    Returns:
        dict با وضعیت و taste_vector جدید.
    """
    from app.models import InteractionType

    try:
        itype = InteractionType(interaction_type)
    except ValueError:
        return {"error": f"Invalid interaction_type: {interaction_type}"}

    pipeline = RecommendationPipeline(db)
    new_vec = pipeline.update_user_embedding(user_id, track_id, itype, listen_duration)

    return {
        "status": "updated",
        "user_id": user_id,
        "track_id": track_id,
        "new_taste_vector": new_vec.tolist(),
    }


def get_user_profile_debug(db: Session, user_id: int) -> dict:
    """
    دریافت اطلاعات کامل پروفایل یک کاربر (برای admin panel).

    Returns:
        dict با taste_vector، top genres/artists، recent interactions.
    """
    from app.models import User, UserInteraction

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    # Recent interactions
    recent = (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(20)
        .all()
    )

    # Parse preferred genres/artists from JSON
    import json
    top_genres = []
    top_artists = []

    if user.preferred_genre_ids:
        try:
            genre_ids = json.loads(user.preferred_genre_ids)
            from app.models import Genre
            genres = db.query(Genre).filter(Genre.id.in_(genre_ids)).all()
            top_genres = [{"id": g.id, "name": g.name} for g in genres]
        except:
            pass

    if user.preferred_artist_ids:
        try:
            artist_ids = json.loads(user.preferred_artist_ids)
            from app.models import Artist
            artists = db.query(Artist).filter(Artist.id.in_(artist_ids)).all()
            top_artists = [{"id": a.id, "name": a.name} for a in artists]
        except:
            pass

    from app.schemas import InteractionOut
    return {
        "user_id": user.id,
        "taste_vector": user.taste_vector,
        "top_genres": top_genres,
        "top_artists": top_artists,
        "recent_interactions": [InteractionOut.model_validate(i) for i in recent],
        "total_interactions": db.query(UserInteraction).filter(
            UserInteraction.user_id == user_id
        ).count(),
    }
