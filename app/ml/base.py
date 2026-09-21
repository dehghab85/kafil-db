"""
Base classes and shared utilities for the ML pipeline.

Exports:
  - InteractionWeights: type-safe weight lookup.
  - time_decay(): exponential half-life decay.
  - compute_interaction_weight(): combines type weight and recency.
  - embedding_from_audio_features(): converts audio JSON → fixed-dim numpy vector.
"""
from __future__ import annotations

import json
import math
from typing import TypedDict

import numpy as np

from app.models import InteractionType


# ---- Interaction weights (same scale as v3; tuned for implicit feedback) ----

class _Weights(TypedDict):
    PLAY: float
    COMPLETE: float
    SEARCH: float
    SKIP: float
    UNLIKE: float


INTERACTION_BASE_WEIGHTS: _Weights = {
    InteractionType.PLAY: 1.0,
    InteractionType.COMPLETE: 2.0,
    InteractionType.LIKE: 3.0,
    InteractionType.SEARCH: 0.5,
    InteractionType.SKIP: -1.5,
    InteractionType.UNLIKE: -2.0,
}


def time_decay(timestamp, half_life_days: float = 30.0) -> float:
    """
    Exponential time decay with configurable half-life.
    A 30-day half-life means an interaction from 30 days ago contributes 0.5.
    """
    age_seconds = max((timestamp - np.datetime64("now", "s")).item(), 0)
    age_days = age_seconds / 86400.0
    return 0.5 ** (age_days / half_life_days)


def compute_interaction_weight(
    interaction_type: InteractionType, timestamp, half_life_days: float = 30.0
) -> float:
    """
    Final interaction weight = base weight × time decay.

    Negative interactions (SKIP, UNLIKE) get a small floor so they don't
    distort the taste vector too aggressively — we penalise, not ban.
    """
    base = INTERACTION_BASE_WEIGHTS.get(interaction_type, 0.0)
    decayed = base * time_decay(timestamp, half_life_days)
    # floor for negative interactions (prevent wild negative spikes from old skips)
    if decayed < 0:
        decayed = max(decayed, -0.5)
    return decayed


# ---- Audio-features → fixed-dim content embedding ----
# Normalisation constants derived from typical Spotify audio analysis ranges.
_AUDIO_FEATURE_SCHEMA = {
    "danceability": (0.0, 1.0),
    "energy": (0.0, 1.0),
    "valence": (0.0, 1.0),
    "acousticness": (0.0, 1.0),
    "instrumentalness": (0.0, 1.0),
    "liveness": (0.0, 1.0),
    "speechiness": (0.0, 1.0),
    "tempo": (50.0, 200.0),  # BPM
    "loudness": (-60.0, 0.0),  # dB
}


def embedding_from_audio_features(audio_features: dict | str | None) -> np.ndarray | None:
    """
    تبدیل dict ویژگی‌های صوتی به بردار با ابعاد ثابت (RECO_CONTENT_DIM).

    ساختار بردار:
      [0:8]  — 8 ویژگی صوتی اصلی (نرمال‌شده به [0,1])
      [8:12] — 4 ویژگی genre one-hot (hard-coded، از نام genre استخراج می‌شود)
      [12:]  — padding تا RECO_CONTENT_DIM (zeros)

    وقتی audio_features خالی باشد، بردار zero برگردانده می‌شود
    (cold-start content retrieval از متادیتای artist/genre استفاده می‌کند).
    """
    from app.config import get_settings

    settings = get_settings()
    dim = settings.content_dim
    vec = np.zeros(dim, dtype=np.float64)

    if audio_features is None:
        return vec

    if isinstance(audio_features, str):
        try:
            audio_features = json.loads(audio_features)
        except (json.JSONDecodeError, TypeError):
            return vec

    if not isinstance(audio_features, dict):
        return vec

    # ویژگی‌های صوتی اصلی (نرمال‌شده)
    ordered_features = [
        "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "liveness", "speechiness",
    ]
    for i, key in enumerate(ordered_features):
        if key in audio_features:
            lo, hi = _AUDIO_FEATURE_SCHEMA.get(key, (0.0, 1.0))
            val = float(audio_features[key])
            vec[i] = (val - lo) / (hi - lo) if hi != lo else 0.0

    # Tempo (نرمال‌شده جداگانه)
    if "tempo" in audio_features:
        lo, hi = _AUDIO_FEATURE_SCHEMA["tempo"]
        val = float(audio_features["tempo"])
        vec[7] = (val - lo) / (hi - lo) if hi != lo else 0.0

    # Loudness (نرمال‌شده از dB به [0,1])
    if "loudness" in audio_features:
        lo, hi = _AUDIO_FEATURE_SCHEMA["loudness"]
        val = float(audio_features["loudness"])
        vec[8] = (val - lo) / (hi - lo) if hi != lo else 0.0

    # Genre one-hot: اولین 4 ژانر را از نام استخراج می‌کنیم
    # (در عمل این بردار از جدول genre + track_genres محاسبه می‌شود.)
    # vec[9:13] reserved for genre one-hot (filled in pipeline.py using DB data)

    return vec