"""
Interaction tracking endpoints — core of personalization engine.

Logs every user action (play, like, skip, complete, search) and updates
the real-time feedback loop when configured.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.ml.base import compute_interaction_weight
from app.models import InteractionType, Track, User, UserInteraction
from app.schemas import InteractionCreate, InteractionOut
from app.security import get_current_user
from app.services.recommendation import handle_feedback

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.post("", response_model=InteractionOut, status_code=status.HTTP_201_CREATED)
def log_interaction(
    interaction_in: InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ثبت یک تعامل کاربر (play, like, skip, complete, search)."""
    valid_types = {t.value for t in InteractionType}
    if interaction_in.interaction_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"نوع تعامل نامعتبر است. مقادیر مجاز: {sorted(valid_types)}",
        )

    track = None
    if interaction_in.track_id is not None:
        track = db.query(Track).filter(Track.id == interaction_in.track_id).first()
        if not track:
            raise HTTPException(status_code=404, detail="آهنگ پیدا نشد")

    itype = InteractionType(interaction_in.interaction_type)

    # Compute weight (type + time decay)
    weight = compute_interaction_weight(itype, datetime.now())

    interaction = UserInteraction(
        user_id=current_user.id,
        track_id=interaction_in.track_id,
        interaction_type=itype,
        listen_duration=interaction_in.listen_duration,
        search_query=interaction_in.search_query,
        weight=weight,
    )
    db.add(interaction)

    # Update counters
    if track:
        if itype == InteractionType.PLAY:
            track.view_count = (track.view_count or 0) + 1
        elif itype == InteractionType.LIKE:
            track.like_count = (track.like_count or 0) + 1
        elif itype == InteractionType.UNLIKE:
            track.like_count = max((track.like_count or 0) - 1, 0)
        elif itype == InteractionType.SKIP:
            track.skip_count = (track.skip_count or 0) + 1

    db.commit()
    db.refresh(interaction)

    # Real-time feedback loop (optional: update taste vector immediately)
    try:
        if interaction_in.track_id is not None:
            from app.config import get_settings
            settings = get_settings()
            # Only enable if RECO_REALTIME_LR > 0 in .env
            if settings.realtime_lr > 0:
                handle_feedback(
                    db, current_user.id, interaction_in.track_id,
                    interaction_in.interaction_type, interaction_in.listen_duration
                )
    except Exception as e:
        # Don't fail the request if feedback update fails
        print(f"[WARN] Real-time feedback update failed: {e}")

    return interaction


@router.get("/users/me/history", response_model=list[InteractionOut])
def get_my_history(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """دریافت تاریخچه تعاملات کاربر جاری."""
    return (
        db.query(UserInteraction)
        .filter(UserInteraction.user_id == current_user.id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
        .all()
    )
