"""
ANN (Approximate Nearest Neighbor) retrieval — candidate generation.

پیاده‌سازی پیش‌فرض: brute-force cosine similarity در NumPy (exact, not approximate).
قابل جایگزینی با:
  - pgvector (RECO_ANN_BACKEND=pgvector): native postgres vector index.
  - FAISS (RECO_ANN_BACKEND=faiss): GPU-accelerated IVF/HNSW.
  - Annoy (RECO_ANN_BACKEND=annoy): Spotify's tree-based ANN library.

Backend را در .env با RECO_ANN_BACKEND تنظیم کنید.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class ANNIndex(Protocol):
    """Interface for ANN backends."""

    def build(self, vectors: NDArray[np.float64], ids: list[int]) -> None:
        """ساخت ایندکس از بردارها."""
        ...

    def search(
        self, query: NDArray[np.float64], k: int
    ) -> tuple[list[int], list[float]]:
        """
        جستجوی k نزدیک‌ترین همسایه.

        Returns:
            (ids, scores) که scores از بزرگ به کوچک مرتب شده‌اند (cosine similarity).
        """
        ...

    def save(self, path: str) -> None:
        ...

    def load(self, path: str) -> None:
        ...


# ---- NumPy brute-force (default) ----

class NumpyANN:
    """Exact brute-force cosine similarity search (no approximation)."""

    def __init__(self):
        self.vectors: NDArray[np.float64] | None = None
        self.ids: list[int] = []

    def build(self, vectors: NDArray[np.float64], ids: list[int]) -> None:
        # Normalize vectors to unit length for cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid div-by-zero
        self.vectors = vectors / norms
        self.ids = ids

    def search(
        self, query: NDArray[np.float64], k: int
    ) -> tuple[list[int], list[float]]:
        if self.vectors is None or len(self.ids) == 0:
            return [], []

        # Normalize query
        q_norm = np.linalg.norm(query)
        if q_norm > 0:
            query = query / q_norm

        # Cosine similarity = dot product (since vectors are normalized)
        scores = self.vectors @ query  # shape (n,)
        top_k_idx = np.argsort(-scores)[:k]  # descending order

        return [self.ids[i] for i in top_k_idx], scores[top_k_idx].tolist()

    def save(self, path: str) -> None:
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        np.savez_compressed(
            path,
            vectors=self.vectors if self.vectors is not None else np.array([]),
            ids=np.array(self.ids, dtype=np.int32),
        )

    def load(self, path: str) -> None:
        data = np.load(path, allow_pickle=False)
        self.vectors = data["vectors"] if data["vectors"].size > 0 else None
        self.ids = data["ids"].tolist()


# ---- Factory ----

def create_ann_index(backend: str = "numpy") -> ANNIndex:
    """
    ساخت یک ANNIndex بر اساس backend.

    Backends:
      - numpy: brute-force exact search (default, همیشه کار می‌کند).
      - pgvector: از operator <=> PostgreSQL استفاده می‌کند (نیاز به افزونه).
      - faiss: FAISS IVFFlat or HNSW (نیاز به faiss-cpu).
      - annoy: Spotify Annoy (نیاز به annoy).
    """
    if backend == "numpy":
        return NumpyANN()
    elif backend == "pgvector":
        # TODO: wrapper روی SQL query با <=> operator
        raise NotImplementedError("pgvector backend requires DB session context")
    elif backend == "faiss":
        try:
            import faiss
            return _FaissANN()
        except ImportError:
            raise RuntimeError("FAISS backend needs: pip install faiss-cpu")
    elif backend == "annoy":
        try:
            from annoy import AnnoyIndex
            return _AnnoyANN()
        except ImportError:
            raise RuntimeError("Annoy backend needs: pip install annoy")
    else:
        raise ValueError(f"Unknown ANN backend: {backend}")


# ---- Optional backend stubs (loaded only if libs are installed) ----

class _FaissANN:
    def __init__(self):
        import faiss
        self.index = None
        self.ids = []
        self.dim = 0

    def build(self, vectors: NDArray[np.float64], ids: list[int]) -> None:
        import faiss
        self.dim = vectors.shape[1]
        self.ids = ids
        # L2-normalized vectors → inner product = cosine similarity
        faiss.normalize_L2(vectors)
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors.astype(np.float32))

    def search(self, query: NDArray[np.float64], k: int) -> tuple[list[int], list[float]]:
        import faiss
        if self.index is None:
            return [], []
        query = query.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query)
        scores, indices = self.index.search(query, k)
        return [self.ids[i] for i in indices[0]], scores[0].tolist()

    def save(self, path: str) -> None:
        import faiss, os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        faiss.write_index(self.index, path + ".faiss")
        np.savez_compressed(path + ".meta", ids=np.array(self.ids, dtype=np.int32))

    def load(self, path: str) -> None:
        import faiss
        self.index = faiss.read_index(path + ".faiss")
        meta = np.load(path + ".meta.npz", allow_pickle=False)
        self.ids = meta["ids"].tolist()


class _AnnoyANN:
    def __init__(self):
        self.index = None
        self.ids = []
        self.dim = 0

    def build(self, vectors: NDArray[np.float64], ids: list[int]) -> None:
        from annoy import AnnoyIndex
        self.dim = vectors.shape[1]
        self.ids = ids
        self.index = AnnoyIndex(self.dim, "angular")  # cosine
        for i, vec in enumerate(vectors):
            self.index.add_item(i, vec)
        self.index.build(10)  # 10 trees

    def search(self, query: NDArray[np.float64], k: int) -> tuple[list[int], list[float]]:
        if self.index is None:
            return [], []
        indices, dists = self.index.get_nns_by_vector(query, k, include_distances=True)
        # Annoy returns angular distance; convert to cosine similarity
        scores = [1.0 - (d ** 2) / 2.0 for d in dists]
        return [self.ids[i] for i in indices], scores

    def save(self, path: str) -> None:
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.index.save(path + ".annoy")
        np.savez_compressed(path + ".meta", ids=np.array(self.ids, dtype=np.int32))

    def load(self, path: str) -> None:
        from annoy import AnnoyIndex
        meta = np.load(path + ".meta.npz", allow_pickle=False)
        self.ids = meta["ids"].tolist()
        self.index = AnnoyIndex(self.dim, "angular")
        self.index.load(path + ".annoy")
