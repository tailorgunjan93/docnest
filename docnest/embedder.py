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


def embed_in_batches(
    embedder: "IEmbedder", texts: list[str], batch_size: int = 64
) -> np.ndarray:
    """Embed ``texts`` in fixed-size batches so peak memory does not scale with len(texts).

    Order-preserving; returns a ``(len(texts), dims)`` float32 array. ``batch_size <= 0``
    falls back to a single ``embed`` call. Bounds the per-call memory of any ``IEmbedder``
    — important once large sections are split into many passages.
    """
    if not texts:
        dims = getattr(embedder, "dims", 0) or 0
        return np.empty((0, dims), dtype=np.float32)
    if batch_size <= 0:
        return np.asarray(embedder.embed(texts), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        vecs = embedder.embed(texts[i:i + batch_size])
        parts.append(np.asarray(vecs, dtype=np.float32))
    return np.vstack(parts)


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


class SentenceTransformerEmbedder(IEmbedder):
    """Local embeddings using HuggingFace sentence-transformers.

    Default model: all-MiniLM-L6-v2
        - 384 dimensions
        - Fast, lightweight (~80 MB)
        - Great quality for semantic search and RAG

    Other good models:
        all-mpnet-base-v2       → 768-dim, higher quality, slower
        all-MiniLM-L12-v2       → 384-dim, slightly better than L6
        multi-qa-MiniLM-L6-cos-v1 → optimised for Q&A retrieval

    Install: pip install sentence-transformers
    Runs fully offline after first download. No API key required.

    Usage:
        embedder = SentenceTransformerEmbedder()           # all-MiniLM-L6-v2
        embedder = SentenceTransformerEmbedder("all-mpnet-base-v2")
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model
        self._model: object | None = None  # lazy init

        # Known dims for popular models — used before the model is loaded
        _KNOWN_DIMS = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
            "multi-qa-MiniLM-L6-cos-v1": 384,
            "paraphrase-MiniLM-L6-v2": 384,
        }
        self._dims = _KNOWN_DIMS.get(model, 384)

    @property
    def dims(self) -> int:
        # Return exact dims from loaded model if available
        if self._model is not None:
            try:
                return self._model.get_sentence_embedding_dimension()  # type: ignore[attr-defined]
            except Exception:
                pass
        return self._dims

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore[import]
            except ImportError as exc:
                raise EmbedError(
                    "sentence-transformers is not installed. "
                    "Run: pip install sentence-transformers"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts using sentence-transformers.

        Args:
            texts: List of strings (section text or summaries).

        Returns:
            float32 array of shape (len(texts), dims).

        Raises:
            EmbedError: If sentence-transformers is not installed or fails.
        """
        if not texts:
            return np.empty((0, self.dims), dtype=np.float32)
        try:
            model = self._get_model()
            # show_progress_bar=False keeps output clean during pipeline runs
            vectors = model.encode(  # type: ignore[attr-defined]
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,   # L2-normalise for cosine similarity
            )
            return np.array(vectors, dtype=np.float32)
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(
                f"SentenceTransformerEmbedder ({self._model_name}) failed: {exc}"
            ) from exc


class LangChainEmbedder(IEmbedder):
    """Universal embedder backed by any LangChain Embeddings provider.

    One class, every provider — swap provider+model without touching
    any other pipeline code.

    Supported providers (lazy imports — install only what you need):

        Provider          Install                              Model example
        ─────────────────────────────────────────────────────────────────────
        huggingface/hf    pip install langchain-huggingface    all-MiniLM-L6-v2
        openai            pip install langchain-openai         text-embedding-3-small
        ollama            pip install langchain-ollama         nomic-embed-text
        google            pip install langchain-google-genai   models/text-embedding-004
        cohere            pip install langchain-cohere         embed-english-v3.0
        bedrock / aws     pip install langchain-aws            amazon.titan-embed-text-v2:0
        nvidia / nim      pip install langchain-nvidia-ai-endpoints  NV-Embed-QA
        mistral           pip install langchain-mistralai       mistral-embed
        ─────────────────────────────────────────────────────────────────────

    Usage:
        # Local sentence-transformers (free, offline after first download)
        embedder = LangChainEmbedder("huggingface", "all-MiniLM-L6-v2")

        # OpenAI (1536-dim, cloud)
        embedder = LangChainEmbedder("openai", "text-embedding-3-small")

        # Ollama local (nomic-embed-text, 768-dim)
        embedder = LangChainEmbedder("ollama", "nomic-embed-text")

        # Google Gemini (768-dim, free tier)
        embedder = LangChainEmbedder("google", "models/text-embedding-004")
    """

    # Known embedding dimensions for popular models
    _KNOWN_DIMS: dict[str, int] = {
        # HuggingFace / sentence-transformers
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
        "multi-qa-MiniLM-L6-cos-v1": 384,
        "paraphrase-MiniLM-L6-v2": 384,
        # OpenAI
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        # Ollama / nomic
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        # Google
        "models/text-embedding-004": 768,
        "models/embedding-001": 768,
        # Cohere
        "embed-english-v3.0": 1024,
        "embed-multilingual-v3.0": 1024,
        # Mistral
        "mistral-embed": 1024,
    }

    def __init__(
        self,
        provider: str = "huggingface",
        model: str = "all-MiniLM-L6-v2",
        api_key: str | None = None,
        **kwargs: object,
    ) -> None:
        """
        Args:
            provider: Embedding provider name (huggingface, openai, ollama, etc.)
            model:    Model identifier for that provider.
            api_key:  API key. Optional — falls back to the provider's env var.
                      Omit for local providers (huggingface local, ollama).
            **kwargs: Extra kwargs forwarded to the provider constructor.
        """
        self._provider = provider
        self._model_name = model
        self._api_key = api_key
        self._kwargs = kwargs
        self._lc_embedder: object | None = None  # lazy init
        self._dims = self._KNOWN_DIMS.get(model, 768)

    @property
    def dims(self) -> int:
        return self._dims

    @property
    def model_name(self) -> str:
        return f"{self._provider}/{self._model_name}"

    def _get_lc_embedder(self) -> object:
        if self._lc_embedder is None:
            try:
                from docnest.llm import get_embeddings  # type: ignore[import]
                self._lc_embedder = get_embeddings(
                    self._provider, self._model_name,
                    api_key=self._api_key,
                    **self._kwargs,
                )
            except Exception as exc:
                raise EmbedError(
                    f"Failed to initialise LangChain embedder "
                    f"({self._provider}/{self._model_name}): {exc}"
                ) from exc
        return self._lc_embedder

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts using the configured LangChain provider.

        Args:
            texts: List of strings to embed.

        Returns:
            float32 array of shape (len(texts), dims).

        Raises:
            EmbedError: If the provider package is not installed or embedding fails.
        """
        if not texts:
            return np.empty((0, self.dims), dtype=np.float32)
        try:
            lc = self._get_lc_embedder()
            vectors = lc.embed_documents(texts)  # type: ignore[attr-defined]
            arr = np.array(vectors, dtype=np.float32)
            # Update dims from actual output if unknown model
            if arr.shape[0] > 0:
                self._dims = arr.shape[1]
            return arr
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(
                f"LangChainEmbedder ({self._provider}/{self._model_name}) failed: {exc}"
            ) from exc
