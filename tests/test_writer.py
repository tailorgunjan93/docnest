"""Tests for UDFWriter — archive structure and content.

Run: pytest tests/test_writer.py -v
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from docnest.models import Document, DocMeta, KeyNumber, RawDocument, Section, TableData
from docnest.normalizer import SectionNormaliser
from docnest.quantizer import Quantizer
from docnest.writer import UDFWriter


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_doc(n_sections: int = 3, with_tables: bool = False) -> Document:
    from tests.conftest import MockEmbedder, make_raw
    sections = [(1, f"Section {i+1}") for i in range(n_sections)]
    raw = make_raw(sections)
    doc = SectionNormaliser().normalise(raw)
    for s in doc.sections:
        s.summary = f"Summary of {s.title}."
        s.keywords = [s.title.lower().replace(" ", "_"), "test"]
    doc.summary = "Overall document summary."
    doc.insights = ["Insight A.", "Insight B."]
    doc.key_numbers = [KeyNumber(label="Count", value="5", unit=None, section="§1")]
    if with_tables:
        doc.sections[0].tables = [
            TableData(
                table_id="t1",
                caption="Demo Table",
                headers=["Col A", "Col B"],
                rows=[["1", "2"], ["3", "4"]],
            )
        ]
    return doc


def write(doc: Document, tmp_path: Path, quantization: str = "float16") -> Path:
    from tests.conftest import MockEmbedder
    out = str(tmp_path / "test.udf")
    UDFWriter(MockEmbedder(), Quantizer(quantization)).write(doc, out)
    return Path(out)


# ── Archive structure ─────────────────────────────────────────────────────────

class TestArchiveStructure:
    def test_creates_zip_file(self, tmp_path: Path):
        p = write(make_doc(), tmp_path)
        assert p.exists()
        assert zipfile.is_zipfile(str(p))

    def test_contains_manifest(self, tmp_path: Path):
        p = write(make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            assert "manifest.json" in zf.namelist()

    def test_contains_catalogue(self, tmp_path: Path):
        p = write(make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            assert "catalogue.json" in zf.namelist()

    def test_contains_content(self, tmp_path: Path):
        p = write(make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            assert "content.json" in zf.namelist()

    def test_contains_embeddings_bin(self, tmp_path: Path):
        """Binary embedding blob should be written."""
        p = write(make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            assert "embeddings.bin" in zf.namelist()

    def test_no_extra_unexpected_files(self, tmp_path: Path):
        p = write(make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            names = set(zf.namelist())
        expected = {"manifest.json", "catalogue.json", "content.json", "embeddings.bin"}
        unexpected = names - expected - {n for n in names if n.startswith("assets/")}
        assert unexpected == set()


# ── manifest.json ─────────────────────────────────────────────────────────────

class TestManifest:
    def _load(self, tmp_path: Path, doc: Document = None) -> dict:
        p = write(doc or make_doc(), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            return json.loads(zf.read("manifest.json"))

    def test_udf_version_present(self, tmp_path: Path):
        m = self._load(tmp_path)
        assert "udf_version" in m

    def test_doc_id_matches_document(self, tmp_path: Path):
        doc = make_doc()
        m = self._load(tmp_path, doc)
        assert m["doc_id"] == doc.doc_id

    def test_title_matches_document(self, tmp_path: Path):
        doc = make_doc()
        m = self._load(tmp_path, doc)
        assert m["title"] == doc.title

    def test_embedding_model_present(self, tmp_path: Path):
        m = self._load(tmp_path)
        assert "embedding_model" in m

    def test_embedding_dims_is_int(self, tmp_path: Path):
        m = self._load(tmp_path)
        assert isinstance(m["embedding_dims"], int)
        assert m["embedding_dims"] > 0

    def test_quantization_field(self, tmp_path: Path):
        m = self._load(tmp_path)
        assert m["quantization"] in ("float32", "float16", "int8", "binary")

    def test_embedding_format_is_binary(self, tmp_path: Path):
        m = self._load(tmp_path)
        assert m.get("embedding_format") == "binary"

    def test_section_count_matches(self, tmp_path: Path):
        doc = make_doc(n_sections=4)
        m = self._load(tmp_path, doc)
        assert m["section_count"] == 4

    def test_docmeta_owner_stored(self, tmp_path: Path):
        doc = make_doc()
        doc.meta = DocMeta(owner="Alice", department="Finance", tags=["q4"])
        m = self._load(tmp_path, doc)
        assert m.get("owner") == "Alice"
        assert m.get("department") == "Finance"

    def test_doc_ids_consistent_across_files(self, tmp_path: Path):
        doc = make_doc()
        p = write(doc, tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            catalogue = json.loads(zf.read("catalogue.json"))
            content = json.loads(zf.read("content.json"))
        assert manifest["doc_id"] == catalogue["doc_id"] == content["doc_id"]


# ── catalogue.json ────────────────────────────────────────────────────────────

class TestCatalogue:
    def _load(self, tmp_path: Path, n: int = 3) -> dict:
        p = write(make_doc(n), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            return json.loads(zf.read("catalogue.json"))

    def test_section_index_length(self, tmp_path: Path):
        cat = self._load(tmp_path, n=3)
        assert len(cat["section_index"]) == 3

    def test_section_ids_present(self, tmp_path: Path):
        cat = self._load(tmp_path)
        for entry in cat["section_index"]:
            assert entry["id"].startswith("§")

    def test_section_titles_present(self, tmp_path: Path):
        cat = self._load(tmp_path)
        for entry in cat["section_index"]:
            assert entry["title"]

    def test_keywords_present(self, tmp_path: Path):
        cat = self._load(tmp_path)
        for entry in cat["section_index"]:
            assert "keywords" in entry

    def test_no_embedding_in_catalogue_section(self, tmp_path: Path):
        """With binary format, embeddings should NOT be in catalogue entries."""
        cat = self._load(tmp_path)
        for entry in cat["section_index"]:
            assert "embedding" not in entry or entry.get("embedding") is None

    def test_summary_in_catalogue(self, tmp_path: Path):
        cat = self._load(tmp_path)
        assert "summary" in cat

    def test_insights_in_catalogue(self, tmp_path: Path):
        cat = self._load(tmp_path)
        assert "insights" in cat

    def test_key_numbers_in_catalogue(self, tmp_path: Path):
        cat = self._load(tmp_path)
        assert "key_numbers" in cat


# ── content.json ──────────────────────────────────────────────────────────────

class TestContent:
    def _load(self, tmp_path: Path, n: int = 3) -> dict:
        p = write(make_doc(n), tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            return json.loads(zf.read("content.json"))

    def test_sections_dict_present(self, tmp_path: Path):
        content = self._load(tmp_path)
        assert "sections" in content

    def test_section_count_matches(self, tmp_path: Path):
        content = self._load(tmp_path, n=4)
        assert len(content["sections"]) == 4

    def test_section_keys_are_ids(self, tmp_path: Path):
        content = self._load(tmp_path)
        for key in content["sections"]:
            assert key.startswith("§")

    def test_section_text_stored(self, tmp_path: Path):
        content = self._load(tmp_path)
        for sec in content["sections"].values():
            assert "text" in sec

    def test_tables_stored_when_present(self, tmp_path: Path):
        doc = make_doc(with_tables=True)
        p = write(doc, tmp_path)
        with zipfile.ZipFile(str(p)) as zf:
            content = json.loads(zf.read("content.json"))
        first_section_id = list(content["sections"].keys())[0]
        tables = content["sections"][first_section_id].get("tables", [])
        assert len(tables) == 1
        assert tables[0]["headers"] == ["Col A", "Col B"]


# ── embeddings.bin ────────────────────────────────────────────────────────────

class TestEmbeddingsBin:
    def test_size_matches_n_dims_float16(self, tmp_path: Path):
        n = 5
        dims = 384  # MockEmbedder.DIMS
        doc = make_doc(n_sections=n)
        p = write(doc, tmp_path, quantization="float16")
        with zipfile.ZipFile(str(p)) as zf:
            raw = zf.read("embeddings.bin")
        expected = n * dims * 2  # float16 = 2 bytes/dim
        assert len(raw) == expected

    def test_size_matches_n_dims_float32(self, tmp_path: Path):
        n = 3
        dims = 384
        doc = make_doc(n_sections=n)
        p = write(doc, tmp_path, quantization="float32")
        with zipfile.ZipFile(str(p)) as zf:
            raw = zf.read("embeddings.bin")
        assert len(raw) == n * dims * 4

    def test_different_section_counts_give_different_blob_sizes(self, tmp_path: Path):
        from tests.conftest import MockEmbedder
        doc1 = make_doc(n_sections=2)
        doc2 = make_doc(n_sections=4)
        doc2.doc_id = "different-doc"

        path1 = str(tmp_path / "doc1.udf")
        path2 = str(tmp_path / "doc2.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc1, path1)
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc2, path2)

        with zipfile.ZipFile(path1) as zf:
            b1 = zf.read("embeddings.bin")
        with zipfile.ZipFile(path2) as zf:
            b2 = zf.read("embeddings.bin")
        assert len(b1) != len(b2)  # 2 sections vs 4 sections


# ── write_library stub ────────────────────────────────────────────────────────

class TestWriteLibrary:
    def test_write_library_raises_not_implemented(self, tmp_path: Path):
        from tests.conftest import MockEmbedder
        writer = UDFWriter(MockEmbedder(), Quantizer("float16"))
        with pytest.raises(NotImplementedError):
            writer.write_library([], str(tmp_path / "lib.udf"))


# ── Error paths ───────────────────────────────────────────────────────────────

class TestWriteErrorPaths:
    def test_udferror_from_storage_is_reraised(self, tmp_path: Path):
        """UDFWriteError raised by storage is re-raised unchanged (lines 129-130)."""
        from unittest.mock import patch
        from docnest.exceptions import UDFWriteError
        from tests.conftest import MockEmbedder
        doc = make_doc()
        writer = UDFWriter(MockEmbedder(), Quantizer("float16"))
        with patch.object(writer.storage, "write_archive",
                          side_effect=UDFWriteError("storage error")):
            with pytest.raises(UDFWriteError, match="storage error"):
                writer.write(doc, str(tmp_path / "out.udf"))

    def test_generic_exception_wrapped_in_udferror(self, tmp_path: Path):
        """Non-UDFWriteError exceptions are wrapped in UDFWriteError (lines 131-132)."""
        from unittest.mock import patch
        from docnest.exceptions import UDFWriteError
        from tests.conftest import MockEmbedder
        doc = make_doc()
        writer = UDFWriter(MockEmbedder(), Quantizer("float16"))
        with patch.object(writer.storage, "write_archive",
                          side_effect=OSError("disk full")):
            with pytest.raises(UDFWriteError):
                writer.write(doc, str(tmp_path / "out.udf"))


# ── Zero-vector placeholder ───────────────────────────────────────────────────

class TestZeroVectorPlaceholder:
    def test_sections_without_embeddings_get_zero_placeholder(self, tmp_path: Path):
        """When embedder returns no vectors, all sections use zero-vector (line 159)."""
        from tests.conftest import MockEmbedder
        import numpy as np

        class ZeroEmbedder(MockEmbedder):
            def embed(self, texts):
                return []  # no embeddings → all sections get zero placeholder

        doc = make_doc(n_sections=2)
        out = str(tmp_path / "zero.udf")
        writer = UDFWriter(ZeroEmbedder(), Quantizer("float16"))
        p = writer.write(doc, out)
        assert Path(p).exists()

        with zipfile.ZipFile(p) as zf:
            blob = zf.read("embeddings.bin")
        # 2 sections × 384 dims × 2 bytes (float16) — all zeros
        assert len(blob) == 2 * 384 * 2
        assert all(b == 0 for b in blob)
