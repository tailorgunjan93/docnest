"""
Shared pytest fixtures for all DOCNEST tests.

Place sample document files in tests/fixtures/ — see tests/fixtures/README.md
for naming conventions and what files are needed.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from docnest.models import (
    Document,
    DocMeta,
    KeyNumber,
    RawDocument,
    Section,
    TableData,
)
from docnest.normalizer import SectionNormaliser
from docnest.providers.llm import ILLMProvider
from docnest.providers.vector import IVectorBackend

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ── File fixtures (skip if missing) ──────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_pdf(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "sample_text.pdf"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}. Add a sample PDF to tests/fixtures/")
    return path


@pytest.fixture
def sample_docx(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "sample.docx"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def sample_xlsx(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "sample_with_tables.xlsx"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path


@pytest.fixture
def sample_md_file(tmp_path: Path) -> Path:
    """Create a synthetic Markdown file for parser tests."""
    md = tmp_path / "sample.md"
    md.write_text(
        "# Introduction\n\nThis is the intro.\n\n"
        "## Background\n\nSome background text.\n\n"
        "### Sub-section\n\nDeep content here.\n\n"
        "## Methods\n\nThe method section.\n\n"
        "# Results\n\nFinal results.\n",
        encoding="utf-8",
    )
    return md


# ── Model helpers ─────────────────────────────────────────────────────────────

def make_raw(sections: list[tuple[int, str]], text: str = "Content") -> RawDocument:
    """Build a RawDocument from (level, title) pairs."""
    return RawDocument(
        doc_id="test-doc",
        title="Test Document",
        source="test.pdf",
        format="pdf",
        sections=[
            Section(id="", title=title, level=level, text=f"{text} of {title}")
            for level, title in sections
        ],
    )


@pytest.fixture
def raw_flat() -> RawDocument:
    """Three flat H1 sections — no nesting."""
    return make_raw([(1, "Introduction"), (1, "Methods"), (1, "Results")])


@pytest.fixture
def raw_nested() -> RawDocument:
    """H1 → H2 → H2 → H1 → H2 hierarchy."""
    return make_raw([
        (1, "Part A"),
        (2, "A Background"),
        (2, "A Scope"),
        (1, "Part B"),
        (2, "B Details"),
    ])


@pytest.fixture
def raw_deep() -> RawDocument:
    """Six-level deep nesting."""
    return make_raw([
        (1, "L1"),
        (2, "L2"),
        (3, "L3"),
        (4, "L4"),
        (5, "L5"),
        (6, "L6"),
    ])


@pytest.fixture
def raw_with_tables() -> RawDocument:
    """Document with structured tables."""
    raw = make_raw([(1, "Data Section")])
    raw.sections[0].tables = [
        TableData(
            table_id="t1",
            caption="Sales Data",
            headers=["Region", "Q1", "Q2"],
            rows=[["North", "100", "120"], ["South", "80", "95"]],
        )
    ]
    return raw


@pytest.fixture
def normalised_doc(raw_nested: RawDocument) -> Document:
    """Fully normalised Document (§ids assigned)."""
    return SectionNormaliser().normalise(raw_nested)


@pytest.fixture
def normalised_flat(raw_flat: RawDocument) -> Document:
    return SectionNormaliser().normalise(raw_flat)


# ── Mock embedder ─────────────────────────────────────────────────────────────

class MockEmbedder:
    """Returns deterministic unit vectors — no network calls."""
    DIMS = 384

    def embed(self, texts: list[str]) -> np.ndarray:
        rng = np.random.default_rng(42)
        mat = rng.standard_normal((len(texts), self.DIMS)).astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        return mat / np.where(norms == 0, 1, norms)

    @property
    def dims(self) -> int:
        return self.DIMS

    @property
    def model_name(self) -> str:
        return "mock/mock-384"


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


# ── Mock LLM provider ─────────────────────────────────────────────────────────

class MockLLMProvider(ILLMProvider):
    """Concrete ILLMProvider for tests — no network, returns fixed string."""

    def complete(self, prompt: str, system: str = "", temperature: float = 0.1,
                 max_tokens: int = 512) -> str:
        return "Mock answer from LLM."

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider()


# ── Minimal .udf file fixture ─────────────────────────────────────────────────

@pytest.fixture
def minimal_udf(tmp_path: Path, normalised_doc: Document, mock_embedder: MockEmbedder) -> Path:
    """Write a real .udf archive and return its path."""
    from docnest.quantizer import Quantizer
    from docnest.writer import UDFWriter

    out = str(tmp_path / "test.udf")
    # Enrich sections with summaries/keywords so writer has something to store
    for s in normalised_doc.sections:
        s.summary = f"Summary of {s.title}."
        s.keywords = [s.title.lower(), "test"]
    normalised_doc.summary = "Test document summary."
    normalised_doc.insights = ["Insight one.", "Insight two."]
    normalised_doc.key_numbers = [KeyNumber(label="Count", value="42", unit=None, section="§1")]

    writer = UDFWriter(mock_embedder, Quantizer("float16"))
    writer.write(normalised_doc, out)
    return Path(out)


@pytest.fixture
def minimal_udf_path(minimal_udf: Path) -> str:
    return str(minimal_udf)
