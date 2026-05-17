"""Tests for UDFWriter.

Phase: 4  |  Run: pytest tests/test_writer.py -v
"""
import pytest
import zipfile
from pathlib import Path


class TestUDFWriter:
    """TODO (Phase 4): Uncomment after UDFWriter is implemented."""

    # def test_write_creates_zip_file(self, tmp_path, sample_document):
    #     from docnest.writer import UDFWriter
    #     from docnest.embedder import NomicEmbedder
    #     from docnest.quantizer import Quantizer
    #     writer = UDFWriter(NomicEmbedder(), Quantizer("float16"))
    #     out = str(tmp_path / "test.udf")
    #     writer.write(sample_document, out)
    #     assert Path(out).exists()

    # def test_udf_contains_required_files(self, tmp_path, sample_document):
    #     out = write_test_udf(tmp_path, sample_document)
    #     with zipfile.ZipFile(out, "r") as zf:
    #         names = zf.namelist()
    #         assert "manifest.json" in names
    #         assert "catalogue.json" in names
    #         assert "content.json" in names

    pass
