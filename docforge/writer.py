"""
UDF Writer — produces .udf zip files from normalised Documents.

A .udf file is a ZIP archive containing:
    manifest.json    — format version, embedding model, quantisation config
    catalogue.json   — section index, BM25 keywords, quantised embeddings, intelligence
    content.json     — full section text (fetched on demand at query time)
    assets/          — images and extracted tables
    original/        — source file (optional, --include-originals flag)

Phase: 4  |  Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 11
           |  UDF format: docs/SPEC_UDF_FORMAT.md (full field reference)
Design pattern: Builder — builds the zip incrementally.
"""

from __future__ import annotations
import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone

from docforge.models import Document, Catalogue
from docforge.embedder import IEmbedder
from docforge.quantizer import Quantizer
from docforge.exceptions import UDFWriteError

UDF_VERSION = "1.0"


class UDFWriter:
    """Builds a .udf zip file from a normalised Document.

    Usage:
        writer = UDFWriter(embedder=NomicEmbedder(), quantizer=Quantizer("float16"))
        writer.write(document, output_path="report.udf")
        writer.write_library(documents, output_path="library.udf")  # Phase 7
    """

    def __init__(self, embedder: IEmbedder, quantizer: Quantizer) -> None:
        self.embedder = embedder
        self.quantizer = quantizer

    def write(self, doc: Document, output_path: str, include_originals: bool = False) -> str:
        """Write a single Document to a .udf file.

        Args:
            doc: Fully normalised Document (all pipeline stages complete).
            output_path: Destination .udf file path.
            include_originals: If True, embed the source file in original/.

        Returns:
            Absolute path to the created .udf file.

        Raises:
            UDFWriteError: If writing fails.

        TODO (Phase 4):
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(self._build_manifest(doc)))
                zf.writestr("catalogue.json", json.dumps(self._build_catalogue(doc)))
                zf.writestr("content.json", json.dumps(self._build_content(doc)))
        """
        raise NotImplementedError("UDFWriter.write not yet implemented.")

    def write_library(self, docs: list[Document], output_path: str) -> str:
        """Write multiple Documents to a single library .udf file.

        Phase 7 feature — folder → library mode.

        TODO (Phase 7):
            Build library_catalogue.json with unified_section_index
            Write each doc's catalogue.json + content.json under documents/{doc_id}/
        """
        raise NotImplementedError("UDFWriter.write_library not yet implemented (Phase 7).")

    def _build_manifest(self, doc: Document) -> dict:
        """Build the manifest.json content."""
        # TODO: See docs/SPEC_UDF_FORMAT.md Section 5 for full field spec
        raise NotImplementedError

    def _build_catalogue(self, doc: Document) -> dict:
        """Build the catalogue.json content with section index and embeddings."""
        # TODO: See docs/SPEC_UDF_FORMAT.md Section 6 for full field spec
        raise NotImplementedError

    def _build_content(self, doc: Document) -> dict:
        """Build the content.json with full section texts."""
        # TODO: See docs/SPEC_UDF_FORMAT.md Section 7 for full field spec
        raise NotImplementedError
