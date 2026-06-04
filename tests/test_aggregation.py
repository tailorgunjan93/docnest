"""Task: Deterministic Table Aggregation — test-first (Phase 3).

These FAIL until docnest/aggregation.py lands. They pin the behaviour described in
docs/tasks/table-aggregation/ and ADR-0004: exact, deterministic, fail-closed
aggregation over TableData — no LLM, no network.

Run: pytest tests/test_aggregation.py -v
"""
from __future__ import annotations

import pytest

from docnest.models import TableData


# ── parse_number ─────────────────────────────────────────────────────────────

class TestParseNumber:
    @pytest.mark.parametrize("raw,expected", [
        ("$4,050", 4050.0),
        ("12 550", 12550.0),          # space thousands-separator
        ("23,400", 23400.0),
        ("1,234.56", 1234.56),
        ("99.97%", 99.97),
        ("5.8x", 5.8),
        ("1.24 billion", 1_240_000_000.0),
        ("210 million", 210_000_000.0),
        ("38.7k", 38_700.0),
        ("  142ms ", 142.0),
        ("-12.5", -12.5),
        ("7600", 7600.0),
    ])
    def test_parses_messy_cells(self, raw, expected):
        from docnest.aggregation import parse_number
        assert parse_number(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", ["", "  ", "N/A", "n/a", "—", "-", "TBD", "hello", None])
    def test_non_numeric_is_none(self, raw):
        from docnest.aggregation import parse_number
        assert parse_number(raw) is None


# ── fixtures ─────────────────────────────────────────────────────────────────

def _revenue_table() -> TableData:
    # Acme Q1/Q2 shape
    return TableData(
        table_id="rev", caption="Revenue",
        headers=["Product", "Q1", "Annual Total"],
        rows=[
            ["DataSync Pro", "4200", "23,400"],
            ["CloudVault", "3100", "20,300"],
            ["SecureID", "1800", "9,900"],
            ["AnalyticsEdge", "2500", "14,100"],
            ["SupportDesk", "950", "4,320"],
        ],
    )


def _accounts_table() -> TableData:
    # Acme Q8 shape: sum ARR where tier == Enterprise → 7600
    return TableData(
        table_id="acc", caption="Top Accounts",
        headers=["Account", "Tier", "ARR (USD thousands)", "Region"],
        rows=[
            ["Globex", "Enterprise", "3,200", "North America"],
            ["Initech", "Mid-Market", "1,500", "Europe"],
            ["Umbrella", "Enterprise", "2,600", "Asia Pacific"],
            ["Stark", "SMB", "400", "North America"],
            ["Wayne", "Enterprise", "1,800", "Europe"],
        ],
    )


# ── column resolution ────────────────────────────────────────────────────────

class TestResolveColumn:
    def test_exact_and_case_insensitive(self):
        from docnest.aggregation import TableQuery
        q = TableQuery(_revenue_table())
        assert q.resolve_column("Q1") == 1
        assert q.resolve_column("annual total") == 2

    def test_fuzzy_suffix_match(self):
        from docnest.aggregation import TableQuery
        q = TableQuery(_accounts_table())
        assert q.resolve_column("ARR") == 2          # → "ARR (USD thousands)"

    def test_unknown_column_returns_none(self):
        from docnest.aggregation import TableQuery
        assert TableQuery(_revenue_table()).resolve_column("EBITDA") is None


# ── aggregation: happy path ──────────────────────────────────────────────────

class TestAggregate:
    def test_sum_column(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_revenue_table()).aggregate("sum", "Q1")
        assert r.ok and r.value == pytest.approx(12550.0) and r.n_rows == 5

    def test_max_column(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_revenue_table()).aggregate("max", "Annual Total")
        assert r.ok and r.value == pytest.approx(23400.0)

    def test_count_and_avg(self):
        from docnest.aggregation import TableQuery
        q = TableQuery(_revenue_table())
        assert q.aggregate("count", "Q1").value == 5
        assert q.aggregate("avg", "Q1").value == pytest.approx(12550.0 / 5)

    def test_sum_with_filter_acme_q8(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_accounts_table()).aggregate(
            "sum", "ARR", where=("Tier", "eq", "Enterprise"))
        assert r.ok
        assert r.value == pytest.approx(7600.0)      # 3200 + 2600 + 1800
        assert r.n_rows == 3

    def test_filter_contains_and_numeric_predicate(self):
        from docnest.aggregation import TableQuery
        q = TableQuery(_accounts_table())
        r = q.aggregate("count", "ARR", where=("Region", "contains", "America"))
        assert r.ok and r.value == 2
        r2 = q.aggregate("sum", "ARR", where=("ARR", "gt", "2000"))
        assert r2.ok and r2.value == pytest.approx(3200 + 2600)


# ── edge / negative: fail closed, never guess, never crash ───────────────────

class TestFailClosed:
    def test_unknown_column_fails(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_revenue_table()).aggregate("sum", "EBITDA")
        assert not r.ok and r.value is None and "EBITDA" in r.reason

    def test_non_numeric_column_fails(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_revenue_table()).aggregate("sum", "Product")
        assert not r.ok and r.value is None

    def test_filter_matches_nothing(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_accounts_table()).aggregate(
            "sum", "ARR", where=("Tier", "eq", "Government"))
        assert not r.ok
        # count over empty match is a valid 0, not a failure
        c = TableQuery(_accounts_table()).aggregate(
            "count", "ARR", where=("Tier", "eq", "Government"))
        assert c.ok and c.value == 0

    def test_empty_table(self):
        from docnest.aggregation import TableQuery
        t = TableData(table_id="e", caption=None, headers=["A", "B"], rows=[])
        assert TableQuery(t).aggregate("count", "A").value == 0
        assert not TableQuery(t).aggregate("sum", "A").ok

    def test_ragged_row_does_not_crash(self):
        from docnest.aggregation import TableQuery
        t = TableData(table_id="r", caption=None, headers=["A", "B"],
                      rows=[["1", "2"], ["3"]])  # short row
        r = TableQuery(t).aggregate("sum", "A")
        assert r.ok and r.value == pytest.approx(4.0)

    def test_skipped_non_numeric_cells_counted(self):
        from docnest.aggregation import TableQuery
        t = TableData(table_id="m", caption=None, headers=["V"],
                      rows=[["10"], ["N/A"], ["20"], ["pending"]])
        r = TableQuery(t).aggregate("sum", "V")
        assert r.ok and r.value == pytest.approx(30.0)
        assert r.n_rows == 2 and r.skipped == 2

    def test_unknown_op_fails(self):
        from docnest.aggregation import TableQuery
        r = TableQuery(_revenue_table()).aggregate("median", "Q1")
        assert not r.ok
