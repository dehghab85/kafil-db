"""
UserInteraction Model - SQLAlchemy 2.0
ثبت تمام تعاملات کاربر برای سیستم توصیه‌گر Kafil
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base
from app.types import EmbeddingType

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.user import User

settings = get_settings()


class InteractionType(str, enum.Enum):
    PLAY = "play"
    COMPLETE = "complete"
    LIKE = "like"
    UNLIKE = "unlike"
    SKIP = "skip"
    SEARCH = "search"


class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True)

    interaction_type: Mapped[InteractionType] = mapped_column(Enum(InteractionType), nullable=False)
    listen_duration: Mapped[int] = mapped_column(Integer, default=0)
    search_query: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    context_vector = mapped_column(EmbeddingType(dim=settings.content_dim), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interactions")
    track: Mapped[Optional["Track"]] = relationship("Track")

    __table_args__ = (
        Index("ix_interaction_user_time", "user_id", "timestamp"),
        Index("ix_interaction_user_track", "user_id", "track_id"),
    )
