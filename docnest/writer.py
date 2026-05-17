"""
UDF Writer — Stage 6c of the DocNest pipeline.

Produces a .udf ZIP archive from a fully-enriched Document. The archive
contains three JSON files:

    manifest.json   — format version, embedding config, metadata
    catalogue.json  — section index with keywords, summaries, and
                      base64-encoded quantised embeddings (loaded into RAM)
    content.json    — full section texts, tables, images (lazy-loaded)

Phase: 4  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 11
           |  UDF format: docs/SPEC_UDF_FORMAT.md
Design pattern: Builder
"""

from __future__ import annotations
import base64
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docnest.models import Document, Catalogue
from docnest.embedder import IEmbedder
from docnest.quantizer import Quantizer
from docnest.exceptions import UDFWriteError

UDF_VERSION = "1.0"


class UDFWriter:
    """Builds a .udf zip file from a normalised, enriched Document.

    Usage:
        writer = UDFWriter(embedder=NomicEmbedder(), quantizer=Quantizer("float16"))
        path = writer.write(document, output_path="report.udf")
        # → report.udf  (ZIP with manifest, catalogue, content)
    """

    def __init__(self, embedder: IEmbedder, quantizer: Quantizer) -> None:
        self.embedder = embedder
        self.quantizer = quantizer

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def write(
        self,
        doc: Document,
        output_path: str,
        include_originals: bool = False,
    ) -> str:
        """Write a single Document to a .udf file.

        Steps:
          1. Embed all sections (batch call to embedder)
          2. Quantize each embedding → bytes → base64
          3. Build manifest, catalogue, content dicts
          4. Write to ZIP with DEFLATED compression

        Args:
            doc: Fully normalised Document (pipeline stages 1-5 complete).
            output_path: Destination .udf file path.
            include_originals: If True, embed source file in original/ folder.

        Returns:
            Absolute path to the created .udf file.

        Raises:
            UDFWriteError: If embedding, quantization, or file writing fails.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Batch embed all sections
            texts = [
                (s.summary or s.title + " " + s.text[:300]).strip()
                for s in doc.sections
            ]
            vectors = self.embedder.embed(texts) if texts else []

            # Step 2: Quantize embeddings and attach to sections
            import numpy as np
            for i, section in enumerate(doc.sections):
                if len(vectors) > i:
                    section.embedding = self.quantizer.quantize(vectors[i])

            # Step 3: Build JSON payloads
            manifest = self._build_manifest(doc)
            catalogue = self._build_catalogue(doc)
            content = self._build_content(doc)

            # Step 4: Write ZIP
            with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                zf.writestr("catalogue.json", json.dumps(catalogue, ensure_ascii=False, indent=2))
                zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
                # Write image assets (empty for now — populated by future image extraction)
                zf.mkdir("assets") if hasattr(zf, "mkdir") else None

        except UDFWriteError:
            raise
        except Exception as exc:
            raise UDFWriteError(f"Failed to write '{out.name}': {exc}") from exc

        return str(out.resolve())

    def write_library(self, docs: list[Document], output_path: str) -> str:
        """Write multiple Documents to a single library .udf file. (Phase 7)"""
        raise NotImplementedError("Library mode not yet implemented (Phase 7).")

    # ------------------------------------------------------------------ #
    #  Builders                                                            #
    # ------------------------------------------------------------------ #

    def _build_manifest(self, doc: Document) -> dict[str, Any]:
        """Build manifest.json — format version and embedding config."""
        return {
            "udf_version": UDF_VERSION,
            "doc_id": doc.doc_id,
            "title": doc.title,
            "source_format": doc.format,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": self.embedder.model_name,
            "embedding_dims": self.embedder.dims,
            "quantization": self.quantizer.mode,
            "section_count": len(doc.sections),
            "intelligence": True,
        }

    def _build_catalogue(self, doc: Document) -> dict[str, Any]:
        """Build catalogue.json — section index loaded into RAM on file open."""
        section_index = []
        for s in doc.sections:
            entry: dict[str, Any] = {
                "id": s.id,
                "title": s.title,
                "level": s.level,
                "parent_id": s.parent_id,
                "children": s.children,
                "summary": s.summary or "",
                "keywords": s.keywords,
                "token_count": s.token_count,
            }
            # Embed stored as base64-encoded bytes
            if s.embedding:
                entry["embedding"] = base64.b64encode(s.embedding).decode("ascii")
            section_index.append(entry)

        return {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "source": doc.source,
            "language": "en",
            "summary": doc.summary or "",
            "insights": doc.insights,
            "key_numbers": [
                {
                    "label": kn.label,
                    "value": kn.value,
                    "unit": kn.unit,
                    "section": kn.section,
                }
                for kn in doc.key_numbers
            ],
            "section_index": section_index,
            "embedding_model": self.embedder.model_name,
            "embedding_dims": self.embedder.dims,
            "quantization": self.quantizer.mode,
        }

    def _build_content(self, doc: Document) -> dict[str, Any]:
        """Build content.json — full section texts fetched lazily at query time."""
        sections: dict[str, Any] = {}
        for s in doc.sections:
            sections[s.id] = {
                "title": s.title,
                "level": s.level,
                "text": s.text,
                "tables": [
                    {
                        "table_id": t.table_id,
                        "caption": t.caption,
                        "headers": t.headers,
                        "rows": t.rows,
                    }
                    for t in s.tables
                ],
                "images": [
                    {
                        "image_id": img.image_id,
                        "alt": img.alt,
                        "asset_path": img.asset_path,
                    }
                    for img in s.images
                ],
            }
        return {"doc_id": doc.doc_id, "sections": sections}
