"""
Collaborative Filtering — Matrix Factorization via ALS (Alternating Least Squares).

این ماژول یک پیاده‌سازی کامل ALS برای implicit feedback (Hu et al., 2008)
است که **فقط روی NumPy** اجرا می‌شود. این پیاده‌سازی قابل جایگزینی با
کتابخانه‌های faster مانند `implicit` است (RECO_CF_BACKEND=implicit).

الگوریتم Weighted Regularized Matrix Factorization (WRMF):
  - R[i,u] = 1  if user u has any interaction with item i, else 0
  - C[i,u] = 1 + alpha × weight[i,u]   (confidence in the preference)
  - P[i,u] = 1  if weight > threshold, else 0  (binary preference)

  Minimise: Σ_{u,i} C[i,u](P[i,u] − X[:,u]·Y[:,i])² + λ(||X||² + ||Y||²)
  Alternating: fix Y → solve for each X[:,u] (closed-form with ridge regression);
               fix X → solve for each Y[:,i].
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from app.config import get_settings

settings = get_settings()


@dataclass
class CFModel:
    """
    ذخیره‌سازی بردارهای عامل کاربر و آهنگ.

    Attributes:
        user_factors: shape (cf_dim, n_users); هر ستون = latent vector کاربر.
        item_factors:  shape (cf_dim, n_items);  هر ستون = latent vector آهنگ.
        user_id_map:   id کاربر ← index ستونی
        item_id_map:   id آهنگ  ← index ستونی
    """
    user_factors: NDArray[np.float64]
    item_factors: NDArray[np.float64]
    user_id_map: dict[int, int] = field(default_factory=dict)
    item_id_map: dict[int, int] = field(default_factory=dict)
    n_users: int = 0
    n_items: int = 0

    @classmethod
    def from_scratch(
        cls, n_users: int, n_items: int, dim: int, seed: int = 42
    ) -> CFModel:
        rng = np.random.default_rng(seed)
        return cls(
            user_factors=rng.normal(0, 0.01, (dim, n_users)).astype(np.float64),
            item_factors=rng.normal(0, 0.01, (dim, n_items)).astype(np.float64),
            n_users=n_users,
            n_items=n_items,
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        np.savez_compressed(
            path,
            user_factors=self.user_factors,
            item_factors=self.item_factors,
            user_id_map=np.array(list(self.user_id_map.items()), dtype=np.int32),
            item_id_map=np.array(list(self.item_id_map.items()), dtype=np.int32),
        )

    @classmethod
    def load(cls, path: str) -> CFModel:
        data = np.load(path, allow_pickle=False)
        uid_pairs = data["user_id_map"]
        iid_pairs = data["item_id_map"]
        return cls(
            user_factors=data["user_factors"],
            item_factors=data["item_factors"],
            user_id_map={int(k): int(v) for k, v in uid_pairs},
            item_id_map={int(k): int(v) for k, v in iid_pairs},
            n_users=data["user_factors"].shape[1],
            n_items=data["item_factors"].shape[1],
        )


def fit_als(
    interaction_matrix: NDArray[np.float64],
    confidence_matrix: NDArray[np.float64],
    dim: int,
    iterations: int = 15,
    regularization: float = 0.01,
    seed: int = 42,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    ALS optimization for implicit feedback.

    Args:
        interaction_matrix: shape (n_items, n_users); binary preference (0 or 1).
        confidence_matrix: shape (n_items, n_users); confidence weight C[i,u].
        dim: latent dimensionality.
        iterations: number of ALS passes.
        regularization: L2 penalty λ.
        seed: random seed for initialization.

    Returns:
        (user_factors, item_factors) both shape (dim, n_{users|items}).
    """
    n_items, n_users = interaction_matrix.shape
    rng = np.random.default_rng(seed)

    # Initialize factor matrices with small random noise
    X = rng.normal(0, 0.01, (dim, n_users)).astype(np.float64)  # user factors
    Y = rng.normal(0, 0.01, (dim, n_items)).astype(np.float64)  # item factors

    reg_eye = regularization * np.eye(dim, dtype=np.float64)

    for iteration in range(iterations):
        # Fix Y, solve for each user u's vector X[:,u]
        for u in range(n_users):
            Cu = confidence_matrix[:, u]  # (n_items,)
            Pu = interaction_matrix[:, u]  # (n_items,)
            # Weighted least-squares closed form:
            # X[:,u] = (Y @ diag(Cu) @ Y.T + λI)^{-1} @ Y @ diag(Cu) @ Pu
            Y_weighted = Y * np.sqrt(Cu)  # shape (dim, n_items)
            A = Y_weighted @ Y_weighted.T + reg_eye  # (dim, dim)
            b = Y_weighted @ (Cu * Pu)  # (dim,)
            X[:, u] = np.linalg.solve(A, b)

        # Fix X, solve for each item i's vector Y[:,i]
        for i in range(n_items):
            Ci = confidence_matrix[i, :]  # (n_users,)
            Pi = interaction_matrix[i, :]  # (n_users,)
            X_weighted = X * np.sqrt(Ci)
            A = X_weighted @ X_weighted.T + reg_eye
            b = X_weighted @ (Ci * Pi)
            Y[:, i] = np.linalg.solve(A, b)

    return X, Y


