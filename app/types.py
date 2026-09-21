"""
نوع ستون برداری قابل حمل بین PostgreSQL و SQLite.

- روی PostgreSQL به `vector(dim)` از افزونه pgvector نگاشت می‌شود (قابل ایندکس ANN).
- روی سایر دیالکت‌ها (SQLite) به‌صورت JSON در ستون TEXT ذخیره می‌شود.

ورودی می‌تواند list / tuple / numpy.ndarray باشد؛ خروجی همیشه list[float] یا None است.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
from sqlalchemy.types import Text, TypeDecorator


class EmbeddingType(TypeDecorator):
    cache_ok = True
    impl = Text

    def __init__(self, dim: int, **kw: Any) -> None:
        self.dim = dim
        super().__init__(**kw)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            value = value.astype(float).tolist()
        else:
            value = [float(x) for x in value]
        if dialect.name == "postgresql":
            return value  # pgvector خودش list را می‌پذیرد
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)
