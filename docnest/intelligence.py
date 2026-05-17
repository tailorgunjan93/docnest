"""
Intelligence Engine — Stages 3, 4, and 5 of the DocNest pipeline.

Uses an LLM (via LiteLLM) to enrich documents with:
  Stage 3: Table normalisation verification
  Stage 4: One-sentence summary + keywords per section
  Stage 5: Document-level summary, insights[], key_numbers[]

LLM calls happen ONCE per document at ingest time.
Every future query benefits for free — zero extra tokens per query.

Phase: 3  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
import json
import re
from typing import Any

from docnest.models import Document, Section, KeyNumber
from docnest.exceptions import IntelligenceError

# System prompt used for all intelligence calls
_SYSTEM = (
    "You are a precise document analyst. "
    "Return ONLY the requested format — no preamble, no explanation."
)

# Max chars to send per section (keeps cost low, avoids context overflow)
_MAX_SECTION_CHARS = 2000
# Max chars of combined summaries to send for document-level enrichment
_MAX_DOC_CONTEXT_CHARS = 8000


class IntelligenceEngine:
    """LLM-powered document enrichment via LiteLLM.

    Supports any LLM provider through LiteLLM's unified interface:
        ollama    — fully local, free (default; needs Ollama running locally)
        groq      — fast, cheap API ($0.01 per 100-page doc)
        openai    — highest quality (~$0.05 per 100-page doc)
        anthropic — also supported via LiteLLM

    Usage:
        engine = IntelligenceEngine(provider="ollama", model="llama3.2")
        doc = engine.enrich_sections(doc)   # Stage 4: per-section summaries
        doc = engine.enrich_document(doc)   # Stage 5: doc-level intelligence
    """

    def __init__(self, provider: str = "ollama", model: str = "llama3.2") -> None:
        self.provider = provider
        self.model = model

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def enrich_sections(self, doc: Document) -> Document:
        """Stage 4: Generate one-sentence summary + keywords per section.

        Skips sections with fewer than 20 words (too short to summarise).

        Args:
            doc: Document with normalised sections.

        Returns:
            Document with section.summary and section.keywords filled.
        """
        for section in doc.sections:
            if len(section.text.split()) < 20:
                section.summary = section.title
                section.keywords = section.title.lower().split()[:5]
                continue
            try:
                section.summary = self._summarise_section(section)
                section.keywords = self._extract_keywords(section)
            except IntelligenceError:
                # Graceful degradation — skip enrichment for this section
                section.summary = section.title
                section.keywords = []
        return doc

    def enrich_document(self, doc: Document) -> Document:
        """Stage 5: Generate document-level summary, insights, key_numbers.

        Builds a compressed context from all section summaries (not full text)
        to keep LLM costs low, then requests JSON output.

        Args:
            doc: Document with section summaries already filled.

        Returns:
            Document with summary, insights, and key_numbers populated.
        """
        context = self._build_doc_context(doc)
        try:
            result = self._call_doc_intelligence(context, doc.title)
            doc.summary = result.get("summary", "")
            doc.insights = result.get("insights", [])
            raw_kn = result.get("key_numbers", [])
            doc.key_numbers = [
                KeyNumber(
                    label=kn.get("label", ""),
                    value=kn.get("value", ""),
                    unit=kn.get("unit"),
                    section=kn.get("section", "§1"),
                )
                for kn in raw_kn
                if kn.get("label") and kn.get("value")
            ]
        except IntelligenceError:
            doc.summary = f"Document: {doc.title}"
            doc.insights = []
            doc.key_numbers = []
        return doc

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _summarise_section(self, section: Section) -> str:
        """Generate a one-sentence summary of a section."""
        text = section.text[:_MAX_SECTION_CHARS]
        prompt = (
            f"Summarise the following section titled '{section.title}' "
            f"in exactly ONE sentence (max 150 characters):\n\n{text}"
        )
        return self._call_llm(prompt).strip()[:200]

    def _extract_keywords(self, section: Section) -> list[str]:
        """Extract 5-8 BM25 index keywords from a section."""
        text = (section.summary or section.title) + " " + section.text[:500]
        prompt = (
            f"Extract 5 to 8 important keywords from this text for a search index. "
            f"Return ONLY a JSON array of lowercase strings, e.g. [\"revenue\", \"q3\"]:\n\n{text}"
        )
        raw = self._call_llm(prompt).strip()
        try:
            keywords = json.loads(_extract_json(raw))
            if isinstance(keywords, list):
                return [str(k).lower() for k in keywords[:10]]
        except Exception:
            pass
        # Fallback: split summary into words
        return [w.lower() for w in (section.summary or section.title).split()[:6]]

    def _build_doc_context(self, doc: Document) -> str:
        """Build a compressed context string from section summaries."""
        parts = [f"Document: {doc.title}\n"]
        total = len(parts[0])
        for section in doc.sections:
            line = f"{section.id} {section.title}: {section.summary or section.text[:100]}\n"
            if total + len(line) > _MAX_DOC_CONTEXT_CHARS:
                break
            parts.append(line)
            total += len(line)
        return "".join(parts)

    def _call_doc_intelligence(self, context: str, title: str) -> dict[str, Any]:
        """Call LLM for document-level intelligence. Returns parsed JSON dict."""
        prompt = (
            f"Analyse this document summary and return a JSON object with exactly these fields:\n"
            f'{{"summary": "3-sentence summary", '
            f'"insights": ["finding1", "finding2", "finding3"], '
            f'"key_numbers": [{{"label": "Revenue", "value": "$142M", "unit": "USD", "section": "§2.1"}}]}}\n\n'
            f"Document sections:\n{context}"
        )
        raw = self._call_llm(prompt)
        try:
            return json.loads(_extract_json(raw))
        except Exception as exc:
            raise IntelligenceError(
                f"Failed to parse document intelligence JSON: {exc}\nRaw: {raw[:200]}"
            ) from exc

    def _call_llm(self, prompt: str) -> str:
        """Make a single LLM call via LiteLLM.

        Args:
            prompt: User message.

        Returns:
            LLM response text.

        Raises:
            IntelligenceError: If the LLM call fails.
        """
        try:
            import litellm  # type: ignore[import]
            litellm.set_verbose = False  # type: ignore[attr-defined]
        except ImportError as exc:
            raise IntelligenceError(
                "litellm not installed. Run: pip install litellm"
            ) from exc

        # Build model string understood by LiteLLM
        if self.provider == "ollama":
            model_str = f"ollama/{self.model}"
        elif self.provider == "openai":
            model_str = self.model  # e.g. "gpt-4o-mini"
        elif self.provider == "groq":
            model_str = f"groq/{self.model}"
        elif self.provider == "anthropic":
            model_str = f"anthropic/{self.model}"
        else:
            model_str = f"{self.provider}/{self.model}"

        try:
            response = litellm.completion(
                model=model_str,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise IntelligenceError(
                f"LLM call failed ({model_str}): {exc}"
            ) from exc


def _extract_json(text: str) -> str:
    """Extract the first JSON object or array from an LLM response string."""
    # Try to find JSON wrapped in code block
    m = re.search(r"```(?:json)?\s*([\[{].*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Try to find raw JSON object or array
    m = re.search(r"([\[{].*[\]}])", text, re.DOTALL)
    if m:
        return m.group(1)
    return text.strip()
