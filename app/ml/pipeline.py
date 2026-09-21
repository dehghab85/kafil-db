"""
Main recommendation pipeline — orchestrates CF, content, and ranking.

Pipeline steps:
  1. Fetch interactions from DB.
  2. Compute track content embeddings from audio_features + metadata.
  3. Fit CF model (ALS) on interaction matrix.
  4. Build ANN index for retrieval.
  5. For each user: generate candidate tracks → rank → return top-K.

Features:
  - Incremental update: update_user_embedding updates taste vector only.
  - Cold-start: fallback to trending/popular if no history.
  - Hybrid scoring: weighted sum of CF, content, popularity.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ml.base import compute_interaction_weight, embedding_from_audio_features
from app.ml.collaborative import CFModel, build_cf_model, get_item_vector, get_user_vector
from app.ml.retrieval import ANNIndex, create_ann_index
from app.models import InteractionType, Track, UserInteraction

settings = get_settings()


@dataclass
class TrackRecord:
    """Cache-friendly track summary."""
    id: int
    content_vector: NDArray[np.float64]
    artist_id: int
    genre_ids: list[int]
    view_count: int
    like_count: int


@dataclass
class PipelineResult:
    """نتیجه تکرار کامل pipeline."""
    cf_model: CFModel
    ann_index: ANNIndex
    tracks_by_id: dict[int, TrackRecord]
    users_with_vectors: int
    items_with_vectors: int


class RecommendationPipeline:
    """پیپ‌لاین کامل تولید پیشنهادات."""

    def __init__(self, db: Session):
        self.db = db
        self.ann_backend = create_ann_index(settings.ann_backend)
        self._tracks_by_id: dict[int, TrackRecord] = {}
        self._cf_model: CFModel | None = None

    # ---- 1. Content vector computation ----

    def _compute_track_content_vector(self, track: Track) -> NDArray[np.float64]:
        """Compute content embedding from audio_features + metadata."""
        dim = settings.content_dim
        vec = np.zeros(dim, dtype=np.float64)

        # Base vector from audio features
        base = embedding_from_audio_features(track.audio_features)
        vec[: len(base)] = base

        # Add genre contribution (simplified: average of genre vectors)
        # در عمل این بخش از یک embedding layer برای ژانرها می‌آید.
        # برای سادگی، تعداد ژانرها را به عنوان وزن اضافه می‌کنیم.
        n_genres = len(track.genres)
        if n_genres > 0:
            # Placeholder: genre embedding from one-hot to content space
            genre_weight = 0.1
            for g in track.genres:
                idx = (hash(g.name) % (dim - 9)) + 9  # place in vec[9:dim]
                vec[idx] += genre_weight / n_genres

        # Normalize to unit length
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        return vec

    def _refresh_track_vectors(self) -> dict[int, TrackRecord]:
        """
        محاسبه بردارهای محتوایی تمام آهنگ‌ها و ذخیره در دیتابیس.

        Returns:
            dict[track_id, TrackRecord]
        """
        tracks = self.db.query(Track).all()
        updated_count = 0

        for track in tracks:
            vec = self._compute_track_content_vector(track)
            track.content_vector = vec.tolist()
            self._tracks_by_id[track.id] = TrackRecord(
                id=track.id,
                content_vector=vec,
                artist_id=track.artist_id,
                genre_ids=[g.id for g in track.genres],
                view_count=track.view_count or 0,
                like_count=track.like_count or 0,
            )
            updated_count += 1

        if updated_count > 0:
            self.db.commit()
            print(f"[PIPELINE] Updated content vectors for {updated_count} tracks")

        return self._tracks_by_id

    # ---- 2. Build CF model from interactions ----

    def _build_cf_model(self) -> CFModel:
        """ساخت مدل CF بر اساس تاریخچه تعاملات."""
        interactions = (
            self.db.query(UserInteraction)
            .filter(UserInteraction.track_id.isnot(None))
            .all()
        )

        # (user_id, track_id, weight)
        raw = [(i.user_id, i.track_id, i.weight or 1.0) for i in interactions]

        if not raw:
            print("[PIPELINE] No interactions found — CF model will be empty")
            return CFModel.from_scratch(0, 0, settings.cf_dim)

        model = build_cf_model(
            raw,
            dim=settings.cf_dim,
            iterations=15,
            regularization=0.01,
            alpha=40.0,
            seed=42,
        )
        print(f"[PIPELINE] CF model: {model.n_users} users, {model.n_items} items")
        return model

    # ---- 3. Build ANN index ----

    def _build_ann_index(self, tracks_by_id: dict[int, TrackRecord]) -> ANNIndex:
        """ساخت ایندکس ANN از بردارهای محتوایی."""
        ids = []
        vectors = []

        for tid, rec in tracks_by_id.items():
            ids.append(tid)
            vectors.append(rec.content_vector)

        if not vectors:
            return self.ann_backend

        self.ann_backend.build(np.array(vectors, dtype=np.float64), ids)
        print(f"[PIPELINE] ANN index built: {len(ids)} items")
        return self.ann_backend

    # ---- 4. Compute user taste vectors ----

    def _update_user_taste_vectors(self) -> int:
        """
        محاسبه taste_vector برای همه کاربران بر اساس تعاملات.

        taste_vector = Σ (interaction_weight × track_content_vector)
        """
        users = self.db.query(UserInteraction.user_id).distinct().all()
        updated = 0

        for (user_id,) in users:
            user_interactions = (
                self.db.query(UserInteraction)
                .filter(UserInteraction.user_id == user_id)
                .filter(UserInteraction.track_id.isnot(None))
                .all()
            )

            if not user_interactions:
                continue

            # Weighted sum of track content vectors
            vec = np.zeros(settings.content_dim, dtype=np.float64)
            total_weight = 0.0

            for inter in user_interactions:
                track_rec = self._tracks_by_id.get(inter.track_id)
                if track_rec is None:
                    continue

                w = inter.weight or compute_interaction_weight(
                    inter.interaction_type, inter.timestamp, settings.half_life_days
                )
                vec += w * track_rec.content_vector
                total_weight += abs(w)

            if total_weight > 0:
                vec /= total_weight

            # Normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm

            # Update user record
            from app.models import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.taste_vector = vec.tolist()
                updated += 1

        if updated > 0:
            self.db.commit()
            print(f"[PIPELINE] Updated taste vectors for {updated} users")

        return updated

    # ---- 5. Full pipeline execution ----

    def run(self) -> PipelineResult:
        """
        اجرای کامل pipeline:

        1. Refresh track content vectors
        2. Build CF model
        3. Build ANN index
        4. Update user taste vectors

        Returns:
            PipelineResult برای ذخیره در دیتابیس/ذخیره ارتفاکت.
        """
        print("[PIPELINE] Starting full pipeline...")

        # Step 1
        print("[PIPELINE] Step 1: Computing content vectors...")
        tracks_by_id = self._refresh_track_vectors()

        # Step 2
        print("[PIPELINE] Step 2: Building CF model...")
        cf_model = self._build_cf_model()
        self._cf_model = cf_model

        # Step 3
        print("[PIPELINE] Step 3: Building ANN index...")
        self._build_ann_index(tracks_by_id)

        # Step 4
        print("[PIPELINE] Step 4: Computing user taste vectors...")
        self._update_user_taste_vectors()

        # Stats
        with_vecs = sum(1 for t in tracks_by_id.values() if np.any(t.content_vector))
        cf_users = cf_model.n_users if cf_model else 0
        cf_items = cf_model.n_items if cf_model else 0

        print("[PIPELINE] Complete!")

        return PipelineResult(
            cf_model=cf_model,
            ann_index=self.ann_backend,
            tracks_by_id=tracks_by_id,
            users_with_vectors=cf_users,
            items_with_vectors=cf_items,
        )

    # ---- 6. Single-user recommendation (runtime) ----

    def recommend_for_user(
        self,
        user_id: int,
        limit: int = 30,
        w_collab: float | None = None,
        w_content: float | None = None,
        w_popularity: float | None = None,
        exclude_ids: list[int] | None = None,
    ) -> list[tuple[int, dict[str, float]]]:
        """
        تولید پیشنهاد برای یک کاربر (runtime).

        Returns:
            [(track_id, {score, collab_score, content_score, pop_score}), ...]
        """
        if exclude_ids is None:
            exclude_ids = []

        w_collab = w_collab or settings.w_collab
        w_content = w_content or settings.w_content
        w_popularity = w_popularity or settings.w_popularity

        # Validate weights
        total = w_collab + w_content + w_popularity
        if abs(total - 1.0) > 1e-6:
            scale = 1.0 / total
            w_collab *= scale
            w_content *= scale
            w_popularity *= scale

        # 1. Fetch user taste vector
        from app.models import User
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None or user.taste_vector is None:
            return self._recommend_popular(limit, exclude_ids)

        taste_vec = np.array(user.taste_vector, dtype=np.float64)

        # 2. Fetch recent interactions (to exclude)
        recent = (
            self.db.query(UserInteraction.track_id)
            .filter(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_type == InteractionType.PLAY,
            )
            .order_by(UserInteraction.timestamp.desc())
            .limit(50)
            .all()
        )
        recent_ids = {r[0] for r in recent if r[0] is not None}

        # 3. ANN retrieval for candidates (content-based)
        ann_ids, ann_scores = self.ann_index.search(taste_vec, settings.candidate_pool)
        candidates = [tid for tid in ann_ids if tid not in exclude_ids and tid not in recent_ids]
        if len(candidates) < 5:
            # Fallback: add popular tracks
            candidates.extend(self._get_popular_ids(20, exclude_ids | recent_ids))

        # 4. Score candidates
        scored = []
        for track_id in candidates:
            track_rec = self._tracks_by_id.get(track_id)
            if track_rec is None:
                continue

            # Content score (already computed by ANN, normalize)
            content_score = ann_scores.get(track_id, 0.0) if track_id in ann_ids else 0.0

            # CF score: dot(product(taste_vec, item_cf_vector))
            cf_score = 0.0
            if self._cf_model:
                cf_vec = get_item_vector(self._cf_model, track_id)
                if cf_vec is not None:
                    cf_score = np.dot(taste_vec, cf_vec)

            # Popularity score (normalized)
            pop_score = (track_rec.like_count + 1) / (track_rec.view_count + 100)
            pop_score = min(1.0, pop_score * 100)  # crude normalization

            # Hybrid score
            score = w_content * content_score + w_collab * cf_score + w_popularity * pop_score

            scored.append((track_id, {
                "score": float(score),
                "collab_score": float(cf_score),
                "content_score": float(content_score),
                "pop_score": float(pop_score),
            }))

        # Sort by total score
        scored.sort(key=lambda x: x[1]["score"], reverse=True)

        return scored[:limit]

    # ---- 7. Cold-start fallback ----

    def _get_popular_ids(self, n: int, exclude_ids: set[int] | None = None) -> list[int]:
        """id آهنگ‌های م��بوب (برای cold-start/backup)."""
        if exclude_ids is None:
            exclude_ids = set()

        query = (
            self.db.query(Track.id)
            .order_by(Track.like_count.desc(), Track.view_count.desc())
        )
        if exclude_ids:
            query = query.filter(~Track.id.in_(exclude_ids))

        return [r[0] for r in query.limit(n).all()]

    def _recommend_popular(
        self, limit: int, exclude_ids: list[int]
    ) -> list[tuple[int, dict[str, float]]]:
        """Recommendation برای کاربران جدید (بدون تاریخچه)."""
        scores = []
        for tid in self._get_popular_ids(limit * 2, set(exclude_ids)):
            track_rec = self._tracks_by_id.get(tid)
            if track_rec is None:
                continue
            scores.append((tid, {
                "score": float(track_rec.like_count + 1),
                "collab_score": 0.0,
                "content_score": 0.0,
                "pop_score": 1.0,
            }))
        return scores[:limit]

    # ---- 8. Real-time feedback update ----

    def update_user_embedding(
        self,
        user_id: int,
        track_id: int,
        interaction_type: InteractionType,
        listen_duration: int = 0,
    ) -> NDArray[np.float64]:
        """
        به‌روزرسانی taste_vector کاربر بعد از یک تعامل جدید.

        Strategy:
          1. محاسبه وزن تعامل (type + time decay).
          2. Fetch current user vector.
          3. Fetch track content vector.
          4. EMA update: new_vec = (1 - lr) × old_vec + lr × weight × track_vec.
          5. Update DB.

        Returns:
            آپدیت شده taste_vector (numpy array).
        """
        from app.models import User

        # Get current user vector
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None or user.taste_vector is None:
            # Fallback: compute from scratch
            return self._update_user_taste_vectors()

        old_vec = np.array(user.taste_vector, dtype=np.float64)

        # Get track vector
        track_rec = self._tracks_by_id.get(track_id)
        if track_rec is None:
            # Try DB lookup
            track = self.db.query(Track).get(track_id)
            if track:
                track_rec = TrackRecord(
                    id=track.id,
                    content_vector=self._compute_track_content_vector(track),
                    artist_id=track.artist_id,
                    genre_ids=[g.id for g in track.genres],
                    view_count=track.view_count or 0,
                    like_count=track.like_count or 0,
                )
                self._tracks_by_id[track_id] = track_rec

        if track_rec is None:
            return old_vec

        # Compute interaction weight
        weight = compute_interaction_weight(
            interaction_type, datetime.now(), settings.half_life_days
        )
        if interaction_type == InteractionType.UNLIKE:
            weight = -abs(weight)
        elif interaction_type == InteractionType.SKIP:
            weight = -abs(weight)

        # EMA update
        lr = settings.realtime_lr
        new_vec = (1 - lr) * old_vec + lr * weight * track_rec.content_vector

        # Normalize
        norm = np.linalg.norm(new_vec)
        if norm > 0:
            new_vec /= norm

        # Save to DB
        user.taste_vector = new_vec.tolist()
        self.db.commit()

        return new_vec


def run_pipeline(db: Session) -> PipelineResult:
    """
    Helper function — یک بار اجرای pipeline کامل.
    """
    pipeline = RecommendationPipeline(db)
    return pipeline.run()
