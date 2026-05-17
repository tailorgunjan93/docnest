"""
DOCNESTPipeline — orchestrates all 6 stages of document normalisation.

This is the main entry point for programmatic use. The CLI and all
integrations (SynapseKB, Synapse Local) go through this class.

Stage 1  Parse          → ParserFactory selects and runs the right parser
Stage 2  Normalise      → SectionNormaliser assigns §ids and links hierarchy
Stage 3  Table norm     → IntelligenceEngine verifies/fixes table structure
Stage 4  Summarise      → IntelligenceEngine writes one sentence per section
Stage 5  Enrich doc     → IntelligenceEngine writes summary, insights, key_numbers
Stage 6  Embed + quant  → Embedder generates vectors, Quantizer compresses

Phase: 1-6  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 11
Design pattern: Pipeline + Dependency Inversion (all deps injected)
"""

from __future__ import annotations
from pathlib import Path
from typing import Callable

from DOCNEST.models import Document
from DOCNEST.parsers.factory import ParserFactory
from DOCNEST.normalizer import SectionNormaliser
from DOCNEST.intelligence import IntelligenceEngine
from DOCNEST.embedder import IEmbedder, NomicEmbedder
from DOCNEST.quantizer import Quantizer
from DOCNEST.writer import UDFWriter
from DOCNEST.exceptions import DOCNESTError


# Callback type: called after each stage completes
StageCallback = Callable[[str, object], None]


class DOCNESTPipeline:
    """Orchestrates the complete 6-stage document normalisation pipeline.

    All dependencies are injected — the pipeline is fully testable with mocks.

    Usage (defaults — fully local, free):
        pipeline = DOCNESTPipeline()
        pipeline.convert("report.pdf")                      # → report.udf
        pipeline.convert("./reports/")                      # → reports.udf (library)

    Usage (custom config):
        pipeline = DOCNESTPipeline(
            embedder=OpenAIEmbedder(api_key="sk-..."),
            quantization="int8",
            llm_provider="groq",
            llm_model="llama3-70b-8192",
        )
    """

    def __init__(
        self,
        embedder: IEmbedder | None = None,
        quantization: str = "float16",
        llm_provider: str = "ollama",
        llm_model: str = "llama3.2",
        on_stage_complete: StageCallback | None = None,
        size_limit_mb: int = 200,
    ) -> None:
        """Initialise the pipeline with injected dependencies.

        Args:
            embedder: Embedding provider. Defaults to NomicEmbedder (local, free).
            quantization: Compression mode — float32, float16, int8, binary.
            llm_provider: LLM provider for intelligence stages.
            llm_model: Model name for the provider.
            on_stage_complete: Optional callback(stage_name, data) for progress tracking.
            size_limit_mb: Maximum .udf output size in megabytes.
        """
        self.parser_factory = ParserFactory()
        self.normaliser = SectionNormaliser()
        self.intelligence = IntelligenceEngine(provider=llm_provider, model=llm_model)
        self.embedder = embedder or NomicEmbedder()
        self.quantizer = Quantizer(mode=quantization)
        self.writer = UDFWriter(self.embedder, self.quantizer)
        self.on_stage_complete = on_stage_complete or (lambda stage, data: None)
        self.size_limit_bytes = size_limit_mb * 1_000_000

    def process(self, file_path: str) -> Document:
        """Run the full 6-stage pipeline on a single document.

        Args:
            file_path: Absolute or relative path to the source document.

        Returns:
            Fully normalised Document with §ids, summaries, insights, and embeddings.

        Raises:
            DOCNESTError: If any pipeline stage fails.

        TODO (as each phase is implemented, uncomment the relevant stage):
        """
        # Stage 1 — Parse
        # parser = self.parser_factory.get(file_path)
        # raw = parser.parse(file_path)
        # self.on_stage_complete("parse", raw)

        # Stage 2 — Normalise (§id assignment)
        # doc = self.normaliser.normalise(raw)
        # self.on_stage_complete("normalise", doc)

        # Stage 3 + 4 — Table normalisation + section summaries
        # doc = self.intelligence.enrich_sections(doc)
        # self.on_stage_complete("enrich_sections", doc)

        # Stage 5 — Document intelligence
        # doc = self.intelligence.enrich_document(doc)
        # self.on_stage_complete("enrich_document", doc)

        # Stage 6 — Embed + quantise
        # texts = [s.summary or s.text[:500] for s in doc.sections]
        # vectors = self.embedder.embed(texts)
        # for i, section in enumerate(doc.sections):
        #     section.embedding = self.quantizer.quantize(vectors[i])
        # self.on_stage_complete("embed", doc)

        # return doc
        raise NotImplementedError(
            "Pipeline stages not yet implemented. "
            "See ROADMAP.md — implement Phase 1 parsers first."
        )

    def convert(self, source: str, output: str | None = None, include_originals: bool = False) -> str:
        """Convert a document or folder to a .udf file.

        Args:
            source: Path to a file or directory.
            output: Output .udf path. Defaults to source path with .udf extension.
            include_originals: Embed source files inside the .udf.

        Returns:
            Path to the created .udf file.

        Raises:
            DOCNESTError: If processing or writing fails.
        """
        path = Path(source)
        if path.is_dir():
            return self._convert_folder(path, output, include_originals)
        doc = self.process(source)
        out_path = output or str(path.with_suffix(".udf"))
        return self.writer.write(doc, out_path, include_originals)

    def _convert_folder(self, folder: Path, output: str | None, include_originals: bool) -> str:
        """Convert all supported documents in a folder to a library .udf."""
        docs = []
        for f in sorted(folder.rglob("*")):
            if f.is_file() and self.parser_factory.supports(f):
                docs.append(self.process(str(f)))
        out_path = output or str(folder.parent / f"{folder.name}.udf")
        return self.writer.write_library(docs, out_path)
