"""
Data models for DOCNEST.

All models are Pydantic v2 — fully typed, validated, and serialisable to JSON.
These are the core data contracts that flow between every stage of the pipeline.

Spec reference: docs/SPEC_DOCNEST_PYPI.md — Section 10 (Interfaces & Classes)
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class TableData(BaseModel):
    """A structured table extracted from a document section.

    Tables are NEVER stored as flat text strings. Column headers are always
    preserved so the LLM receives full context when answering table-based queries.
    """
    table_id: str = Field(description="Unique ID within the document, e.g. tbl_001")
    caption: Optional[str] = Field(default=None, description="Table title or caption")
    headers: list[str] = Field(description="Column header labels")
    rows: list[list[str]] = Field(description="Data rows — each row length must equal len(headers)")


class ImageRef(BaseModel):
    """Reference to an image asset extracted from a section."""
    image_id: str
    alt: Optional[str] = None
    asset_path: str = Field(description="Relative path inside the .udf zip, e.g. assets/img_001.png")


class Section(BaseModel):
    """A single navigable section within a document.

    Every heading in the source document becomes one Section. Sections are the
    fundamental unit of retrieval — the LLM receives one section, not a blind chunk.
    """
    id: str = Field(description="Section identifier, e.g. '§3.1'")
    title: str = Field(description="Original heading text")
    level: int = Field(ge=1, le=6, description="Heading level (1=H1, 6=H6)")
    text: str = Field(description="Full normalised section text")
    tables: list[TableData] = Field(default_factory=list)
    images: list[ImageRef] = Field(default_factory=list)
    parent_id: Optional[str] = Field(default=None, description="Parent section id, None for top-level")
    children: list[str] = Field(default_factory=list, description="Child section ids")
    token_count: int = Field(default=0, description="Approximate token count of text")
    # Filled by IntelligenceEngine (Stage 4)
    summary: Optional[str] = Field(default=None, description="One-sentence section summary")
    keywords: list[str] = Field(default_factory=list, description="BM25 keyword index terms")
    # Filled by Embedder + Quantizer (Stage 6)
    embedding: Optional[bytes] = Field(default=None, description="Quantised embedding bytes")


class KeyNumber(BaseModel):
    """A metric or key figure extracted from the document."""
    label: str = Field(description="Human-readable label, e.g. 'Revenue'")
    value: str = Field(description="The value, e.g. '$142M'")
    unit: Optional[str] = Field(default=None, description="Unit of measurement, e.g. 'USD', 'percent'")
    section: str = Field(description="Source section id, e.g. '§3.1'")


class RawDocument(BaseModel):
    """Output of Stage 1 (parsing) — unstructured, before section assignment.

    This is the intermediate format produced by parsers before normalisation.
    Parsers fill this; the Normaliser consumes it.
    """
    doc_id: str
    title: str
    source: str = Field(description="Absolute file path or source URL")
    format: str = Field(description="File format: pdf, docx, xlsx, html, md, etc.")
    sections: list[Section] = Field(default_factory=list, description="Sections without §ids yet")
    raw_text: Optional[str] = Field(default=None, description="Full raw text if section extraction failed")


class Document(BaseModel):
    """A fully normalised document — output of the complete 6-stage pipeline."""
    doc_id: str
    title: str
    source: str
    format: str
    sections: list[Section]
    # Filled by IntelligenceEngine (Stage 5)
    summary: Optional[str] = None
    insights: list[str] = Field(default_factory=list, description="3-5 non-obvious findings")
    key_numbers: list[KeyNumber] = Field(default_factory=list)


class Catalogue(BaseModel):
    """Lightweight document catalogue stored in catalogue.json inside the .udf.

    The catalogue is loaded into memory on file open. content.json is only
    fetched section-by-section on demand (lazy loading).
    """
    doc_id: str
    title: str
    source: str
    language: str = "en"
    summary: str = ""
    insights: list[str] = Field(default_factory=list)
    key_numbers: list[KeyNumber] = Field(default_factory=list)
    section_index: list[dict] = Field(
        default_factory=list,
        description="Lightweight section metadata: id, title, keywords, summary, embedding (base64)"
    )
    embedding_model: str = ""
    embedding_dims: int = 0
    quantization: str = "float16"
