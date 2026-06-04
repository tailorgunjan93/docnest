"""Passage chunking — make large sections retrievable.

Splits a section's prose into bounded, boundary-aware **passages** so each passage can be
embedded separately. A huge section (e.g. a 101k-char appendix) would otherwise get one
truncated embedding, hiding its content from dense retrieval (ADR-0007).

Pure-Python, deterministic, dependency-free. Operates on prose text only — tables
(`TableData`) are kept whole by the caller and never split here. Net-new; wiring into the
retrieval build path / `.udf` are separate, gated steps.
"""
from __future__ import annotations

import re

__all__ = ["chunk_text"]

_PARA_RE = re.compile(r"\n\s*\n")          # blank-line paragraph breaks
_SENT_RE = re.compile(r"(?<=[.!?])\s+")    # sentence boundaries


def _hard_split(s: str, max_chars: int) -> list[str]:
    """Last resort: split a boundary-less run into fixed-size windows."""
    return [s[i:i + max_chars] for i in range(0, len(s), max_chars)]


def _units(text: str, max_chars: int) -> list[str]:
    """Break text into units each <= max_chars: paragraphs → sentences → hard windows."""
    units: list[str] = []
    for para in _PARA_RE.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            units.append(para)
            continue
        for sent in _SENT_RE.split(para):
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) <= max_chars:
                units.append(sent)
            else:
                units.extend(_hard_split(sent, max_chars))
    return units


def chunk_text(text: str, max_chars: int = 2000, overlap: int = 200) -> list[str]:
    """Split prose into passages, each ``<= max_chars``, on natural boundaries.

    Consecutive passages share up to ``overlap`` characters (best-effort — dropped when it
    would exceed ``max_chars``). Text already within ``max_chars`` returns a single passage;
    empty/whitespace returns ``[]``.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    if max_chars <= 0:
        return [text]
    overlap = max(0, min(overlap, max_chars // 2))

    units = _units(text, max_chars)
    passages: list[str] = []
    buf = ""
    for u in units:
        if not buf:
            buf = u
            continue
        candidate = f"{buf} {u}"
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            passages.append(buf)
            tail = buf[-overlap:] if overlap else ""
            buf = f"{tail} {u}".strip() if tail else u
            if len(buf) > max_chars:        # overlap would overflow → drop it
                buf = u
    if buf:
        passages.append(buf)
    return passages
