"""
Intelligence Engine — Stages 3, 4, and 5 of the DocForge pipeline.

Uses an LLM to enrich documents with:
  Stage 3: Table normalisation (verify/fix column structure)
  Stage 4: One-sentence summary per section
  Stage 5: Document-level summary, insights[], key_numbers[]

LLM calls happen ONCE per document at ingest time.
Every future query benefits for free — this is the core cost advantage.

Phase: 3  |  Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 10
"""

from __future__ import annotations
from docforge.models import Document, Section, KeyNumber


class IntelligenceEngine:
    """LLM-powered document enrichment via LiteLLM.

    Supports any LLM provider through LiteLLM's unified interface:
        ollama  — fully local, free (recommended for privacy)
        groq    — fast, cheap ($0.01 per 100-page doc)
        openai  — highest quality (~$0.05 per 100-page doc)
        anthropic, google — also supported

    TODO (Phase 3):
        import litellm
        litellm.set_verbose = False
    """

    def __init__(self, provider: str = "ollama", model: str = "llama3.2") -> None:
        """Initialise the intelligence engine.

        Args:
            provider: LLM provider — 'ollama', 'groq', 'openai', 'anthropic', 'google'
            model: Model name as understood by LiteLLM, e.g. 'ollama/llama3.2'
        """
        self.provider = provider
        self.model = model
        # TODO: validate provider + model combination using litellm

    def enrich_sections(self, doc: Document) -> Document:
        """Stage 4: Generate one-sentence summary per section.

        Args:
            doc: Document with sections (text already extracted).

        Returns:
            Document with section.summary filled for every section.
        """
        # TODO (Phase 3):
        # For each section, call LLM with prompt:
        #   "Summarise this section in one sentence (max 150 chars): {section.text[:1000]}"
        # Set section.summary = response
        raise NotImplementedError("IntelligenceEngine.enrich_sections not yet implemented.")

    def enrich_document(self, doc: Document) -> Document:
        """Stage 5: Generate document-level intelligence.

        Fills:
            doc.summary    — three-sentence document summary
            doc.insights   — 3-5 non-obvious findings
            doc.key_numbers — all metrics with §citation

        Args:
            doc: Document with section summaries already filled.

        Returns:
            Document with summary, insights, and key_numbers populated.
        """
        # TODO (Phase 3):
        # Build context from all section summaries (not full text — cheaper)
        # Call LLM with structured prompt requesting JSON output:
        #   { "summary": "...", "insights": [...], "key_numbers": [...] }
        # Parse JSON response into Document fields
        raise NotImplementedError("IntelligenceEngine.enrich_document not yet implemented.")

    def _call_llm(self, prompt: str, system: str | None = None) -> str:
        """Make a single LLM call via LiteLLM.

        Args:
            prompt: User message.
            system: Optional system prompt.

        Returns:
            LLM response text.

        Raises:
            IntelligenceError: If the LLM call fails.
        """
        # TODO (Phase 3):
        # import litellm
        # model_str = f"{self.provider}/{self.model}" if self.provider == "ollama" else self.model
        # response = litellm.completion(model=model_str, messages=[...])
        # return response.choices[0].message.content
        raise NotImplementedError
