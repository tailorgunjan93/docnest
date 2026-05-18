"""Tests for docnest CLI — all commands via Typer CliRunner.

Run: pytest tests/test_cli.py -v
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from docnest.cli import app

runner = CliRunner()


# ── inspect ───────────────────────────────────────────────────────────────────

class TestInspectCommand:
    def test_inspect_exits_0_for_valid_udf(self, minimal_udf: Path):
        result = runner.invoke(app, ["inspect", str(minimal_udf)])
        assert result.exit_code == 0

    def test_inspect_prints_title(self, minimal_udf: Path):
        result = runner.invoke(app, ["inspect", str(minimal_udf)])
        assert "Test Document" in result.output

    def test_inspect_prints_section_ids(self, minimal_udf: Path):
        result = runner.invoke(app, ["inspect", str(minimal_udf)])
        assert "§" in result.output

    def test_inspect_prints_insights(self, minimal_udf: Path):
        result = runner.invoke(app, ["inspect", str(minimal_udf)])
        # minimal_udf has insights
        assert "Insight" in result.output

    def test_inspect_prints_key_numbers(self, minimal_udf: Path):
        result = runner.invoke(app, ["inspect", str(minimal_udf)])
        assert "Count" in result.output

    def test_inspect_missing_file_exits_1(self, tmp_path: Path):
        result = runner.invoke(app, ["inspect", str(tmp_path / "missing.udf")])
        assert result.exit_code == 1

    def test_inspect_invalid_udf_exits_1(self, tmp_path: Path):
        """A plain text file masquerading as .udf should error."""
        bad = tmp_path / "bad.udf"
        bad.write_bytes(b"not a zip")
        result = runner.invoke(app, ["inspect", str(bad)])
        assert result.exit_code == 1


# ── stats ─────────────────────────────────────────────────────────────────────

class TestStatsCommand:
    def test_stats_exits_0_for_valid_udf(self, minimal_udf: Path):
        result = runner.invoke(app, ["stats", str(minimal_udf)])
        assert result.exit_code == 0

    def test_stats_shows_embedding_model(self, minimal_udf: Path):
        result = runner.invoke(app, ["stats", str(minimal_udf)])
        assert "mock" in result.output.lower() or "embedding" in result.output.lower()

    def test_stats_shows_section_count(self, minimal_udf: Path):
        result = runner.invoke(app, ["stats", str(minimal_udf)])
        assert "Sections" in result.output or "section" in result.output.lower()

    def test_stats_shows_quantization(self, minimal_udf: Path):
        result = runner.invoke(app, ["stats", str(minimal_udf)])
        assert "float16" in result.output

    def test_stats_missing_file_exits_1(self, tmp_path: Path):
        result = runner.invoke(app, ["stats", str(tmp_path / "missing.udf")])
        assert result.exit_code == 1

    def test_stats_invalid_file_exits_1(self, tmp_path: Path):
        bad = tmp_path / "bad.udf"
        bad.write_bytes(b"not a zip")
        result = runner.invoke(app, ["stats", str(bad)])
        assert result.exit_code == 1


# ── view ──────────────────────────────────────────────────────────────────────

class TestViewCommand:
    def test_view_generates_html_file(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        result = runner.invoke(app, ["view", str(minimal_udf), "--output", out, "--no-open"])
        assert result.exit_code == 0
        assert Path(out).exists()

    def test_view_exits_0_on_success(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "view_out.html")
        result = runner.invoke(app, ["view", str(minimal_udf), "--output", out, "--no-open"])
        assert result.exit_code == 0

    def test_view_output_is_valid_html(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        runner.invoke(app, ["view", str(minimal_udf), "--output", out, "--no-open"])
        content = Path(out).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_view_missing_file_exits_1(self, tmp_path: Path):
        result = runner.invoke(app, ["view", str(tmp_path / "missing.udf"), "--no-open"])
        assert result.exit_code == 1

    def test_view_success_message_in_output(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        result = runner.invoke(app, ["view", str(minimal_udf), "--output", out, "--no-open"])
        assert "Viewer ready" in result.output or "out.html" in result.output


# ── convert ───────────────────────────────────────────────────────────────────

class TestConvertCommand:
    def test_convert_fast_mode_with_mocked_pipeline(self, tmp_path: Path, sample_md_file: Path):
        """Verify the convert command runs end-to-end with a mocked pipeline."""
        out = str(tmp_path / "out.udf")
        # Pre-create the output file so stat() works after the mock
        Path(out).write_bytes(b"fake udf content padded" * 100)

        with patch("docnest.pipeline.DocNestPipeline") as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.convert.return_value = out
            MockPipeline.return_value = mock_instance

            result = runner.invoke(app, [
                "convert", str(sample_md_file), "--fast", "--output", out,
            ])

        assert result.exit_code == 0

    def test_convert_missing_source_exits_1(self, tmp_path: Path):
        result = runner.invoke(app, ["convert", str(tmp_path / "missing.md")])
        assert result.exit_code == 1

    def test_convert_passes_quantization(self, tmp_path: Path, sample_md_file: Path):
        out = str(tmp_path / "out.udf")
        Path(out).write_bytes(b"x" * 1000)

        with patch("docnest.pipeline.DocNestPipeline") as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.convert.return_value = out
            MockPipeline.return_value = mock_instance

            runner.invoke(app, [
                "convert", str(sample_md_file), "--fast", "--output", out,
                "--quantization", "int8",
            ])

            call_kwargs = MockPipeline.call_args
            assert call_kwargs is not None

    def test_convert_with_owner_metadata(self, tmp_path: Path, sample_md_file: Path):
        out = str(tmp_path / "out.udf")
        Path(out).write_bytes(b"x" * 500)

        with patch("docnest.pipeline.DocNestPipeline") as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.convert.return_value = out
            MockPipeline.return_value = mock_instance

            result = runner.invoke(app, [
                "convert", str(sample_md_file), "--fast", "--output", out,
                "--owner", "Alice", "--department", "Engineering",
            ])

        assert result.exit_code == 0

    def test_convert_verbose_flag_accepted(self, tmp_path: Path, sample_md_file: Path):
        out = str(tmp_path / "out.udf")
        Path(out).write_bytes(b"x" * 500)

        with patch("docnest.pipeline.DocNestPipeline") as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.convert.return_value = out
            MockPipeline.return_value = mock_instance

            result = runner.invoke(app, [
                "convert", str(sample_md_file), "--fast", "--output", out, "--verbose",
            ])

        assert result.exit_code == 0

    def test_convert_docnest_error_exits_1(self, tmp_path: Path, sample_md_file: Path):
        from docnest.exceptions import DOCNESTError

        with patch("docnest.pipeline.DocNestPipeline") as MockPipeline:
            mock_instance = MagicMock()
            mock_instance.convert.side_effect = DOCNESTError("Pipeline failed")
            MockPipeline.return_value = mock_instance

            result = runner.invoke(app, [
                "convert", str(sample_md_file), "--fast",
            ])

        assert result.exit_code == 1


# ── query ─────────────────────────────────────────────────────────────────────

class TestQueryCommand:
    def test_query_missing_file_exits_1(self, tmp_path: Path):
        result = runner.invoke(app, ["query", str(tmp_path / "missing.udf"), "What is this?"])
        assert result.exit_code == 1

    def test_query_returns_answer(self, minimal_udf: Path):
        """Query against minimal_udf — Layer 0 should answer without LLM."""
        result = runner.invoke(app, [
            "query", str(minimal_udf), "What is this document about?",
        ])
        # Layer 0 summary should be returned without any LLM call
        assert result.exit_code == 0

    def test_query_show_layer_flag(self, minimal_udf: Path):
        result = runner.invoke(app, [
            "query", str(minimal_udf), "summarise the document",
            "--show-layer",
        ])
        assert result.exit_code == 0
        # Layer 0 label should be shown
        assert "Layer" in result.output or "layer" in result.output or "pre-computed" in result.output

    def test_query_prints_non_empty_answer(self, minimal_udf: Path):
        result = runner.invoke(app, [
            "query", str(minimal_udf), "What is the summary?",
        ])
        assert result.exit_code == 0
        # Some non-empty output expected
        assert len(result.output.strip()) > 0


# ── library init ─────────────────────────────────────────────────────────────

class TestLibraryInitCommand:
    def test_library_init_exits_0(self, tmp_path: Path):
        result = runner.invoke(app, ["library", "init", str(tmp_path), "--name", "Test Lib"])
        assert result.exit_code == 0

    def test_library_init_creates_library_json(self, tmp_path: Path):
        runner.invoke(app, ["library", "init", str(tmp_path), "--name", "My Lib"])
        assert (tmp_path / "library.json").exists()

    def test_library_init_shows_name(self, tmp_path: Path):
        result = runner.invoke(app, ["library", "init", str(tmp_path), "--name", "Engineering"])
        assert "Engineering" in result.output

    def test_library_init_with_description(self, tmp_path: Path):
        result = runner.invoke(app, [
            "library", "init", str(tmp_path),
            "--name", "Docs", "--description", "All engineering docs",
        ])
        assert result.exit_code == 0


# ── library add ──────────────────────────────────────────────────────────────

class TestLibraryAddCommand:
    def test_library_add_exits_0(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "add", str(minimal_udf), "--library", str(tmp_path),
        ])
        assert result.exit_code == 0

    def test_library_add_shows_title(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "add", str(minimal_udf), "--library", str(tmp_path),
        ])
        assert "Test Document" in result.output

    def test_library_add_missing_udf_exits_1(self, tmp_path: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "add", str(tmp_path / "missing.udf"), "--library", str(tmp_path),
        ])
        assert result.exit_code == 1

    def test_library_add_persists_to_json(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        runner.invoke(app, ["library", "add", str(minimal_udf), "--library", str(tmp_path)])
        data = json.loads((tmp_path / "library.json").read_text())
        assert len(data["documents"]) == 1


# ── library list ─────────────────────────────────────────────────────────────

class TestLibraryListCommand:
    def test_library_list_empty_shows_no_docs_message(self, tmp_path: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, ["library", "list", "--library", str(tmp_path)])
        assert result.exit_code == 0
        assert "No documents" in result.output

    def test_library_list_shows_added_doc(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        runner.invoke(app, ["library", "add", str(minimal_udf), "--library", str(tmp_path)])
        result = runner.invoke(app, ["library", "list", "--library", str(tmp_path)])
        assert result.exit_code == 0
        assert "Test Document" in result.output

    def test_library_list_filter_by_department(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        runner.invoke(app, ["library", "add", str(minimal_udf), "--library", str(tmp_path)])
        # Filter for non-existent department → no docs
        result = runner.invoke(app, [
            "library", "list", "--library", str(tmp_path), "--department", "NonExistent",
        ])
        assert result.exit_code == 0


# ── library search ────────────────────────────────────────────────────────────

class TestLibrarySearchCommand:
    def test_library_search_returns_results(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        runner.invoke(app, ["library", "add", str(minimal_udf), "--library", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "search", "test", "--library", str(tmp_path),
        ])
        assert result.exit_code == 0

    def test_library_search_no_results_message(self, tmp_path: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "search", "anythingxyz", "--library", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "No results" in result.output


# ── library remove ────────────────────────────────────────────────────────────

class TestLibraryRemoveCommand:
    def test_library_remove_existing_doc(self, tmp_path: Path, minimal_udf: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        runner.invoke(app, ["library", "add", str(minimal_udf), "--library", str(tmp_path)])
        data = json.loads((tmp_path / "library.json").read_text())
        doc_id = data["documents"][0]["doc_id"]

        result = runner.invoke(app, [
            "library", "remove", doc_id, "--library", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_library_remove_nonexistent_shows_warning(self, tmp_path: Path):
        runner.invoke(app, ["library", "init", str(tmp_path)])
        result = runner.invoke(app, [
            "library", "remove", "nonexistent-doc", "--library", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Warning" in result.output or "not found" in result.output.lower()
