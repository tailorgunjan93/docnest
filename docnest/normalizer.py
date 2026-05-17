"""
Section Normaliser — Stage 2 of the DocNest pipeline.

Assigns hierarchical §ids to every section in a RawDocument and builds
the parent/child tree. Also counts tokens and normalises table column widths.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from docnest.models import RawDocument, Document, Section


class SectionNormaliser:
    """Assigns §ids to sections and builds the parent/child hierarchy.

    Input:  RawDocument  (sections with id="", from any parser)
    Output: Document     (sections with §ids, parent_id, children links)

    Section ID rules:
        Top-level heading  → §1, §2, §3 ...
        Second-level       → §1.1, §1.2, §2.1 ...
        Third-level        → §1.1.1, §1.1.2 ...
        Maximum depth: 6 levels (H1–H6)
    """

    def normalise(self, raw: RawDocument) -> Document:
        """Assign §ids and build parent/child links.

        Args:
            raw: RawDocument from any parser (sections without §ids).

        Returns:
            Document with fully linked section hierarchy.
        """
        counters = [0] * 6          # [l1, l2, l3, l4, l5, l6]
        stack: list[str] = []        # §ids of ancestors at each depth
        section_map: dict[str, Section] = {}

        for section in raw.sections:
            level = max(1, min(6, section.level))
            idx = level - 1

            # Increment this level, reset all deeper levels
            counters[idx] += 1
            for i in range(idx + 1, 6):
                counters[i] = 0

            # Build §id from counters 0..level-1
            section_id = self._build_section_id(counters, level)
            section.id = section_id

            # Determine parent_id by trimming stack to parent depth
            while len(stack) >= level:
                stack.pop()

            if stack:
                parent_id = stack[-1]
                section.parent_id = parent_id
                parent = section_map.get(parent_id)
                if parent and section_id not in parent.children:
                    parent.children.append(section_id)
            else:
                section.parent_id = None

            # Approximate token count: words * 1.3 (GPT tokenisation heuristic)
            section.token_count = int(len(section.text.split()) * 1.3)

            # Normalise tables: ensure all rows same width as headers
            for table in section.tables:
                n = len(table.headers)
                if n == 0:
                    continue
                normalised = []
                for row in table.rows:
                    if len(row) < n:
                        row = row + [""] * (n - len(row))
                    elif len(row) > n:
                        row = row[:n]
                    normalised.append(row)
                table.rows = normalised

            section_map[section_id] = section
            stack.append(section_id)

        return Document(
            doc_id=raw.doc_id,
            title=raw.title,
            source=raw.source,
            format=raw.format,
            sections=raw.sections,
        )

    def _build_section_id(self, counters: list[int], level: int) -> str:
        """Build a §id string from the current level counters.

        Args:
            counters: Current count at each heading level [l1, l2, l3, ...]
            level: Current heading level (1-based)

        Returns:
            Section id string, e.g. '§1.2.3'
        """
        return "§" + ".".join(str(counters[i]) for i in range(level))
