"""
Section Normaliser — Stage 2 of the DocNest pipeline.

Assigns hierarchical §ids to every section in a RawDocument and builds
the parent/child tree. Also counts tokens and normalises table column widths.

Phase: 1 | Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from docnest.models import RawDocument, Document, Section


class SectionNormaliser:
    """Assigns §ids to sections and builds the parent/child hierarchy.

    Input: RawDocument (sections with id="", from any parser)
    Output: Document (sections with §ids, parent_id, children links)

    Section ID rules:
    Top-level heading → §1, §2, §3 ...
    Second-level → §1.1, §1.2, §2.1 ...
    Third-level → §1.1.1, §1.1.2 ...
    Maximum depth: 6 levels (H1–H6)

    When heading levels are skipped (e.g. H1 → H3 without an H2),
    the §id is compacted to reflect the actual nesting depth rather
    than inserting zero-padded intermediate segments. For example,
    an H3 directly under an H1 gets §1.1 (not §1.0.1), because it
    occupies depth 1 in the hierarchy.

    The depth of each section is computed dynamically from the
    ancestor stack: a section's depth is one more than its parent's
    depth. The parent is the nearest preceding heading with a lower
    raw level number.
    """

    def normalise(self, raw: RawDocument) -> Document:
        """Assign §ids and build parent/child links.

        Args:
            raw: RawDocument from any parser (sections without §ids).

        Returns:
            Document with fully linked section hierarchy.
        """
        counters = [0] * 6  # counters per compact depth
        # Stack of (raw_level, §id, depth) for ancestor tracking
        stack: list[tuple[int, str, int]] = []
        section_map: dict[str, Section] = {}

        for section in raw.sections:
            raw_level = max(1, min(6, section.level))

            # Pop stack until we find a parent (strictly lower raw level)
            while stack and stack[-1][0] >= raw_level:
                stack.pop()

            # Determine depth: one more than parent's depth, or 0 for top
            depth = stack[-1][2] + 1 if stack else 0

            # Increment counter at this depth, reset all deeper counters
            counters[depth] += 1
            for i in range(depth + 1, 6):
                counters[i] = 0

            # Build compact §id from counters at depths 0..depth
            section_id = "§" + ".".join(str(counters[i]) for i in range(depth + 1))
            section.id = section_id

            # Set parent link
            if stack:
                parent_id = stack[-1][1]
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
            stack.append((raw_level, section_id, depth))

        return Document(
            doc_id=raw.doc_id,
            title=raw.title,
            source=raw.source,
            format=raw.format,
            sections=raw.sections,
        )
