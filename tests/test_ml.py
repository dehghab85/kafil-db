"""
Tests for ML components (unit tests).
"""
import numpy as np

from app.ml.base import compute_interaction_weight, embedding_from_audio_features
from app.ml.collaborative import CFModel, build_cf_model
from app.ml.retrieval import NumpyANN
from app.models import InteractionType


def test_interaction_weight():
    """Test weight computation."""
    from datetime import datetime
    weight = compute_interaction_weight(InteractionType.LIKE, datetime.now(), half_life_days=30)
    assert 2.5 <= weight <= 3.5  # base=3.0, recent decay≈1.0


def test_audio_features_embedding():
    """Test audio features → vector."""
    features = {
        "danceability": 0.7,
        "energy": 0.8,
        "valence": 0.6,
        "tempo": 120,
    }
    vec = embedding_from_audio_features(features)
    assert vec is not None
    assert len(vec) == 48  # RECO_CONTENT_DIM default
    assert vec[0] == pytest.approx(0.7, abs=0.01)  # danceability


def test_cf_model_build():
    """Test CF model construction."""
    interactions = [
        (1, 10, 1.0),
        (1, 20, 2.0),
        (2, 10, 1.5),
        (2, 30, 1.0),
    ]
    model = build_cf_model(interactions, dim=8, iterations=5)
    assert model.n_users == 2
    assert model.n_items == 3
    assert model.user_factors.shape == (8, 2)
    assert model.item_factors.shape == (8, 3)


def test_numpy_ann():
    """Test brute-force ANN."""
    vectors = np.random.randn(100, 16).astype(np.float64)
    ids = list(range(100))

    ann = NumpyANN()
    ann.build(vectors, ids)

    query = np.random.randn(16).astype(np.float64)
    result_ids, scores = ann.search(query, k=5)

    assert len(result_ids) == 5
    assert len(scores) == 5
    assert all(isinstance(i, int) for i in result_ids)
