"""
HTML parser using BeautifulSoup.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from pathlib import Path

from docnest.parsers.base import IParser
from docnest.models import RawDocument, Section, TableData
from docnest.exceptions import ParseError

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class HTMLParser(IParser):
    """Parses HTML files using BeautifulSoup.

    Walks h1-h6 tags to build the section hierarchy and extracts
    <table> elements as TableData objects.  Requires beautifulsoup4
    (already a core dependency via pyproject.toml).
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".html", ".htm"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse an HTML file into a RawDocument."""
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {file_path}")

        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise ParseError(
                "beautifulsoup4 is required for HTML parsing. "
                "Run: pip install beautifulsoup4"
            ) from exc

        html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        doc_id = self._make_doc_id(file_path)

        # Title: prefer <title>, then first <h1>, then filename stem
        title_tag = soup.find("title")
        h1_tag = soup.find("h1")
        if title_tag and title_tag.get_text(strip=True):
            title = title_tag.get_text(strip=True)
        elif h1_tag:
            title = h1_tag.get_text(strip=True)
        else:
            title = path.stem.replace("-", " ").replace("_", " ").title()

        sections = self._extract_sections(soup)

        return RawDocument(
            doc_id=doc_id,
            title=title,
            source=str(path.resolve()),
            format="html",
            sections=sections,
        )

    # ------------------------------------------------------------------ #
    #  Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _extract_sections(self, soup: "BeautifulSoup") -> list[Section]:  # type: ignore[name-defined]
        """Walk headings in document order; collect body text and tables."""
        headings = soup.find_all(list(_HEADING_TAGS))
        if not headings:
            # No headings — wrap all body text in a single section
            body = soup.get_text(separator="\n", strip=True)
            if body:
                return [Section(id="", title="Document", level=1, text=body)]
            return []

        sections: list[Section] = []
        for heading in headings:
            level = _HEADING_TAGS[heading.name]
            heading_text = heading.get_text(strip=True)

            text_parts: list[str] = []
            tables: list[TableData] = []

            # Walk siblings until the next heading tag
            sibling = heading.next_sibling
            while sibling:
                tag_name = getattr(sibling, "name", None)
                if tag_name in _HEADING_TAGS:
                    break
                if tag_name == "table":
                    tbl = self._extract_table(sibling, len(tables))
                    if tbl:
                        tables.append(tbl)
                elif tag_name:
                    chunk = sibling.get_text(separator=" ", strip=True)
                    if chunk:
                        text_parts.append(chunk)
                elif isinstance(sibling, str) and sibling.strip():
                    text_parts.append(sibling.strip())
                sibling = sibling.next_sibling

            sections.append(Section(
                id="",
                title=heading_text,
                level=level,
                text=" ".join(text_parts),
                tables=tables,
            ))

        return sections

    def _extract_table(self, table_tag: "Tag", index: int) -> TableData | None:  # type: ignore[name-defined]
        """Convert a <table> element to a TableData object.

        Expands ``rowspan`` / ``colspan`` into a rectangular grid so every column
        lines up (a spanning cell's value is repeated across the cells it covers).
        """
        rows = table_tag.find_all("tr")
        if not rows:
            return None

        grid = self._expand_grid(rows)
        if not grid or not any(grid[0]):
            return None

        headers = grid[0]
        data_rows = [r for r in grid[1:] if any(c.strip() for c in r)]

        caption_tag = table_tag.find("caption")
        caption = caption_tag.get_text(strip=True) if caption_tag else None

        return TableData(
            table_id=f"tbl_{index + 1:03d}",
            caption=caption,
            headers=headers,
            rows=data_rows,
        )

    @staticmethod
    def _expand_grid(tr_tags) -> list[list[str]]:
        """Expand <tr> tags into a dense rectangular grid honouring row/col spans.

        Standard table-grid placement: each cell is written into every (row, col) it
        covers; cells already occupied by a rowspan from above are skipped.
        """
        occupied: dict[tuple, str] = {}
        max_cols = 0
        for r, tr in enumerate(tr_tags):
            c = 0
            for cell in tr.find_all(["th", "td"]):
                while (r, c) in occupied:           # skip cells filled by a rowspan above
                    c += 1
                val = cell.get_text(strip=True)
                try:
                    cs = max(1, int(cell.get("colspan", 1) or 1))
                    rs = max(1, int(cell.get("rowspan", 1) or 1))
                except (TypeError, ValueError):
                    cs = rs = 1
                for dr in range(rs):
                    for dc in range(cs):
                        occupied[(r + dr, c + dc)] = val
                c += cs
                max_cols = max(max_cols, c)
        if not occupied:
            return []
        n_rows = max(rr for rr, _ in occupied) + 1
        return [[occupied.get((r, c), "") for c in range(max_cols)] for r in range(n_rows)]
