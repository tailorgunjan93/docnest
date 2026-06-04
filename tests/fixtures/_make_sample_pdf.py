"""Generate a small structured sample PDF for the Docling integration tests.

Produces tests/fixtures/sample_text.pdf with a title, headings, paragraphs and a
bordered table (so DoclingPDFParser's TableFormer has a table to detect).
License-clean and deterministic — no downloaded/third-party content.

Run: python tests/fixtures/_make_sample_pdf.py
"""
from pathlib import Path
import fitz

OUT = Path(__file__).parent / "sample_text.pdf"


def main() -> None:
    doc = fitz.open()
    page = doc.new_page()  # A4-ish default

    def text(x, y, s, size, bold=False):
        page.insert_text((x, y), s, fontsize=size,
                         fontname="helv" if not bold else "hebo")

    # Title (large) + headings (medium) so font-size heading detection has levels
    text(72, 80, "Quarterly Business Report", 22, bold=True)
    text(72, 120, "Revenue Summary", 16, bold=True)
    text(72, 145, "Revenue grew across all regions in the third quarter.", 11)
    text(72, 162, "The table below breaks down revenue by region and quarter.", 11)

    # Bordered table (header row + 3 data rows, 4 columns)
    headers = ["Region", "Q1", "Q2", "Q3"]
    rows = [
        ["Europe", "38.1", "41.0", "45.2"],
        ["Asia", "29.3", "35.6", "41.7"],
        ["Americas", "47.0", "49.5", "52.1"],
    ]
    x0, y0 = 72, 185
    col_w, row_h = 110, 26
    grid = [headers] + rows
    for r, rowvals in enumerate(grid):
        for c, val in enumerate(rowvals):
            rect = fitz.Rect(x0 + c * col_w, y0 + r * row_h,
                             x0 + (c + 1) * col_w, y0 + (r + 1) * row_h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 5, rect.y0 + 17), str(val),
                             fontsize=10, fontname="hebo" if r == 0 else "helv")

    text(72, y0 + len(grid) * row_h + 40, "Outlook", 16, bold=True)
    text(72, y0 + len(grid) * row_h + 65,
         "Management expects continued growth into the next fiscal year.", 11)

    doc.save(str(OUT))
    doc.close()
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
