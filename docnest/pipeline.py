"""
DocNestPipeline — orchestrates all 6 stages of document normalisation.

Main entry point for programmatic use. The CLI and all integrations
(SynapseKB, desktop app) go through this class.

Stage 1  Parse          → ParserFactory selects and runs the right parser
Stage 2  Normalise      → SectionNormaliser assigns §ids and links hierarchy
Stage 3  Table norm     → Handled inside SectionNormaliser (column normalisation)
Stage 4  Summarise      → IntelligenceEngine: one sentence per section + keywords
Stage 5  Enrich doc     → IntelligenceEngine: summary, insights, key_numbers
Stage 6  Embed + quant  → Embedder generates vectors, Quantizer compresses
         Write          → UDFWriter packs everything into a .udf ZIP

Phase: 1-6  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 11
Design pattern: Pipeline + Dependency Inversion (all deps injected, fully testable)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from docnest.models import Document, DocMeta
from docnest.parsers.factory import ParserFactory
from docnest.normalizer import SectionNormaliser
from docnest.intelligence import IntelligenceEngine
from docnest.embedder import IEmbedder
from docnest.quantizer import Quantizer
from docnest.writer import UDFWriter
from docnest.exceptions import DOCNESTError, ParseError
from docnest.providers.llm import ILLMProvider, get_llm_provider
from docnest.providers.search import ISearchProvider, get_search_provider
from docnest.providers.storage import IStorageBackend, get_storage_backend

# Callback type: (stage_name, stage_output) — used for progress bars in CLI
StageCallback = Callable[[str, object], None]

_NOOP: StageCallback = lambda stage, data: None


class DocNestPipeline:
    """Orchestrates the complete 6-stage document normalisation pipeline.

    All dependencies are injected — the pipeline is fully testable with mocks.

    Usage (defaults — fully local, free):
        pipeline = DocNestPipeline()
        pipeline.convert("report.pdf")        # → report.udf
        pipeline.convert("./reports/")        # → reports.udf (library, Phase 7)

    Usage (custom config):
        pipeline = DocNestPipeline(
            embedder=OpenAIEmbedder(api_key="sk-..."),
            quantization="int8",
            llm_provider="groq",
            llm_model="llama3-70b-8192",
        )

    Usage (skip intelligence — faster, no LLM required):
        pipeline = DocNestPipeline(skip_intelligence=True)
    """

    def __init__(
        self,
        # ── LLM — string config OR pre-built ILLMProvider instance ───────────
        llm_provider: str | ILLMProvider = "groq",
        llm_model: str = "llama-3.3-70b-versatile",
        llm_api_key: str | None = None,
        # ── Embeddings — string config OR pre-built IEmbedder instance ───────
        emb_provider: str = "huggingface",
        emb_model: str = "all-MiniLM-L6-v2",
        emb_api_key: str | None = None,
        # ── Pipeline options ─────────────────────────────────────────────────
        quantization: str = "float16",
        on_stage_complete: Optional[StageCallback] = None,
        size_limit_mb: int = 200,
        skip_intelligence: bool = False,
        # ── Provider overrides — pass pre-built objects to bypass string config
        storage: Optional[IStorageBackend] = None,
        search: Optional[ISearchProvider] = None,
        # ── Legacy — kept for backward compatibility ──────────────────────────
        embedder: Optional[IEmbedder] = None,
    ) -> None:
        """Initialise the pipeline.

        Both LLM and embeddings follow the same three-param pattern:
            (provider, model, api_key)
        api_key is always optional — falls back to the provider's env var,
        or can be omitted entirely for local providers (ollama, huggingface).

        Args:
            llm_provider:  LLM provider name — groq, openai, ollama, anthropic,
                           google, bedrock, mistral, together, cohere, etc.
            llm_model:     Model identifier for the LLM provider.
            llm_api_key:   LLM API key (optional — uses env var if not set).
                           Not needed for ollama.
            emb_provider:  Embedding provider — huggingface, openai, ollama,
                           google, cohere, bedrock, nvidia, mistral.
            emb_model:     Model identifier for the embedding provider.
            emb_api_key:   Embedding API key (optional — uses env var if set).
                           Not needed for huggingface (local) or ollama.
            quantization:  Vector compression — float32, float16, int8, binary.
            on_stage_complete: Optional callback(stage_name, data) for progress.
            size_limit_mb: Maximum .udf output file size in MB (default 200).
            skip_intelligence: Skip LLM enrichment stages — faster, no key needed.
            embedder:      Legacy: pass a pre-built IEmbedder instance directly.
                           Overrides emb_provider/emb_model/emb_api_key.

        Examples:
            # Groq LLM + local HuggingFace embeddings (recommended quickstart)
            DocNestPipeline(
                llm_provider="groq", llm_model="llama-3.3-70b-versatile",
                llm_api_key="gsk_...",
                emb_provider="huggingface", emb_model="all-MiniLM-L6-v2",
            )

            # OpenAI for both LLM and embeddings
            DocNestPipeline(
                llm_provider="openai", llm_model="gpt-4o-mini",
                llm_api_key="sk-...",
                emb_provider="openai", emb_model="text-embedding-3-small",
                emb_api_key="sk-...",
            )

            # Fully local — no API keys, no internet after first download
            DocNestPipeline(
                llm_provider="ollama", llm_model="llama3.2",
                emb_provider="huggingface", emb_model="all-MiniLM-L6-v2",
                skip_intelligence=False,
            )
        """
        from docnest.embedder import LangChainEmbedder

        self.parser_factory = ParserFactory()
        self.normaliser     = SectionNormaliser()

        # ── LLM provider ──────────────────────────────────────────────────────
        # Accept ILLMProvider instance OR (provider, model, api_key) strings.
        if isinstance(llm_provider, ILLMProvider):
            llm = llm_provider
        else:
            llm = get_llm_provider(llm_provider, llm_model, api_key=llm_api_key)

        self.intelligence = IntelligenceEngine(provider=llm)

        # ── Embedder ──────────────────────────────────────────────────────────
        # embedder kwarg takes precedence (backward compat); otherwise build from config
        self.embedder = embedder or LangChainEmbedder(
            provider=emb_provider,
            model=emb_model,
            api_key=emb_api_key,
        )

        # ── Storage + search providers ────────────────────────────────────────
        self._storage = storage or get_storage_backend("zip")
        self._search  = search  or get_search_provider("auto")

        self.quantizer = Quantizer(mode=quantization)
        self.writer    = UDFWriter(self.embedder, self.quantizer, storage=self._storage)
        self.on_stage_complete = on_stage_complete or _NOOP
        self.size_limit_bytes  = size_limit_mb * 1_000_000
        self.skip_intelligence = skip_intelligence

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def process(self, file_path: str) -> Document:
        """Run the full pipeline on a single document file.

        Args:
            file_path: Absolute or relative path to the source document.

        Returns:
            Fully normalised Document with §ids, summaries, insights,
            embeddings, and key_numbers.

        Raises:
            ParseError: If no parser supports the file format.
            DOCNESTError: If any pipeline stage fails.
        """
        path = Path(file_path)

        # ── Stage 1: Parse ──────────────────────────────────────────────
        parser = self.parser_factory.get(str(path))
        raw = parser.parse(str(path))
        self.on_stage_complete("parse", raw)

        # ── Stage 2: Normalise (§id assignment + table normalisation) ───
        doc = self.normaliser.normalise(raw)
        self.on_stage_complete("normalise", doc)

        if not self.skip_intelligence:
            # ── Stage 4: Section summaries + keywords ───────────────────
            doc = self.intelligence.enrich_sections(doc)
            self.on_stage_complete("enrich_sections", doc)

            # ── Stage 5: Document-level intelligence ────────────────────
            doc = self.intelligence.enrich_document(doc)
            self.on_stage_complete("enrich_document", doc)

        # ── Stage 5b: Deterministic intelligence (no LLM) ────────────────
        # Populate key_numbers by extraction so Layer 0 (0-token) works even when LLM
        # enrichment is skipped/unavailable. No-op if key_numbers already populated.
        from docnest.key_numbers import enrich_key_numbers
        enrich_key_numbers(doc)

        # ── Stage 6: Embed + quantize ────────────────────────────────────
        # (Embeddings are attached to sections inside UDFWriter.write())
        self.on_stage_complete("embed", doc)

        return doc

    def convert(
        self,
        source: str,
        output: Optional[str] = None,
        include_originals: bool = False,
        meta: Optional[DocMeta] = None,
        include_source_path: bool = False,
    ) -> str:
        """Convert a document or folder to a .udf file.

        Args:
            source: Path to a file or directory.
            output: Output .udf path. Defaults to source with .udf extension.
            include_originals: Embed source files inside the .udf archive.
            meta: Optional DocMeta with owner, department, tags, etc.
            include_source_path: If True, store the full original path in the .udf.
                Default False stores only the basename (privacy-safe, portable).

        Returns:
            Absolute path to the created .udf file.

        Raises:
            DOCNESTError: If processing or writing fails.
        """
        path = Path(source)
        if path.is_dir():
            return self._convert_folder(path, output, include_originals)

        doc = self.process(source)
        if meta:
            doc.meta = meta
        out_path = output or str(path.with_suffix(".udf"))
        result = self.writer.write(doc, out_path, include_originals, include_source_path)
        self.on_stage_complete("write", result)
        return result

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _convert_folder(
        self,
        folder: Path,
        output: Optional[str],
        include_originals: bool,
    ) -> str:
        """Convert all supported documents in a folder to a library .udf.

        Phase 7 — library mode. Each supported file becomes one Document
        in the combined library archive.
        """
        docs: list[Document] = []
        errors: list[str] = []

        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            if not self.parser_factory.supports(f):
                continue
            try:
                docs.append(self.process(str(f)))
            except DOCNESTError as exc:
                errors.append(f"{f.name}: {exc}")

        if not docs:
            raise DOCNESTError(
                f"No supported documents found in '{folder}'. "
                f"Errors: {errors or 'none'}"
            )

        out_path = output or str(folder.parent / f"{folder.name}.udf")
        result = self.writer.write_library(docs, out_path)
        self.on_stage_complete("write_library", result)
        return result
