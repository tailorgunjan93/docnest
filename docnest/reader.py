"""
UDF Reader and five-layer query engine.

Loads a .udf file and resolves queries through five escalating layers:
    Layer 0 — Pre-computed intelligence (0 tokens, <1ms)
    Layer 1 — BM25 + cosine hybrid search (0 tokens, <20ms)
    Layer 2 — Section-scoped LLM (~300 tokens, 1-3s)
    Layer 3 — Multi-section synthesis (~900 tokens, 2-5s)
    Layer 4 — Full document fallback (~4000 tokens, 5-15s)

Phase: 4  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Sections 8 and 11
"""

from __future__ import annotations
import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from docnest.models import Catalogue, KeyNumber
from docnest.quantizer import Quantizer
from docnest.exceptions import UDFReadError, IntelligenceError
from docnest.providers.storage import IStorageBackend, ZipStorageBackend
from docnest.providers.search import ISearchProvider, get_search_provider
from docnest.providers.llm import ILLMProvider, get_llm_provider
from docnest.providers.vector import IVectorBackend, NumpyVectorBackend, get_vector_backend

UDF_VERSION = "1.0"

# Thresholds for escalation
_L1_SCORE_THRESHOLD = 0.35   # hybrid BM25+cosine score above this → Layer 1 answer
_L2_SCORE_THRESHOLD = 0.15   # above this → Layer 2 (single section LLM)
# Keywords that trigger Layer 0 pre-computed answers
_SUMMARY_KEYWORDS = {"summarise", "summarize", "summary", "what is this", "overview", "about"}
_INSIGHT_KEYWORDS = {"insight", "finding", "key finding", "takeaway", "conclusion"}

# Table rendering budget for the LLM context (production query path).
# Replaces a former hard 5-row cap so aggregation/lookup questions see all the data
# (bounded by the budget). Rows beyond the budget are summarised as "… (+N more rows)".
_TABLE_CHAR_BUDGET = 1500     # max chars rendered per table in an LLM prompt
_SECTION_PROSE_CHARS = 2000   # Layer-2 prose cap — the table is appended separately so
                              # it is never chopped by this cap.


def _render_table(table: dict, budget: int = _TABLE_CHAR_BUDGET) -> str:
    """Render a table as text up to ``budget`` characters.

    Always shows the header and at least one row; appends ``"… (+N more rows)"`` when
    rows are omitted so the LLM (and the user) know the table was truncated.
    """
    headers = " | ".join(table.get("headers", []))
    lines = [headers]
    used = len(headers)
    shown = 0
    rows = table.get("rows", [])
    for row in rows:
        line = " | ".join(row)
        if used + len(line) + 1 > budget and shown >= 1:
            break
        lines.append(line)
        used += len(line) + 1
        shown += 1
    body = "\n".join(lines)
    omitted = len(rows) - shown
    if omitted > 0:
        body += f"\n… (+{omitted} more rows)"
    return f"Table {table.get('table_id', '')}:\n{body}"


@dataclass
class QueryResult:
    """Result of a five-layer query resolution."""
    answer: str
    citations: list[str] = field(default_factory=list)
    navigate_to: str | None = None       # §id to navigate to (Layer 1)
    layer_used: int = 0
    tokens_used: int = 0
    confidence: float = 0.0


