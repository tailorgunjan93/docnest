"""Tests for Task 1 — Path/Schema Compaction (privacy-by-default source sanitisation).

Protocol: written test-first (Phase 3). These FAIL until the writer change lands.
Covers: unit (pure helper), integration (writer), e2e (pipeline), CLI flag wiring,
and backward-compatibility (a .udf that stores a full path still loads & queries).

Run: pytest tests/test_source_compaction.py -v
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from docnest.normalizer import SectionNormaliser
from docnest.quantizer import Quantizer
from docnest.writer import UDFWriter
from tests.conftest import MockEmbedder, MockLLMProvider, make_raw


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_doc(source: str):
    raw = make_raw([(1, "Introduction"), (1, "Body")])
    raw.source = source
    doc = SectionNormaliser().normalise(raw)
    for s in doc.sections:
        s.summary = f"Summary of {s.title}."
        s.keywords = [s.title.lower(), "test"]
    return doc


def _read_catalogue(udf_path: str) -> dict:
    with zipfile.ZipFile(udf_path, "r") as z:
        return json.loads(z.read("catalogue.json"))


WIN_PATH = r"C:\Reports\2025\sample_report.md"
POSIX_PATH = "/home/user/docs/report.pdf"
URL_SRC = "https://github.com/owner/repo/blob/main/file.py"


def _embedder_works_offline() -> bool:
    """True only if the default HuggingFace embedder runs WITHOUT network.

    Forces HF offline mode and actually embeds a probe string. This is the truest
    gate for the real-CLI e2e: it runs only when the model is fully usable offline,
    and never triggers a download (so the default suite stays fast and offline).
    Checking only that a config file is cached is NOT enough — weights or packages
    may still be missing.
    """
    import os
    prev = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        from docnest.embedder import LangChainEmbedder
        vec = LangChainEmbedder("huggingface", "all-MiniLM-L6-v2").embed(["probe"])
        return getattr(vec, "shape", (0,))[0] == 1
    except Exception:
        return False
    finally:
        if prev is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = prev


requires_minilm = pytest.mark.skipif(
    not _embedder_works_offline(),
    reason="all-MiniLM-L6-v2 embedder not usable offline — skipping network-gated CLI e2e",
)


# ── Unit: pure helper _sanitise_source ──────────────────────────────────────

class TestSanitiseSource:
    def test_windows_absolute_path_becomes_basename(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(WIN_PATH) == "sample_report.md"

    def test_posix_absolute_path_becomes_basename(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(POSIX_PATH) == "report.pdf"

    def test_keep_full_returns_original(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(WIN_PATH, keep_full=True) == WIN_PATH

    def test_url_is_preserved(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(URL_SRC) == URL_SRC

    def test_name_with_spaces_and_unicode(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(r"C:\Docs\Q1 résumé.docx") == "Q1 résumé.docx"

    def test_no_extension(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source(r"C:\data\READMEFILE") == "READMEFILE"

    def test_already_basename_unchanged(self):
        from docnest.writer import _sanitise_source
        assert _sanitise_source("test.pdf") == "test.pdf"


# ── Integration: UDFWriter stores sanitised source ──────────────────────────

class TestWriterSanitisesSource:
    def test_default_stores_basename_only(self, tmp_path: Path):
        doc = _build_doc(WIN_PATH)
        out = str(tmp_path / "o.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, out)
        cat = _read_catalogue(out)
        assert cat["source"] == "sample_report.md"
        assert "\\" not in cat["source"] and "/" not in cat["source"]

    def test_opt_in_keeps_full_path(self, tmp_path: Path):
        doc = _build_doc(WIN_PATH)
        out = str(tmp_path / "o.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(
            doc, out, include_source_path=True
        )
        cat = _read_catalogue(out)
        assert cat["source"] == WIN_PATH


# ── E2E: pipeline.convert produces a path-free .udf ─────────────────────────

class TestPipelineSourceCompaction:
    def test_convert_default_has_no_absolute_path(self, tmp_path: Path):
        from docnest.pipeline import DocNestPipeline
        md = tmp_path / "my report.md"
        md.write_text("# Title\n\nHello world, some content here.\n", encoding="utf-8")
        pipe = DocNestPipeline(embedder=MockEmbedder(), skip_intelligence=True)
        out = pipe.convert(str(md))
        cat = _read_catalogue(out)
        assert cat["source"] == "my report.md"

    def test_convert_opt_in_keeps_full_path(self, tmp_path: Path):
        from docnest.pipeline import DocNestPipeline
        md = tmp_path / "doc.md"
        md.write_text("# Title\n\nContent body here.\n", encoding="utf-8")
        pipe = DocNestPipeline(embedder=MockEmbedder(), skip_intelligence=True)
        out = pipe.convert(str(md), include_source_path=True)
        cat = _read_catalogue(out)
        assert cat["source"] == str(md.resolve()) or cat["source"] == str(md)


# ── Functional: CLI flag is wired ───────────────────────────────────────────

class TestCliFlag:
    def test_help_lists_include_source_path(self):
        from typer.testing import CliRunner
        from docnest.cli import app
        result = CliRunner().invoke(app, ["convert", "--help"])
        assert "--include-source-path" in result.output


# ── Regression / backward-compat: full-path .udf still loads & queries ──────

class TestBackwardCompat:
    def test_udf_with_full_path_still_loads_and_queries(self, tmp_path: Path):
        from docnest.reader import UDFIndex
        doc = _build_doc(r"D:\old\machine\private\report.md")
        out = str(tmp_path / "old_style.udf")
        # include_source_path=True reproduces the legacy absolute-path .udf
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(
            doc, out, include_source_path=True
        )
        idx = UDFIndex.load(out)
        res = idx.query("introduction", llm_provider=MockLLMProvider())
        assert res is not None
        assert isinstance(res.answer, str)


# ── True E2E: the real `docnest convert` CLI command (network-gated) ────────

class TestCliEndToEnd:
    @requires_minilm
    def test_real_cli_convert_strips_absolute_path(self, tmp_path: Path):
        """Drive the actual CLI: convert a file → .udf → source is basename only.

        Uses the real default HuggingFace embedder (offline, from cache) and --fast
        to skip the LLM. Skipped automatically when the model is not cached.
        """
        from typer.testing import CliRunner
        from docnest.cli import app

        md = tmp_path / "cli report.md"
        md.write_text(
            "# Quarterly Report\n\nSome content for the CLI end-to-end test.\n",
            encoding="utf-8",
        )
        out = tmp_path / "cli_report.udf"
        result = CliRunner().invoke(
            app, ["convert", str(md), "--fast", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        cat = _read_catalogue(str(out))
        assert cat["source"] == "cli report.md"
        assert "\\" not in cat["source"] and "/" not in cat["source"]
