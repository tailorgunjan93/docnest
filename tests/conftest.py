"""
Shared pytest fixtures for all DocForge tests.

Place sample document files in tests/fixtures/ — see tests/fixtures/README.md
for naming conventions and what files are needed.
"""

from __future__ import annotations
from pathlib import Path
import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_pdf(fixtures_dir: Path) -> Path:
    """Return path to the sample text-based PDF fixture."""
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
def sample_md(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "sample.md"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    return path
