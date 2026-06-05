"""Deterministic keyword extraction — populate section keywords WITHOUT an LLM.

The reader builds its BM25/keyword index from section ``keywords`` (+ title). When those are
empty (LLM-generated at ingest, usually skipped), hybrid search returns nothing and queries
fall straight to the Layer-4 full-document fallback. Extracting salient terms is deterministic
(frequency × specificity over non-stopwords), so DocNest can do it itself.

Pure-Python, dependency-free. See retrospective §5.2.
"""
from __future__ import annotations

import re
from collections import Counter

from docnest.models import Document

__all__ = ["extract_keywords", "enrich_keywords"]

_STOP = set(
    "the a an of to from in on at by for and or is are was were be been being this that "
    "these those it its with as it's we our their they them than into about above below "
    "report say says will would can could should may might must have has had do does did "
    "not no so if then else when where which who whom how what why all any each per via "
    "using used use new now also more most other some such only over under between within".split()
)


def extract_keywords(text: str, title: str = "", k: int = 8) -> list[str]:
    """Return up to ``k`` salient lowercase keywords (title terms first, then frequent terms)."""
    title_terms = [t for t in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", (title or "").lower())
                   if t not in _STOP]
    tokens = [t for t in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", (text or "").lower())
              if t not in _STOP]
    # Score = frequency, with a small bonus for longer (more specific) terms.
    freq = Counter(tokens)
    scored = sorted(freq, key=lambda w: (freq[w] + 0.1 * len(w)), reverse=True)
    out: list[str] = []
    for w in title_terms + scored:                      # title terms get priority
        if w not in out:
            out.append(w)
        if len(out) >= k:
            break
    return out


def enrich_keywords(doc: Document, k: int = 8) -> Document:
    """Populate each section's ``keywords`` deterministically (per-section no-op if set)."""
    for s in doc.sections:
        if s.keywords:
            continue
        s.keywords = extract_keywords(s.text or "", s.title or "", k=k)
    return doc
