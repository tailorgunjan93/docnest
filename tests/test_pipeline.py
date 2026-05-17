"""Integration tests for the full DocForgePipeline.

Phase: 1-6  |  Run: pytest tests/test_pipeline.py -v
Requires Ollama running locally with llama3.2 and nomic-embed-text pulled.
"""
import pytest
from pathlib import Path
from docforge.pipeline import DocForgePipeline


class TestDocForgePipeline:
    """TODO: Uncomment as each phase is implemented."""

    # @pytest.mark.integration
    # def test_end_to_end_pdf(self, tmp_path, sample_pdf):
    #     pipeline = DocForgePipeline(llm_provider="ollama", llm_model="llama3.2")
    #     out = pipeline.convert(str(sample_pdf), output=str(tmp_path / "out.udf"))
    #     assert Path(out).exists()
    #     assert Path(out).stat().st_size > 1024

    # @pytest.mark.integration
    # def test_folder_creates_library_udf(self, tmp_path, fixtures_dir):
    #     pipeline = DocForgePipeline()
    #     out = pipeline.convert(str(fixtures_dir), output=str(tmp_path / "library.udf"))
    #     from docforge.reader import UDFIndex
    #     index = UDFIndex.load(out)
    #     assert index.catalogue.doc_id or index.catalogue.title

    pass
