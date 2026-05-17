"""
Embedding generation — Stage 6a of the DocNest pipeline.

Generates dense vector representations of section text for semantic search.
Embeddings are computed once at ingest time and stored (quantised) in the .udf.

Design pattern: Strategy — swap embedding model without changing pipeline.
Phase: 2  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np

from docnest.exceptions import EmbedError


class IEmbedder(ABC):
    """Abstract base for all embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts. Returns float32 array of shape (len(texts), dims)."""
        ...

    @property
    @abstractmethod
    def dims(self) -> int:
        """Embedding dimensionality."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Canonical model identifier stored in manifest.json."""
        ...


class NomicEmbedder(IEmbedder):
    """Local embeddings using nomic-embed-text-v1.5 via fastembed.

    FREE — runs on CPU, no API key, no internet required after first download.
    768 dimensions. Good quality for most RAG use cases.

    Install: pip install fastembed
    """

    def __init__(self) -> None:
        self._model: object | None = None  # lazy init

    @property
    def dims(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "nomic-ai/nomic-embed-text-v1.5"

    def _get_model(self) -> object:
        if self._model is None:
            try:
                from fastembed import TextEmbedding  # type: ignore[import]
            except ImportError as exc:
                raise EmbedError(
                    "fastembed is not installed. Run: pip install fastembed"
                ) from exc
            self._model = TextEmbedding("nomic-ai/nomic-embed-text-v1.5")
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts locally using fastembed.

        Args:
            texts: List of strings (section text or summaries).

        Returns:
            float32 array of shape (len(texts), 768).

        Raises:
            EmbedError: If fastembed fails or is not installed.
        """
        if not texts:
            return np.empty((0, self.dims), dtype=np.float32)
        try:
            model = self._get_model()
            embeddings = list(model.embed(texts))  # type: ignore[attr-defined]
            return np.array(embeddings, dtype=np.float32)
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(f"NomicEmbedder failed: {exc}") from exc


class OpenAIEmbedder(IEmbedder):
    """Cloud embeddings via OpenAI text-embedding-3-small.

    Requires OPENAI_API_KEY env var or explicit api_key.
    ~$0.002 per 100-page document. 1536 dimensions.
    Install: pip install openai
    """

    def __init__(self, api_key: str | None = None) -> None:
        import os
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise EmbedError("OpenAI API key required. Set OPENAI_API_KEY env var.")
        self._client: object | None = None

    @property
    def dims(self) -> int:
        return 1536

    @property
    def model_name(self) -> str:
        return "text-embedding-3-small"

    def _get_client(self) -> object:
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore[import]
            except ImportError as exc:
                raise EmbedError(
                    "openai package not installed. Run: pip install openai"
                ) from exc
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dims), dtype=np.float32)
        try:
            client = self._get_client()
            response = client.embeddings.create(  # type: ignore[attr-defined]
                model="text-embedding-3-small", input=texts
            )
            vectors = [e.embedding for e in response.data]
            return np.array(vectors, dtype=np.float32)
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(f"OpenAIEmbedder failed: {exc}") from exc


class GoogleEmbedder(IEmbedder):
    """Cloud embeddings via Google text-embedding-004.

    Free tier: 1M tokens/month. 768 dimensions.
    Install: pip install google-generativeai
    """

    def __init__(self, api_key: str | None = None) -> None:
        import os
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not self.api_key:
            raise EmbedError("Google API key required. Set GOOGLE_API_KEY env var.")

    @property
    def dims(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "text-embedding-004"

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dims), dtype=np.float32)
        try:
            import google.generativeai as genai  # type: ignore[import]
            genai.configure(api_key=self.api_key)
            vectors = []
            for text in texts:
                result = genai.embed_content(
                    model="models/text-embedding-004", content=text
                )
                vectors.append(result["embedding"])
            return np.array(vectors, dtype=np.float32)
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(f"GoogleEmbedder failed: {exc}") from exc
