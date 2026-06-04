"""Complex Tables · Step 3 — HTML rowspan/colspan expansion (test-first).

FAILS until HTMLParser._extract_table expands spans into a rectangular grid.
Skips if beautifulsoup4 is not installed.

Run: pytest tests/test_html_tables.py -v
"""
from __future__ import annotations

import pytest

bs4 = pytest.importorskip("bs4", reason="beautifulsoup4 not installed")
from bs4 import BeautifulSoup  # noqa: E402

from docnest.parsers.html import HTMLParser  # noqa: E402


def _extract(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return HTMLParser()._extract_table(soup.find("table"), 0)


class TestColspan:
    def test_colspan_repeats_value_across_columns(self):
        html = """
        <table>
          <tr><th>Region</th><th colspan="2">Sales</th></tr>
          <tr><td>Europe</td><td>10</td><td>20</td></tr>
        </table>"""
        t = _extract(html)
        assert t is not None
        assert t.headers == ["Region", "Sales", "Sales"]
        assert t.rows == [["Europe", "10", "20"]]
        # every row aligns to header width
        assert all(len(r) == len(t.headers) for r in t.rows)


class TestRowspan:
    def test_rowspan_carries_value_down(self):
        html = """
        <table>
          <tr><th>Group</th><th>Item</th></tr>
          <tr><td rowspan="2">A</td><td>x</td></tr>
          <tr><td>y</td></tr>
        </table>"""
        t = _extract(html)
        assert t is not None
        assert t.headers == ["Group", "Item"]
        assert t.rows == [["A", "x"], ["A", "y"]]   # 'A' carried into the 2nd row

    def test_combined_rowspan_colspan_aligned(self):
        html = """
        <table>
          <tr><th>Q</th><th colspan="2">Metrics</th></tr>
          <tr><td rowspan="2">Q1</td><td>rev</td><td>100</td></tr>
          <tr><td>cost</td><td>40</td></tr>
        </table>"""
        t = _extract(html)
        assert t is not None
        assert t.headers == ["Q", "Metrics", "Metrics"]
        assert t.rows == [["Q1", "rev", "100"], ["Q1", "cost", "40"]]
        assert all(len(r) == 3 for r in t.rows)


class TestPlainTableUnaffected:
    def test_simple_table_still_works(self):
        html = """
        <table>
          <tr><th>A</th><th>B</th></tr>
          <tr><td>1</td><td>2</td></tr>
          <tr><td>3</td><td>4</td></tr>
        </table>"""
        t = _extract(html)
        assert t.headers == ["A", "B"]
        assert t.rows == [["1", "2"], ["3", "4"]]
