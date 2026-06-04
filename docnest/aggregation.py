"""Deterministic table aggregation — the library does the math, not the LLM.

Pure-Python, dependency-free, offline, deterministic. Operates on the existing
``docnest.models.TableData`` (``headers`` + ``rows`` of string cells) and computes
sum / count / min / max / avg over a column, with an optional row filter.

Design (see docs/tasks/table-aggregation/ + ADR-0004):
  • ``parse_number`` — robust messy-cell → float (currency, %, ``x``, magnitude words,
    comma- and space-thousands separators).
  • ``TableQuery`` — wraps one ``TableData``; resolves columns fuzzily, filters rows
    (relational σ), folds a numeric column (relational aggregate).
  • Fail-closed — any ambiguity / parse failure returns ``ok=False`` with a reason,
    never a guessed number, never an exception.

Nothing in the library imports this yet; wiring into the reader query path is a
separate, gated task.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from docnest.models import TableData

__all__ = ["parse_number", "TableQuery", "AggregationResult"]

_OPS = {"sum", "count", "min", "max", "avg"}
_MAGNITUDES = (("billion", 1e9), ("million", 1e6), ("thousand", 1e3))
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_BLANKS = {"", "n/a", "na", "—", "–", "-", "tbd", "none", "null"}


def parse_number(cell: object) -> Optional[float]:
    """Parse a messy string cell into a canonical float, or ``None`` if non-numeric.

    Examples: ``"$4,050"`` → 4050.0, ``"12 550"`` → 12550.0, ``"99.97%"`` → 99.97,
    ``"1.24 billion"`` → 1.24e9, ``"5.8x"`` → 5.8, ``"38.7k"`` → 38700.0.
    Blanks / placeholders (``""``, ``"N/A"``, ``"—"``) and pure text → ``None``.
    """
    if cell is None:
        return None
    s = str(cell).strip()
    if s.lower() in _BLANKS:
        return None

    low = s.lower()
    mult = 1.0
    # Magnitude WORDS (word-bounded so "urban" is not read as "bn", etc.)
    for word, m in _MAGNITUDES:
        if re.search(rf"\b{word}\b", low):
            mult = m
            low = re.sub(rf"\b{word}\b", " ", low)
            break

    # Strip comma thousands-separators and join space thousands-separators
    cleaned = low.replace(",", "")
    cleaned = re.sub(r"(?<=\d)\s+(?=\d{3}\b)", "", cleaned)

    m = _NUM_RE.search(cleaned)
    if not m:
        return None
    val = float(m.group(0))

    # Suffix 'k' directly after the number ("38.7k") = ×1000 ('x', '%', units ignored)
    tail = cleaned[m.end():m.end() + 1]
    if tail == "k":
        mult *= 1e3
    return val * mult


def _norm(text: str) -> str:
    """Lowercase, replace non-alphanumerics with spaces, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text).lower())).strip()


def _unit_of(raw: str) -> Optional[str]:
    """Best-effort unit symbol of a raw cell (for reporting only)."""
    s = str(raw)
    if "%" in s:
        return "%"
    if "$" in s:
        return "$"
    if s.strip().lower().endswith("x"):
        return "x"
    return None


@dataclass
class AggregationResult:
    """Outcome of an aggregation. ``ok=False`` ⇒ could not answer (see ``reason``)."""
    ok: bool
    op: str
    value: Optional[float] = None
    unit: Optional[str] = None
    n_rows: int = 0          # contributing rows (numeric cells for sum/avg/min/max)
    skipped: int = 0         # candidate cells skipped as non-numeric
    reason: str = ""