def build_cf_model(
    interactions: list[tuple[int, int, float]],
    dim: int = 32,
    iterations: int = 15,
    regularization: float = 0.01,
    alpha: float = 40.0,
    seed: int = 42,
) -> CFModel:
    """
    ساخت مدل CF از لیست تعاملات.

    Args:
        interactions: [(user_id, track_id, weight), ...]
        dim: ابعاد latent (RECO_CF_DIM).
        iterations: تعداد دورهای ALS.
        regularization: λ (پنالتی L2).
        alpha: ضریب confidence = 1 + alpha × |weight|.
        seed: random seed.

    Returns:
        CFModel با بردارهای user_factors و item_factors.
    """
    if not interactions:
        return CFModel.from_scratch(0, 0, dim, seed)

    # Build ID maps
    user_ids = sorted({u for u, _, _ in interactions})
    item_ids = sorted({i for _, i, _ in interactions})
    user_id_map = {uid: idx for idx, uid in enumerate(user_ids)}
    item_id_map = {iid: idx for idx, iid in enumerate(item_ids)}

    n_users = len(user_ids)
    n_items = len(item_ids)

    # Build interaction and confidence matrices
    R = np.zeros((n_items, n_users), dtype=np.float64)
    C = np.ones((n_items, n_users), dtype=np.float64)  # baseline confidence

    for user_id, item_id, weight in interactions:
        u_idx = user_id_map[user_id]
        i_idx = item_id_map[item_id]
        # Binary preference (any positive weight → 1)
        R[i_idx, u_idx] = 1.0 if weight > 0 else 0.0
        # Confidence scales with weight magnitude
        C[i_idx, u_idx] = 1.0 + alpha * abs(weight)

    X, Y = fit_als(R, C, dim, iterations, regularization, seed)

    model = CFModel(
        user_factors=X,
        item_factors=Y,
        user_id_map=user_id_map,
        item_id_map=item_id_map,
        n_users=n_users,
        n_items=n_items,
    )
    return model


def get_user_vector(model: CFModel, user_id: int) -> NDArray[np.float64] | None:
    """دریافت بردار CF یک کاربر."""
    idx = model.user_id_map.get(user_id)
    if idx is None:
        return None
    return model.user_factors[:, idx]


def get_item_vector(model: CFModel, item_id: int) -> NDArray[np.float64] | None:
    """دریافت بردار CF یک آهنگ."""
    idx = model.item_id_map.get(item_id)
    if idx is None:
        return None
    return model.item_factors[:, idx]
