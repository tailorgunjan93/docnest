"""
Section Normaliser — Stage 2 of the DOCNEST pipeline.

Assigns hierarchical §ids to every section in a RawDocument and builds
the parent/child tree. This is what turns a flat list of sections into
a navigable library structure.

Phase: 1  |  Issue: github.com/tailorgunjan93/DOCNESTd/issues/2
Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
Design pattern: single responsibility — normaliser only assigns ids and links.
"""

from __future__ import annotations
from docnest.models import RawDocument, Document, Section


class SectionNormaliser:
    """Assigns §ids to sections and builds the parent/child hierarchy.

    Input:  RawDocument  (sections without §ids, from any parser)
    Output: Document     (sections with §ids, parent_id, children links)

    Section ID rules:
        Top-level heading   → §1, §2, §3 ...
        Second-level        → §1.1, §1.2, §2.1 ...
        Third-level         → §1.1.1, §1.1.2 ...
        Maximum depth: 6 levels

    TODO (Phase 1 — Issue #2):
        1. Walk sections in document order
        2. Track current counters per level: [0, 0, 0, 0, 0, 0]
        3. On encountering a heading at level N:
               increment counter[N-1]
               reset counters[N:] to 0
               build id from non-zero counters joined by '.'
               prefix with '§'
        4. Track a stack to determine parent_id
        5. Add section.id to parent's children list
        6. Return Document with all sections linked
    """

    def normalise(self, raw: RawDocument) -> Document:
        """Assign §ids and build parent/child links.

        Args:
            raw: RawDocument from any parser (sections without §ids).

        Returns:
            Document with fully linked section hierarchy.
        """
        # TODO: Implement §id assignment
        raise NotImplementedError(
            "SectionNormaliser not yet implemented. "
            "See issue #2: github.com/tailorgunjan93/DOCNESTd/issues/2"
        )

    def _build_section_id(self, counters: list[int], level: int) -> str:
        """Build a §id string from the current level counters.

        Args:
            counters: Current count at each heading level [l1, l2, l3, ...]
            level: Current heading level (1-based)

        Returns:
            Section id string, e.g. '§1.2.3'
        """
        # TODO: Join non-zero counters up to current level with '.'
        raise NotImplementedError
