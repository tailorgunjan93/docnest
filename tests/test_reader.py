"""Tests for UDFIndex and five-layer query resolution.

Phase: 4  |  Run: pytest tests/test_reader.py -v
"""
import pytest


class TestUDFIndex:
    """TODO (Phase 4): Uncomment after UDFIndex is implemented."""

    # def test_load_valid_udf(self, tmp_path):
    #     from docforge.reader import UDFIndex
    #     # Create a minimal .udf fixture, then load it
    #     index = UDFIndex.load("tests/fixtures/test.udf")
    #     assert index.catalogue is not None

    # def test_layer_0_answers_summary_question(self):
    #     index = load_test_index()
    #     result = index.query("What is this document about?")
    #     assert result.layer_used == 0
    #     assert result.tokens_used == 0
    #     assert result.answer

    # def test_layer_1_navigates_to_section(self):
    #     index = load_test_index()
    #     result = index.query("revenue breakdown")
    #     assert result.layer_used == 1
    #     assert result.navigate_to is not None
    #     assert result.navigate_to.startswith("§")

    pass