class TableQuery:
    """Deterministic query/aggregation over a single ``TableData``."""

    def __init__(self, table: TableData) -> None:
        self._t = table
        self._headers_norm = [_norm(h) for h in table.headers]

    # ── column resolution ────────────────────────────────────────────────
    def resolve_column(self, name: str) -> Optional[int]:
        """Resolve a header by exact (normalized) then fuzzy token/substring match."""
        norm = _norm(name)
        if not norm:
            return None
        for i, h in enumerate(self._headers_norm):
            if h == norm:
                return i
        qtok = set(norm.split())
        best_score, best_i = 0.0, None
        for i, h in enumerate(self._headers_norm):
            htok = set(h.split())
            if not htok:
                continue
            inter = qtok & htok
            if inter:
                score = len(inter) / len(qtok | htok)
                if norm in h or h in norm:
                    score = max(score, 0.6)
            elif norm in h:
                score = 0.5
            else:
                continue
            if score > best_score:
                best_score, best_i = score, i
        return best_i if best_score >= 0.3 else None

    # ── cell access ──────────────────────────────────────────────────────
    def _cell(self, row: list[str], col: int) -> str:
        return row[col] if 0 <= col < len(row) else ""

    def numeric_column(self, name: str) -> list[tuple[int, float]]:
        """Return ``(row_index, value)`` for every numeric cell in the column."""
        col = self.resolve_column(name)
        if col is None:
            return []
        out: list[tuple[int, float]] = []
        for ri, row in enumerate(self._t.rows):
            v = parse_number(self._cell(row, col))
            if v is not None:
                out.append((ri, v))
        return out

    # ── row filter (relational σ) ─────────────────────────────────────────
    def filter_rows(self, col: str, op: str, value: str) -> list[int]:
        ci = self.resolve_column(col)
        if ci is None:
            return []
        nv = _norm(value)
        pv = parse_number(value)
        matched: list[int] = []
        for ri, row in enumerate(self._t.rows):
            cell = self._cell(row, ci)
            if op == "eq":
                if _norm(cell) == nv:
                    matched.append(ri)
            elif op == "contains":
                if nv and nv in _norm(cell):
                    matched.append(ri)
            elif op in ("gt", "lt"):
                cv = parse_number(cell)
                if cv is None or pv is None:
                    continue
                if (op == "gt" and cv > pv) or (op == "lt" and cv < pv):
                    matched.append(ri)
        return matched

    # ── aggregate (relational fold) ───────────────────────────────────────
    def aggregate(self, op: str, column: str,
                  where: Optional[tuple[str, str, str]] = None) -> AggregationResult:
        op = (op or "").lower()
        if op not in _OPS:
            return AggregationResult(False, op, reason=f"unsupported op: {op!r}")

        col = self.resolve_column(column)
        if col is None:
            return AggregationResult(False, op,
                                     reason=f"column not found: {column!r}")

        # Candidate row indices (relational selection)
        if where is not None:
            wcol, wop, wval = where
            if self.resolve_column(wcol) is None:
                return AggregationResult(False, op,
                                         reason=f"filter column not found: {wcol!r}")
            candidates = self.filter_rows(wcol, wop, wval)
        else:
            candidates = list(range(len(self._t.rows)))

        # COUNT = number of selected rows (numeric not required)
        if op == "count":
            return AggregationResult(True, op, value=float(len(candidates)),
                                     n_rows=len(candidates))

        # Numeric fold for sum/min/max/avg
        values, units = [], []
        for ri in candidates:
            raw = self._cell(self._t.rows[ri], col)
            v = parse_number(raw)
            if v is None:
                continue
            values.append(v)
            units.append(_unit_of(raw))
        skipped = len(candidates) - len(values)

        if not values:
            return AggregationResult(False, op, n_rows=0, skipped=skipped,
                                     reason="no numeric values to aggregate")

        if op == "sum":
            result = sum(values)
        elif op == "min":
            result = min(values)
        elif op == "max":
            result = max(values)
        else:  # avg
            result = sum(values) / len(values)

        present = [u for u in units if u]
        unit = max(set(present), key=present.count) if present else None
        return AggregationResult(True, op, value=result, unit=unit,
                                 n_rows=len(values), skipped=skipped)