class UDFIndex:
    """In-memory index loaded from a .udf file.

    The catalogue.json is fully loaded into RAM on open.
    content.json sections are fetched lazily (only when LLM needs them).

    Usage:
        index = UDFIndex.load("report.udf")
        result = index.query("What was Q3 revenue?")
        print(result.answer, result.citations)
    """

    def __init__(
        self,
        catalogue: dict[str, Any],
        content: dict[str, Any],
        zip_path: str,
        quantization: str = "float16",
        embedding_dims: int = 768,
        storage: IStorageBackend | None = None,
        search: ISearchProvider | None = None,
        vector: IVectorBackend | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._content   = content
        self._zip_path  = zip_path
        self._quantizer = Quantizer(quantization)
        self._dims      = embedding_dims
        self._storage   = storage or ZipStorageBackend()
        self._search    = search  or get_search_provider("auto")
        self._vector    = vector  or NumpyVectorBackend()   # pluggable vector backend

        # Keyword index — built eagerly (cheap: just tokenised keyword lists)
        self._section_ids: list[str] = []

        # Raw embedding matrix — loaded lazily on first search.
        # None until _load_embed_matrix() is called.
        # Shape when loaded: (n_sections, embedding_dims), dtype float32.
        self._embed_matrix: np.ndarray | None = None
        self._embed_matrix_loaded: bool = False   # True once load was attempted

        # Format flags set during _build_index()
        self._has_binary_embeddings: bool = False   # embeddings.bin present
        self._has_legacy_embeddings: bool = False   # base64 in catalogue (old format)

        self._build_index()

    # ------------------------------------------------------------------ #
    #  Class method: load                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def load(
        cls,
        udf_path: str,
        storage: IStorageBackend | None = None,
        search: ISearchProvider | None = None,
        vector: IVectorBackend | str | None = None,
        **vector_kwargs,
    ) -> "UDFIndex":
        """Load a .udf file and return a queryable UDFIndex.

        Args:
            udf_path:      Path to the .udf file (or directory for "dir" backend).
            storage:       IStorageBackend to use for reading.  Defaults to
                           ZipStorageBackend (standard .udf ZIP format).
            search:        ISearchProvider to use for BM25/keyword search.
                           Defaults to best available (bm25 → tfidf → keyword).
            vector:        IVectorBackend (or backend name string) for semantic
                           similarity search.  Options:
                             ``None`` / ``"numpy"``  — pure NumPy (default, zero deps)
                             ``"faiss"``             — FAISS IndexFlatIP (pip install faiss-cpu)
                             ``"chroma"``            — ChromaDB (pip install chromadb)
                           Pass an IVectorBackend instance to use a custom backend.
            **vector_kwargs: Extra keyword arguments forwarded to get_vector_backend()
                           when ``vector`` is a string (e.g. ``persist_dir="./store"``).

        Returns:
            UDFIndex ready to query.

        Raises:
            UDFReadError:  If the file is missing, invalid, or wrong version.
            ImportError:   If the chosen vector backend's package is not installed.

        Examples::

            # Default — NumPy, zero deps
            idx = UDFIndex.load("report.udf")

            # FAISS — needs: pip install faiss-cpu
            idx = UDFIndex.load("report.udf", vector="faiss")

            # ChromaDB persistent — needs: pip install chromadb
            idx = UDFIndex.load("report.udf", vector="chroma",
                                persist_dir="./chroma_store")
        """
        path    = Path(udf_path)
        backend = storage or ZipStorageBackend()

        if not path.exists():
            raise UDFReadError(f"UDF file not found: {udf_path}")

        try:
            names = backend.list_entries(str(path))
            if "manifest.json" not in names:
                raise UDFReadError(
                    f"Invalid .udf — missing manifest.json: {udf_path}"
                )

            manifest  = backend.read_json(str(path), "manifest.json")
            version   = manifest.get("udf_version", "?")
            if version != UDF_VERSION:
                raise UDFReadError(
                    f"Unsupported .udf version '{version}'. Expected '{UDF_VERSION}'."
                )

            catalogue = backend.read_json(str(path), "catalogue.json")
            content   = backend.read_json(str(path), "content.json")

        except UDFReadError:
            raise
        except Exception as exc:
            raise UDFReadError(f"Failed to open '{udf_path}': {exc}") from exc

        # Resolve the vector backend — accept name string or instance
        if vector is None or isinstance(vector, str):
            vec_backend = get_vector_backend(vector or "numpy", **vector_kwargs)
        else:
            vec_backend = vector

        return cls(
            catalogue=catalogue,
            content=content,
            zip_path=str(path.resolve()),
            quantization=manifest.get("quantization", "float16"),
            embedding_dims=manifest.get("embedding_dims", 768),
            storage=backend,
            search=search,
            vector=vec_backend,
        )

    # ------------------------------------------------------------------ #
    #  Public query API                                                    #
    # ------------------------------------------------------------------ #

    def query(
        self,
        question: str,
        llm_provider: str | ILLMProvider = "groq",
        llm_model: str = "llama-3.3-70b-versatile",
        llm_api_key: str | None = None,
    ) -> QueryResult:
        """Resolve a question through the five-layer stack.

        Args:
            question: Natural language question.
            llm_provider: LLM provider for layers 2-4.
            llm_model: Model name for the provider.

        Returns:
            QueryResult with answer, citations, layer used, and token count.
        """
        q_lower = question.lower().strip()

        # ── Layer 0: pre-computed intelligence (0 tokens) ────────────────
        precomputed = self.get_precomputed(q_lower)
        if precomputed:
            return QueryResult(
                answer=precomputed,
                layer_used=0,
                tokens_used=0,
                confidence=1.0,
            )

        # ── Layer 1: BM25 + cosine hybrid search (0 tokens) ──────────────
        ranked = self._hybrid_search(question)
        if ranked:
            top_id, top_score = ranked[0]
            if top_score >= _L1_SCORE_THRESHOLD:
                entry = self._get_catalogue_entry(top_id)
                summary = entry.get("summary", "") if entry else ""
                if summary:
                    return QueryResult(
                        answer=summary,
                        citations=[top_id],
                        navigate_to=top_id,
                        layer_used=1,
                        tokens_used=0,
                        confidence=min(1.0, top_score),
                    )

        # ── Layer 2: single section LLM (~300 tokens) ─────────────────────
        if ranked:
            top_id, top_score = ranked[0]
            if top_score >= _L2_SCORE_THRESHOLD:
                section_text = self._get_section_text(top_id)
                if section_text:
                    answer, tokens = self._call_llm_section(
                        question, top_id, section_text, llm_provider, llm_model, llm_api_key
                    )
                    return QueryResult(
                        answer=answer,
                        citations=[top_id],
                        navigate_to=top_id,
                        layer_used=2,
                        tokens_used=tokens,
                        confidence=min(1.0, top_score + 0.1),
                    )

        # ── Layer 3: multi-section synthesis (~900 tokens) ────────────────
        if len(ranked) >= 2:
            top_ids = [r[0] for r in ranked[:3]]
            sections = {sid: self._get_section_text(sid) for sid in top_ids}
            sections = {k: v for k, v in sections.items() if v}
            if sections:
                answer, tokens = self._call_llm_multi(
                    question, sections, llm_provider, llm_model, llm_api_key
                )
                return QueryResult(
                    answer=answer,
                    citations=list(sections.keys()),
                    layer_used=3,
                    tokens_used=tokens,
                    confidence=0.6,
                )

        # ── Layer 4: full document fallback (~4000 tokens) ────────────────
        full_text = self._build_full_text()
        answer, tokens = self._call_llm_full(question, full_text, llm_provider, llm_model, llm_api_key)
        return QueryResult(
            answer=answer,
            citations=[],
            layer_used=4,
            tokens_used=tokens,
            confidence=0.4,
        )

    def get_precomputed(self, question: str) -> str | None:
        """Layer 0: check pre-computed intelligence for a direct answer."""
        q = question.lower()

        # Summary request
        if any(kw in q for kw in _SUMMARY_KEYWORDS):
            return self._catalogue.get("summary") or None

        # Insights request
        if any(kw in q for kw in _INSIGHT_KEYWORDS):
            insights = self._catalogue.get("insights", [])
            if insights:
                return "\n".join(f"• {i}" for i in insights)

        # Key number lookup (e.g. "what is revenue" → find label match)
        key_numbers = self._catalogue.get("key_numbers", [])
        for kn in key_numbers:
            label = kn.get("label", "").lower()
            if label and label in q:
                unit = f" {kn['unit']}" if kn.get("unit") else ""
                return f"{kn['label']}: {kn['value']}{unit} (source: {kn.get('section', '')})"

        return None

    def get_section(self, section_id: str) -> dict[str, Any] | None:
        """Fetch full section content by §id from content.json."""
        sections = self._content.get("sections", {})
        return sections.get(section_id)

    # ------------------------------------------------------------------ #
    #  Index building                                                      #
    # ------------------------------------------------------------------ #

    def _build_index(self) -> None:
        """Build keyword search index. Embeddings are NOT decoded here — lazy.

        Only the lightweight keyword/title tokens are processed at load time.
        The embedding matrix is loaded on the first call to _load_embed_matrix(),
        which is triggered only when hybrid search actually needs it.
        """
        section_index    = self._catalogue.get("section_index", [])
        tokenised_corpus: list[list[str]] = []

        for entry in section_index:
            sid = entry.get("id", "")
            self._section_ids.append(sid)
            # Tokenise keywords + title for BM25 / keyword index
            keywords     = entry.get("keywords", [])
            title_tokens = entry.get("title", "").lower().split()
            tokenised_corpus.append(list(set(keywords + title_tokens)))

        # Detect which embedding format is available
        try:
            names = self._storage.list_entries(self._zip_path)
            self._has_binary_embeddings = "embeddings.bin" in names
        except Exception:
            self._has_binary_embeddings = False

        if not self._has_binary_embeddings:
            # Legacy: check if any section entry has a base64 embedding
            self._has_legacy_embeddings = any(
                entry.get("embedding") for entry in section_index
            )

        # Build keyword search index (cheap — no network, no large allocations)
        if tokenised_corpus:
            try:
                self._search.build_index(tokenised_corpus)
            except Exception:
                pass  # index failure → falls back to overlap scoring

    def _load_embed_matrix(self) -> np.ndarray | None:
        """Load the embedding matrix on first call (lazy).

        Returns:
            float32 ndarray of shape (n_sections, embedding_dims), or None if
            no embeddings are available or loading fails.
        """
        if self._embed_matrix_loaded:
            return self._embed_matrix   # already loaded (or already failed)

        self._embed_matrix_loaded = True
        n = len(self._section_ids)
        if n == 0 or self._dims == 0:
            return None

        try:
            if self._has_binary_embeddings:
                # Fast path: raw bytes → single np.frombuffer call, zero-copy reshape
                raw = self._storage.read_entry(self._zip_path, "embeddings.bin")
                expected = n * self._quantizer.stride(self._dims)
                if len(raw) != expected:
                    return None   # corrupt or version mismatch
                mat = (
                    np.frombuffer(raw, dtype=self._quantizer.numpy_dtype)
                    .reshape(n, self._dims)
                    .astype(np.float32)
                )

            elif self._has_legacy_embeddings:
                # Slow path: decode base64 per-section (backward compatibility)
                vecs: list[np.ndarray] = []
                for entry in self._catalogue.get("section_index", []):
                    emb_b64 = entry.get("embedding")
                    if emb_b64:
                        try:
                            emb_bytes = base64.b64decode(emb_b64)
                            vec = self._quantizer.dequantize(emb_bytes, self._dims)
                        except Exception:
                            vec = np.zeros(self._dims, dtype=np.float32)
                    else:
                        vec = np.zeros(self._dims, dtype=np.float32)
                    vecs.append(vec)
                mat = np.stack(vecs) if vecs else None

            else:
                return None

            self._embed_matrix = mat
            # ── Hand the matrix to the vector backend (lazy build) ───────
            try:
                self._vector.build(self._section_ids, mat)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Vector backend build() failed (%s): %s — falling back to numpy",
                    self._vector.backend_name, exc,
                )
                # Fallback: swap in a fresh NumpyVectorBackend silently
                from docnest.providers.vector import NumpyVectorBackend as _NpBE
                self._vector = _NpBE()
                self._vector.build(self._section_ids, mat)
            return mat

        except Exception:
            return None

    # ------------------------------------------------------------------ #
    #  Search                                                              #
    # ------------------------------------------------------------------ #

    def _hybrid_search(self, question: str) -> list[tuple[str, float]]:
        """Keyword (ISearchProvider) + embedding cosine hybrid.

        Score = 0.5 × BM25 + 0.5 × semantic_score
        Semantic score: cosine similarity against stored embeddings if available,
        otherwise falls back to keyword-overlap Jaccard (no embedder needed).

        Embeddings are loaded lazily here — only decoded on first search call.
        """
        if not self._section_ids:
            return []

        tokens = question.lower().split()
        n      = len(self._section_ids)

        # ── BM25 / keyword scores ─────────────────────────────────────────
        kw_scores = np.zeros(n, dtype=np.float32)
        try:
            raw = self._search.get_scores(tokens)
            if raw and len(raw) == n:
                kw_scores = np.array(raw, dtype=np.float32)
        except Exception:
            pass

        # ── Semantic scores — lazy load embeddings on first call ──────────
        sem_scores = np.zeros(n, dtype=np.float32)
        embed_mat  = self._load_embed_matrix()   # None if no embeddings

        if embed_mat is not None and self._vector.is_ready():
            # Build a proxy query vector by averaging stored embeddings of
            # keyword-matching sections (no live embedder needed at query time)
            tok_set = set(tokens)
            match_indices: list[int] = []
            for i, entry_id in enumerate(self._section_ids):
                entry = self._get_catalogue_entry(entry_id)
                if entry:
                    kw = set(entry.get("keywords", []))
                    if kw & tok_set:
                        match_indices.append(i)

            if match_indices:
                query_vec = embed_mat[match_indices].mean(axis=0)
                # ── Delegate to the pluggable vector backend ─────────────
                backend_results = self._vector.search(query_vec, k=n)
                # Scatter backend scores back into sem_scores array by §id
                id_to_idx = {sid: i for i, sid in enumerate(self._section_ids)}
                for sid, score in backend_results:
                    idx = id_to_idx.get(sid)
                    if idx is not None:
                        sem_scores[idx] = score
            else:
                # No keyword matches — Jaccard overlap fallback
                for i, entry_id in enumerate(self._section_ids):
                    entry = self._get_catalogue_entry(entry_id)
                    if entry:
                        kw = set(entry.get("keywords", []))
                        if kw and tok_set:
                            sem_scores[i] = len(kw & tok_set) / max(len(kw | tok_set), 1)
        else:
            # No embeddings available — Jaccard overlap fallback
            tok_set = set(tokens)
            for i, entry_id in enumerate(self._section_ids):
                entry = self._get_catalogue_entry(entry_id)
                if entry:
                    kw = set(entry.get("keywords", []))
                    if kw and tok_set:
                        sem_scores[i] = len(kw & tok_set) / max(len(kw | tok_set), 1)

        # ── Hybrid: 60% keyword, 40% semantic ─────────────────────────────
        hybrid = 0.6 * kw_scores + 0.4 * sem_scores
        order  = np.argsort(hybrid)[::-1]
        return [
            (self._section_ids[i], float(hybrid[i]))
            for i in order
            if float(hybrid[i]) > 0.0
        ]

    # ------------------------------------------------------------------ #
    #  LLM calls                                                           #
    # ------------------------------------------------------------------ #

    def _call_llm_section(
        self,
        question: str,
        section_id: str,
        section_text: str,
        provider: str | ILLMProvider,
        model: str = "",
        api_key: str | None = None,
    ) -> tuple[str, int]:
        """Layer 2: single section answer.

        Prose is capped at ``_SECTION_PROSE_CHARS``; the budget-rendered table is appended
        afterwards so table rows are never chopped by the prose cap (a common cause of
        wrong table-aggregation answers).
        """
        prose, tables = self._section_parts(section_id)
        body = prose[:_SECTION_PROSE_CHARS]
        if tables:
            body += f"\n\n{tables}"
        if not body.strip():
            body = section_text[:_SECTION_PROSE_CHARS]   # fallback to caller-supplied text
        prompt = (
            f"Answer the question using ONLY the section below. "
            f"If the answer is not in the section, say 'Not found in {section_id}'.\n\n"
            f"Section {section_id}:\n{body}\n\n"
            f"Question: {question}"
        )
        answer = _llm_call(prompt, provider, model, api_key)
        return answer, len(prompt.split()) + len(answer.split())

    def _call_llm_multi(
        self,
        question: str,
        sections: dict[str, str],
        provider: str | ILLMProvider,
        model: str = "",
        api_key: str | None = None,
    ) -> tuple[str, int]:
        """Layer 3: multi-section synthesis."""
        context = "\n\n".join(
            f"[{sid}]\n{text[:600]}" for sid, text in sections.items()
        )
        prompt = (
            f"Synthesise an answer from the sections below.\n\n"
            f"{context}\n\n"
            f"Question: {question}"
        )
        answer = _llm_call(prompt, provider, model, api_key)
        return answer, len(prompt.split()) + len(answer.split())

    def _call_llm_full(
        self,
        question: str,
        full_text: str,
        provider: str | ILLMProvider,
        model: str = "",
        api_key: str | None = None,
    ) -> tuple[str, int]:
        """Layer 4: full document fallback."""
        prompt = (
            f"Using the document below, answer: {question}\n\n"
            f"Document:\n{full_text[:6000]}"
        )
        answer = _llm_call(prompt, provider, model, api_key)
        return answer, len(prompt.split()) + len(answer.split())

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_catalogue_entry(self, section_id: str) -> dict[str, Any] | None:
        for entry in self._catalogue.get("section_index", []):
            if entry.get("id") == section_id:
                return entry
        return None

    def _section_parts(self, section_id: str) -> tuple[str, str]:
        """Return (prose, rendered_tables) for a section.

        Tables are budget-rendered (see ``_render_table``) — no hard row cap. Keeping
        prose and tables separate lets callers cap prose without chopping the table.
        """
        section = self.get_section(section_id)
        if not section:
            return "", ""
        prose = section.get("text", "")
        tables = "\n\n".join(_render_table(t) for t in section.get("tables", []))
        return prose, tables

    def _get_section_text(self, section_id: str) -> str | None:
        prose, tables = self._section_parts(section_id)
        text = prose + (f"\n\n{tables}" if tables else "")
        return text.strip() or None

    def _build_full_text(self) -> str:
        """Build full document text from content.json for Layer 4 fallback."""
        parts = []
        for sid in self._section_ids:
            text = self._get_section_text(sid)
            if text:
                entry = self._get_catalogue_entry(sid)
                title = entry.get("title", sid) if entry else sid
                parts.append(f"## {title}\n{text}")
        return "\n\n".join(parts)


# ------------------------------------------------------------------ #
#  LLM helper — thin wrapper over docnest.llm (LangChain backend)      #
# ------------------------------------------------------------------ #

def _llm_call(
    prompt: str,
    provider: str | ILLMProvider,
    model: str = "",
    api_key: str | None = None,
) -> str:
    """Route a query-time call through an ILLMProvider.

    Accepts either an ILLMProvider instance or legacy (provider, model, api_key)
    strings.  Returns a plain string — never raises — so a failed LLM call
    never crashes a query; the caller gets a bracketed error message instead.
    """
    try:
        if isinstance(provider, ILLMProvider):
            llm = provider
        else:
            llm = get_llm_provider(provider, model, api_key=api_key)
        return llm.complete(prompt=prompt, system="")
    except Exception as exc:
        label = (
            f"{provider.provider_name}/{provider.model_name}"
            if isinstance(provider, ILLMProvider)
            else f"{provider}/{model}"
        )
        return f"[LLM error ({label}): {exc}]"
