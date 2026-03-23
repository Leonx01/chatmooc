from __future__ import annotations

from threading import Lock
from typing import Any

from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import settings


class EmbedCore:
    """Embedding provider manager (lazy + thread-safe)."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._lock = Lock()

    @property
    def model(self):
        """Lazy load embedding model when first used."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = DashScopeEmbeddings(
                        model=settings.EMBEDDING_MODEL,
                        dashscope_api_key=settings.DASHSCOPE_API_KEY,
                    )
        return self._model

    def embed_text(self, text: str) -> list[float]:
        return self.model.embed_query(text)

    def embed_docs(self, docs: list[str]) -> list[list[float]]:
        return self.model.embed_documents(docs)


_embed_core = EmbedCore()


def get_embedding_model():
    """Unified entrypoint for embedding model instance."""
    return _embed_core.model
