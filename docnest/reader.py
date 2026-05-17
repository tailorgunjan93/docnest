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
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from docnest.models import Catalogue, KeyNumber
from docnest.quantizer import Quantizer
from docnest.exceptions import UDFReadError, IntelligenceError

UDF_VERSION = "1.0"

# Thresholds for escalation
_L1_SCORE_THRESHOLD = 0.35   # hybrid BM25+cosine score above this → Layer 1 answer
_L2_SCORE_THRESHOLD = 0.15   # above this → Layer 2 (single section LLM)
# Keywords that trigger Layer 0 pre-computed answers
_SUMMARY_KEYWORDS = {"summarise", "summarize", "summary", "what is this", "overview", "about"}
_INSIGHT_KEYWORDS = {"insight", "finding", "key finding", "takeaway", "conclusion"}


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
    ) -> None:
        self._catalogue = catalogue
        self._content = content
        self._zip_path = zip_path
        self._quantizer = Quantizer(quantization)
        self._dims = embedding_dims

        # Build BM25 index from section keywords
        self._section_ids: list[str] = []
        self._embeddings: list[np.ndarray] = []
        self._bm25: object | None = None
        self._build_index()

    # ------------------------------------------------------------------ #
    #  Class method: load                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, udf_path: str) -> "UDFIndex":
        """Load a .udf file and return a queryable UDFIndex.

        Args:
            udf_path: Path to the .udf file.

        Returns:
            UDFIndex ready to query.

        Raises:
            UDFReadError: If the file is missing, invalid, or wrong version.
        """
        path = Path(udf_path)
        if not path.exists():
            raise UDFReadError(f"UDF file not found: {udf_path}")

        try:
            with zipfile.ZipFile(str(path), "r") as zf:
                names = zf.namelist()
                if "manifest.json" not in names:
                    raise UDFReadError(f"Invalid .udf — missing manifest.json: {udf_path}")

                manifest = json.loads(zf.read("manifest.json"))
                version = manifest.get("udf_version", "?")
                if version != UDF_VERSION:
                    raise UDFReadError(
                        f"Unsupported .udf version '{version}'. Expected '{UDF_VERSION}'."
                    )

                catalogue = json.loads(zf.read("catalogue.json"))
                content = json.loads(zf.read("content.json"))

        except UDFReadError:
            raise
        except Exception as exc:
            raise UDFReadError(f"Failed to open '{udf_path}': {exc}") from exc

        return cls(
            catalogue=catalogue,
            content=content,
            zip_path=str(path.resolve()),
            quantization=manifest.get("quantization", "float16"),
            embedding_dims=manifest.get("embedding_dims", 768),
        )

    # ------------------------------------------------------------------ #
    #  Public query API                                                    #
    # ------------------------------------------------------------------ #

    def query(
        self,
        question: str,
        llm_provider: str = "ollama",
        llm_model: str = "llama3.2",
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
                        question, top_id, section_text, llm_provider, llm_model
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
                    question, sections, llm_provider, llm_model
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
        answer, tokens = self._call_llm_full(question, full_text, llm_provider, llm_model)
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
        """Build BM25 index and decode embeddings from catalogue."""
        section_index = self._catalogue.get("section_index", [])
        tokenised_corpus: list[list[str]] = []

        for entry in section_index:
            sid = entry.get("id", "")
            self._section_ids.append(sid)

            # Decode embedding
            emb_b64 = entry.get("embedding")
            if emb_b64:
                try:
                    emb_bytes = base64.b64decode(emb_b64)
                    vec = self._quantizer.dequantize(emb_bytes, self._dims)
                    self._embeddings.append(vec)
                except Exception:
                    self._embeddings.append(np.zeros(self._dims, dtype=np.float32))
            else:
                self._embeddings.append(np.zeros(self._dims, dtype=np.float32))

            # Tokenise keywords + title for BM25
            keywords = entry.get("keywords", [])
            title_tokens = entry.get("title", "").lower().split()
            tokens = list(set(keywords + title_tokens))
            tokenised_corpus.append(tokens)

        # Build BM25 index
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import]
            if tokenised_corpus:
                self._bm25 = BM25Okapi(tokenised_corpus)
        except ImportError:
            pass  # BM25 scoring will be skipped — cosine only

    # ------------------------------------------------------------------ #
    #  Search                                                              #
    # ------------------------------------------------------------------ #

    def _hybrid_search(self, question: str) -> list[tuple[str, float]]:
        """BM25 + cosine similarity hybrid search. Returns [(§id, score)] sorted desc."""
        if not self._section_ids:
            return []

        tokens = question.lower().split()
        n = len(self._section_ids)

        # BM25 scores
        bm25_scores = np.zeros(n, dtype=np.float32)
        if self._bm25 is not None:
            try:
                scores = self._bm25.get_scores(tokens)  # type: ignore[attr-defined]
                bm25_max = float(np.max(scores)) + 1e-8
                bm25_scores = np.array(scores, dtype=np.float32) / bm25_max
            except Exception:
                pass

        # Cosine similarity scores (only if query can be embedded)
        cosine_scores = np.zeros(n, dtype=np.float32)
        # Note: at query time we use keyword tokens for cosine approximation
        # Full cosine requires an embedder — pass one in for production use.
        # For now, cosine is derived from keyword overlap as a proxy.
        for i, entry_id in enumerate(self._section_ids):
            entry = self._get_catalogue_entry(entry_id)
            if entry:
                kw = set(entry.get("keywords", []))
                tok_set = set(tokens)
                if kw and tok_set:
                    overlap = len(kw & tok_set) / max(len(kw | tok_set), 1)
                    cosine_scores[i] = float(overlap)

        # Hybrid: equal weight
        hybrid = 0.5 * bm25_scores + 0.5 * cosine_scores
        order = np.argsort(hybrid)[::-1]
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
        provider: str,
        model: str,
    ) -> tuple[str, int]:
        """Layer 2: single section answer."""
        prompt = (
            f"Answer the question using ONLY the section below. "
            f"If the answer is not in the section, say 'Not found in {section_id}'.\n\n"
            f"Section {section_id}:\n{section_text[:2000]}\n\n"
            f"Question: {question}"
        )
        answer = _llm_call(prompt, provider, model)
        tokens = len(prompt.split()) + len(answer.split())
        return answer, tokens

    def _call_llm_multi(
        self,
        question: str,
        sections: dict[str, str],
        provider: str,
        model: str,
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
        answer = _llm_call(prompt, provider, model)
        tokens = len(prompt.split()) + len(answer.split())
        return answer, tokens

    def _call_llm_full(
        self,
        question: str,
        full_text: str,
        provider: str,
        model: str,
    ) -> tuple[str, int]:
        """Layer 4: full document fallback."""
        prompt = (
            f"Using the document below, answer: {question}\n\n"
            f"Document:\n{full_text[:6000]}"
        )
        answer = _llm_call(prompt, provider, model)
        tokens = len(prompt.split()) + len(answer.split())
        return answer, tokens

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_catalogue_entry(self, section_id: str) -> dict[str, Any] | None:
        for entry in self._catalogue.get("section_index", []):
            if entry.get("id") == section_id:
                return entry
        return None

    def _get_section_text(self, section_id: str) -> str | None:
        section = self.get_section(section_id)
        if not section:
            return None
        text = section.get("text", "")
        for table in section.get("tables", []):
            headers = " | ".join(table.get("headers", []))
            rows = "\n".join(" | ".join(row) for row in table.get("rows", [])[:5])
            text += f"\n\nTable {table.get('table_id', '')}:\n{headers}\n{rows}"
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
#  LiteLLM helper                                                      #
# ------------------------------------------------------------------ #

def _llm_call(prompt: str, provider: str, model: str) -> str:
    """Thin LiteLLM wrapper used by reader layers 2-4."""
    try:
        import litellm  # type: ignore[import]
        litellm.set_verbose = False  # type: ignore[attr-defined]
    except ImportError:
        return "[LLM unavailable — install litellm]"

    if provider == "ollama":
        model_str = f"ollama/{model}"
    elif provider == "openai":
        model_str = model
    elif provider == "groq":
        model_str = f"groq/{model}"
    else:
        model_str = f"{provider}/{model}"

    try:
        response = litellm.completion(
            model=model_str,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"[LLM error: {exc}]"
