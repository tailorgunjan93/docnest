"""Deterministic key-number extraction — populate intelligence WITHOUT an LLM.

The Observer's-Tax eval showed the 0-token path is dead because `key_numbers` (which power
Layer 0) are LLM-generated at ingest and usually empty. Extracting figures from text is a
deterministic task (regex + label binding), so DocNest can do it itself — for free, offline,
every time. This revives Layer-0 numeric lookups.

Pure-Python, dependency-free. See the eval retrospective §5.1 and ADR-0008.
"""
from __future__ import annotations

import re

from docnest.models import Document, KeyNumber

__all__ = ["extract_key_numbers", "enrich_key_numbers", "parse_number"]

# Ordered most-specific-first so "$18,400" isn't split into 18 and 400.
_PATTERNS = [
    ("money",    r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:million|billion|trillion|M|B|K|k)?"),
    ("percent",  r"\d+(?:\.\d+)?\s?%"),
    ("duration", r"\d+(?:\.\d+)?\s?(?:ms|seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\b"),
    ("ratio",    r"\d+(?:\.\d+)?\s?[x×]\b"),
    ("count",    r"\b\d[\d,]*(?:\.\d+)?\b"),
]
_NUM_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _PATTERNS))
_BULLET_LABEL = re.compile(r"\*\*\s*([^*:]+?)\s*:?\s*\*\*\s*:?")
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s")          # "1. ", "2) "
# An identifier has a LETTER immediately before the number (v2, AZ-204, H2). We must NOT
# treat a unit that FOLLOWS the number (142ms, 8x) as an identifier — that's a metric.
_IDENTIFIER_PREFIX = re.compile(r"[A-Za-z]-?$")
_FILLERS = {"the", "a", "an", "of", "to", "from", "and", "is", "was", "are", "now",
            "all", "with", "at", "by", "in", "on", "after", "down", "up", "for",
            "then", "it", "its", "this", "that", "we", "our"}


def parse_number(raw: str) -> float | None:
    """Canonical float for a raw figure (strips $, %, commas, x, unit words/multipliers)."""
    s = str(raw).strip().lower()
    mult = 1.0
    for word, m in (("trillion", 1e12), ("billion", 1e9), ("million", 1e6), ("thousand", 1e3)):
        if re.search(rf"\b{word}\b", s):
            mult = m
            s = re.sub(rf"\b{word}\b", " ", s)
            break
    cleaned = s.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not m:
        return None
    val = float(m.group(0))
    if cleaned[m.end():m.end() + 1] == "k":
        mult *= 1e3
    return val * mult


_INLINE_LABEL = re.compile(r"([A-Za-z][A-Za-z0-9 \-/&]{1,40}?)\s*:\s*\**\s*$")


def _label_for(line: str, span_start: int) -> str:
    """Bind a number to the nearest preceding label — the closest ``Label:`` (handles
    ``**Uptime:**`` and a parenthetical ``(SLA target: …``), else the preceding noun words."""
    head = line[:span_start]
    m = _INLINE_LABEL.search(head.rstrip())
    if m:
        return m.group(1).strip(" *(")
    words = re.findall(r"[A-Za-z][A-Za-z\-/&]+", head)
    kept = [w for w in words if w.lower() not in _FILLERS]
    return " ".join(kept[-4:]).strip()


def _acronym_prefixed(head: str) -> bool:
    """True if the token immediately before the number is an all-caps acronym (ISO 27001)."""
    toks = re.findall(r"\S+", head)
    return bool(toks) and bool(re.fullmatch(r"[A-Z]{2,}", toks[-1].strip(".,")))


def extract_key_numbers(text: str, section_id: str) -> list[KeyNumber]:
    """Extract labelled figures from section text. Deterministic; no LLM.

    Drops noise: ordered-list markers, bare years (1900–2099), and numbers embedded in
    identifiers (AZ-204, ISO 27001). Requires a non-empty bound label.
    """
    out: list[KeyNumber] = []
    seen: set[tuple] = set()
    for line in (text or "").splitlines():
        is_list_line = bool(_LIST_MARKER.match(line))
        for m in _NUM_RE.finditer(line):
            raw = m.group(0).strip()
            kind = m.lastgroup
            # Skip list-marker ordinals at the very start of a list line.
            if is_list_line and m.start() < _LIST_MARKER.match(line).end():
                continue
            # Skip identifiers: a letter/dash immediately before the number (AZ-204, v2) or
            # an all-caps acronym prefix (ISO 27001). Units that FOLLOW (142ms) are kept.
            left = line[:m.start()]
            if _IDENTIFIER_PREFIX.search(left) or _acronym_prefixed(left):
                continue
            canon = parse_number(raw)
            # Skip bare years presented as a plain count (no $, %, unit).
            if kind == "count" and canon is not None and 1900 <= canon <= 2099 \
                    and "." not in raw:
                continue
            label = _label_for(line, m.start())
            if not label:
                continue
            key = (label.lower(), raw)
            if key in seen:
                continue
            seen.add(key)
            unit = "%" if kind == "percent" else ("USD" if raw.lstrip().startswith("$") else None)
            out.append(KeyNumber(label=label, value=raw, unit=unit, section=section_id))
    return out


def enrich_key_numbers(doc: Document, max_numbers: int = 64) -> Document:
    """Populate ``doc.key_numbers`` deterministically (no-op if already populated)."""
    if doc.key_numbers:
        return doc
    collected: list[KeyNumber] = []
    for s in doc.sections:
        collected.extend(extract_key_numbers(s.text or "", s.id))
        if len(collected) >= max_numbers:
            break
    doc.key_numbers = collected[:max_numbers]
    return doc
