"""
Fast PDF parser using PyMuPDF (fitz).

Works on text-based PDFs with zero ML model downloads.
Detects headings by relative font size — larger font = heading.
Perfect for resumes, reports, and any text-native PDF.

Use DoclingPDFParser for scanned/image PDFs that need OCR.

Phase: 1  |  Install: pip install pymupdf
Docs: https://pymupdf.readthedocs.io/
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from docnest.parsers.base import IParser
from docnest.models import RawDocument, Section, TableData
from docnest.exceptions import ParseError

if TYPE_CHECKING:
    from docnest.providers.ocr import IOCRProvider


class PyMuPDFParser(IParser):
    """Fast text-PDF parser using PyMuPDF — no ML models, no internet required.

    Heading detection: blocks with font size >= heading_threshold * median_font_size
    are treated as headings. The level is determined by relative font size bands.

    Usage:
        parser = PyMuPDFParser()
        raw = parser.parse("/path/to/resume.pdf")
    """

    def __init__(
        self,
        heading_threshold: float = 1.15,
        ocr: bool = False,
        ocr_provider: "IOCRProvider | None" = None,
        ocr_languages: Optional[list[str]] = None,
        ocr_dpi: int = 200,
        ocr_max_px: int = 2000,
        text_layer_min_chars: int = 20,
    ) -> None:
        """
        Args:
            heading_threshold: Font size multiplier above median to be a heading.
                               Default 1.15 = 15% larger than median body text.
            ocr: Enable OCR fallback for image-only pages (default off — text PDFs
                 need no OCR). When on, pages whose text layer has fewer than
                 ``text_layer_min_chars`` characters are rendered and OCR'd.
            ocr_provider: An IOCRProvider to use. Default None → EasyOCRProvider
                 (when ``ocr=True``), falling back to NullOCRProvider if EasyOCR
                 is not installed.
            ocr_languages: OCR language codes (e.g. ["hi", "en"]). Default ["en"].
            ocr_dpi: Render DPI for OCR (higher = sharper but slower). Default 200.
            ocr_max_px: Downscale the rendered page so its longest edge is at most
                 this many pixels — bounds OCR time on large images. Default 2000.
            text_layer_min_chars: A page with at least this many characters in its
                 text layer is treated as a text page (no OCR). Default 20.
        """
        self.heading_threshold = heading_threshold
        self._ocr = ocr
        self._ocr_dpi = ocr_dpi
        self._ocr_max_px = ocr_max_px
        self._text_layer_min_chars = text_layer_min_chars
        self._ocr_provider = self._resolve_ocr_provider(ocr, ocr_provider, ocr_languages)

    @staticmethod
    def _resolve_ocr_provider(
        ocr: bool,
        provider: "IOCRProvider | None",
        languages: Optional[list[str]],
    ) -> "IOCRProvider | None":
        """Pick the OCR provider. Default EasyOCR; graceful fallback to no-op."""
        if not ocr or provider is not None:
            return provider
        import warnings
        from docnest.providers.ocr import EasyOCRProvider, NullOCRProvider
        candidate = EasyOCRProvider(languages=languages or ["en"])
        if candidate.available:
            return candidate
        warnings.warn(
            "OCR requested but EasyOCR is not installed — falling back to no-op OCR. "
            "Install with: pip install docnest-ai[ocr-easyocr]",
            RuntimeWarning,
            stacklevel=3,
        )
        return NullOCRProvider()

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    def parse(self, file_path: str) -> RawDocument:
        """Parse a text-based PDF into a RawDocument.

        Args:
            file_path: Absolute or relative path to the PDF.

        Returns:
            RawDocument with sections extracted by font-size heading detection.

        Raises:
            ParseError: File missing, empty, or PyMuPDF fails.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise ParseError(f"PDF not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"PDF is empty: {path}")

        try:
            import fitz  # PyMuPDF  # type: ignore[import]
        except ImportError as exc:
            raise ParseError(
                "PyMuPDF not installed. Run: pip install pymupdf"
            ) from exc

        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            raise ParseError(f"PyMuPDF failed to open '{path.name}': {exc}") from exc

        try:
            blocks = self._extract_blocks(doc)
            title = self._extract_title(blocks, path)
            sections = self._build_sections(blocks)
        finally:
            doc.close()

        return RawDocument(
            doc_id=self._make_doc_id(file_path),
            title=title,
            source=str(path),
            format="pdf",
            sections=sections,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _extract_blocks(self, doc: object) -> list[dict]:
        """Extract all text blocks with font metadata from all pages."""
        blocks: list[dict] = []
        for page in doc:  # type: ignore[attr-defined]
            page_dict = page.get_text("dict", flags=0)  # type: ignore[attr-defined]
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:  # type 0 = text, skip images
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        blocks.append({
                            "text": text,
                            "size": round(span.get("size", 10), 1),
                            "bold": bool(span.get("flags", 0) & 2**4),  # bold flag
                        })

            # OCR fallback: only for image-only / near-empty text pages, and only
            # when OCR is enabled. Text pages are never OCR'd (fast).
            if self._ocr and self._ocr_provider is not None:
                layer = page.get_text("text").strip()  # type: ignore[attr-defined]
                if len(layer) < self._text_layer_min_chars:
                    ocr_text = self._ocr_page(page)
                    if ocr_text.strip():
                        # Uniform size → treated as body text (a scan has no font info)
                        blocks.append({"text": ocr_text.strip(), "size": 10.0, "bold": False})
        return blocks

    def _ocr_page(self, page: object) -> str:
        """Render a page to PNG (downscaled) and OCR it via the provider.

        Never raises — returns "" on any failure so a bad page can't crash parsing.
        """
        try:
            pix = page.get_pixmap(dpi=self._ocr_dpi)  # type: ignore[attr-defined]
            png = pix.tobytes("png")
            if max(pix.width, pix.height) > self._ocr_max_px:
                png = _downscale_png(png, self._ocr_max_px)
            return self._ocr_provider.extract_text(png)  # type: ignore[union-attr]
        except Exception:
            return ""

    def _median_font_size(self, blocks: list[dict]) -> float:
        """Compute the median font size across all blocks."""
        sizes = sorted(b["size"] for b in blocks if b["text"].strip())
        if not sizes:
            return 11.0
        mid = len(sizes) // 2
        return sizes[mid]

    def _extract_title(self, blocks: list[dict], path: Path) -> str:
        """Return the largest text block (likely the document title)."""
        if not blocks:
            return _filename_to_title(path.stem)
        largest = max(blocks, key=lambda b: b["size"])
        return largest["text"].strip() or _filename_to_title(path.stem)

    def _build_sections(self, blocks: list[dict]) -> list[Section]:
        """Group blocks into sections using font-size heading detection."""
        if not blocks:
            return []

        median = self._median_font_size(blocks)
        heading_min = median * self.heading_threshold

        # Collect unique heading font sizes to assign levels
        heading_sizes = sorted(
            {b["size"] for b in blocks if b["size"] >= heading_min},
            reverse=True,  # largest = level 1
        )
        size_to_level: dict[float, int] = {
            sz: min(i + 1, 6) for i, sz in enumerate(heading_sizes)
        }

        sections: list[Section] = []
        current: Optional[Section] = None

        for block in blocks:
            text = block["text"].strip()
            size = block["size"]
            is_bold = block["bold"]

            is_heading = (
                size >= heading_min or
                (is_bold and size >= median * 1.05 and len(text) < 100)
            )

            if is_heading and text:
                if current is not None:
                    current.text = current.text.strip()
                    sections.append(current)
                level = size_to_level.get(size, 1)
                current = Section(
                    id="",
                    title=text,
                    level=level,
                    text="",
                )
            else:
                if not text:
                    continue
                if current is None:
                    current = Section(id="", title="Introduction", level=1, text="")
                current.text += text + "\n"

        if current is not None:
            current.text = current.text.strip()
            sections.append(current)

        return sections


def _downscale_png(png_bytes: bytes, max_px: int) -> bytes:
    """Downscale a PNG so its longest edge is at most ``max_px`` pixels.

    Bounds OCR time on large page images. Returns the original bytes unchanged if
    it already fits or if Pillow is unavailable.
    """
    try:
        import io
        from PIL import Image  # type: ignore[import]
        img = Image.open(io.BytesIO(png_bytes))
        w, h = img.size
        longest = max(w, h)
        if longest <= max_px:
            return png_bytes
        scale = max_px / float(longest)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return png_bytes


def _filename_to_title(stem: str) -> str:
    """Convert a filename stem to a human-readable title.

    Handles CamelCase (GunjanTailor → Gunjan Tailor), hyphens,
    underscores, and numbers (SampleReport2024 → Sample Report 2024).
    """
    # 1. Insert space between a lowercase letter and an uppercase letter (CamelCase)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    # 2. Insert space between a letter and a digit boundary
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    # 3. Replace hyphens/underscores with spaces
    s = re.sub(r"[-_]+", " ", s)
    # 4. Collapse multiple spaces, then title-case each word
    return " ".join(s.split()).title()
