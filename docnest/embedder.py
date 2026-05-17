"""
Embedding generation — Stage 6a of the DOCNEST pipeline.

Generates dense vector representations of section text for semantic search.
Embeddings are computed once at ingest time and stored (quantised) in the .udf.

Phase: 2  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
Design pattern: Strategy — swap embedding model without changing pipeline.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np


class IEmbedder(ABC):
    """Abstract base for all embedding providers.

    Implement this to add a new embedding model.
    Register in pipeline.py or pass directly to DOCNESTPipeline.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts into float32 vectors.

        Args:
            texts: List of text strings to embed (section summaries or full text).

        Returns:
            numpy array of shape (len(texts), self.dims) — dtype float32.

        Raises:
            EmbedError: If embedding fails for any text.
        """
        ...

    @property
    @abstractmethod
    def dims(self) -> int:
        """Embedding dimensionality (e.g. 768 for nomic-embed-text)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Canonical model identifier stored in manifest.json."""
        ...


class NomicEmbedder(IEmbedder):
    """Local embeddings using nomic-embed-text via fastembed.

    FREE — runs on CPU, no API key, no internet required.
    768 dimensions. Good quality for most RAG use cases.

    TODO (Phase 2):
        from fastembed import TextEmbedding
        self._model = TextEmbedding("nomic-ai/nomic-embed-text-v1.5")
        embeddings = list(self._model.embed(texts))
        return np.array(embeddings, dtype=np.float32)
    """

    @property
    def dims(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "nomic-embed-text"

    def embed(self, texts: list[str]) -> np.ndarray:
        # TODO (Phase 2): Implement using fastembed
        raise NotImplementedError("NomicEmbedder not yet implemented.")


class OpenAIEmbedder(IEmbedder):
    """Cloud embeddings via OpenAI text-embedding-3-small.

    Requires OPENAI_API_KEY. ~$0.002 per 100-page document.
    1536 dimensions. Higher quality than local models.

    TODO (Phase 2):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model="text-embedding-3-small", input=texts)
        return np.array([e.embedding for e in response.data], dtype=np.float32)
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    def dims(self) -> int:
        return 1536

    @property
    def model_name(self) -> str:
        return "text-embedding-3-small"

    def embed(self, texts: list[str]) -> np.ndarray:
        # TODO (Phase 2): Implement using openai SDK
        raise NotImplementedError("OpenAIEmbedder not yet implemented.")


class GoogleEmbedder(IEmbedder):
    """Cloud embeddings via Google text-embedding-004.

    Free tier: 1M tokens/month. 768 dimensions.

    TODO (Phase 2):
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        result = genai.embed_content(model="models/text-embedding-004", content=texts)
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    def dims(self) -> int:
        return 768

    @property
    def model_name(self) -> str:
        return "text-embedding-004"

    def embed(self, texts: list[str]) -> np.ndarray:
        # TODO (Phase 2): Implement using google-generativeai
        raise NotImplementedError("GoogleEmbedder not yet implemented.")
