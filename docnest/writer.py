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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docnest.models import Document, Catalogue, DocMeta
from docnest.embedder import IEmbedder
from docnest.quantizer import Quantizer
from docnest.exceptions import UDFWriteError
from docnest.providers.storage import IStorageBackend, ZipStorageBackend

UDF_VERSION = "1.0"

# Compact JSON separators — removes all whitespace (saves 15-20% vs indent=2)
# Human-readable output is handled by `docnest view` (HTML) and `docnest inspect` (CLI)
_JSON_SEP = (',', ':')


class UDFWriter:
    """Builds a .udf archive from a normalised, enriched Document.

    Usage::

        writer = UDFWriter(embedder, Quantizer("float16"))
        path = writer.write(document, output_path="report.udf")

        # Use a directory backend for easy debugging
        from docnest.providers.storage import get_storage_backend
        writer = UDFWriter(embedder, Quantizer("float16"),
                           storage=get_storage_backend("dir"))
    """

    def __init__(
        self,
        embedder: IEmbedder | None = None,
        quantizer: Quantizer | None = None,
        storage: IStorageBackend | None = None,
    ) -> None:
        self.embedder  = embedder
        self.quantizer = quantizer if quantizer is not None else Quantizer("float16")
        self.storage   = storage or ZipStorageBackend()

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
            # Step 1: Batch embed all sections (skipped when no embedder provided)
            texts = [
                (s.summary or s.title + " " + s.text[:300]).strip()
                for s in doc.sections
            ]
            vectors = self.embedder.embed(texts) if (texts and self.embedder) else []

            # Step 2: Quantize embeddings and attach to sections
            import numpy as np
            for i, section in enumerate(doc.sections):
                if len(vectors) > i:
                    section.embedding = self.quantizer.quantize(vectors[i])

            # Step 3: Build JSON payloads (compact — no indent whitespace)
            manifest  = self._build_manifest(doc)
            catalogue = self._build_catalogue(doc)
            content   = self._build_content(doc)

            # Step 4: Build binary embedding blob (embeddings.bin)
            # Raw bytes — no base64, no JSON overhead. Sections in section_index order.
            # Format: [section_0_bytes | section_1_bytes | ... ] where each chunk is
            # exactly (embedding_dims × bytes_per_element) bytes.
            emb_blob = self._build_embedding_blob(doc)

            # Step 5: Write archive — compact JSON + binary blob
            entries: dict[str, str | bytes] = {
                "manifest.json":  json.dumps(manifest,  ensure_ascii=False, separators=_JSON_SEP),
                "catalogue.json": json.dumps(catalogue, ensure_ascii=False, separators=_JSON_SEP),
                "content.json":   json.dumps(content,   ensure_ascii=False, separators=_JSON_SEP),
            }
            if emb_blob:
                entries["embeddings.bin"] = emb_blob  # bytes → stored as ZIP_STORED

            return self.storage.write_archive(entries, str(out))

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

    def _build_embedding_blob(self, doc: Document) -> bytes:
        """Concatenate all section embedding bytes into a single binary blob.

        Sections with no embedding contribute (dims × bytes_per_element) zero bytes
        so the blob is always a perfect (n_sections × stride) matrix.
        Consumers can decode with:
            np.frombuffer(blob, dtype=np.float16).reshape(n_sections, dims)
        """
        import numpy as np
        stride = self.quantizer.stride(self.embedder.dims)
        parts: list[bytes] = []
        for section in doc.sections:
            if section.embedding and len(section.embedding) == stride:
                parts.append(section.embedding)
            else:
                parts.append(b"\x00" * stride)  # zero-vector placeholder
        return b"".join(parts) if parts else b""

    def _build_manifest(self, doc: Document) -> dict[str, Any]:
        """Build manifest.json — format version and embedding config."""
        m = doc.meta
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
            "embedding_format": "binary",   # embeddings.bin — not base64 in catalogue
            # Human-facing metadata
            "owner": m.owner,
            "department": m.department,
            "tags": m.tags,
            "access_roles": m.access_roles,
            "version": m.version,
            "last_updated": m.last_updated,
            "producer": "docnest-ai 1.0",
        }

    def _build_catalogue(self, doc: Document) -> dict[str, Any]:
        """Build catalogue.json — section index loaded into RAM on file open."""
        section_index = []
        for s in doc.sections:
            # NOTE: embeddings are NOT stored here — they live in embeddings.bin
            # Keeping embedding field absent keeps catalogue.json small and fast to parse.
            section_index.append({
                "id":          s.id,
                "title":       s.title,
                "level":       s.level,
                "parent_id":   s.parent_id,
                "children":    s.children,
                "summary":     s.summary or "",
                "keywords":    s.keywords,
                "token_count": s.token_count,
            })

        m = doc.meta
        return {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "source": doc.source,
            "language": "en",
            "summary": doc.summary or "",
            "insights": doc.insights,
            # Human-facing metadata
            "owner": m.owner,
            "department": m.department,
            "tags": m.tags,
            "access_roles": m.access_roles,
            "version": m.version,
            "last_updated": m.last_updated,
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
