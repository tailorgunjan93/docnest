"""
PDF parser using Docling.

Handles text-based PDFs (headings, paragraphs, tables) and scanned PDFs
(OCR via Docling's built-in Tesseract integration).

Tables are extracted as structured TableData objects — never as flat strings.
Images are captured as ImageRef entries with asset paths.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
Docling docs: https://ds4sd.github.io/docling/
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from docnest.parsers.base import IParser
from docnest.models import RawDocument, Section, TableData, ImageRef
from docnest.exceptions import ParseError


# Docling label strings for each content type
_HEADING_LABELS = {"section_header", "title"}
_TEXT_LABELS = {"text", "paragraph", "list_item", "caption", "footnote"}
_TABLE_LABEL = "table"
_PICTURE_LABEL = "picture"
_IGNORE_LABELS = {"page_header", "page_footer", "page_number"}


class DoclingPDFParser(IParser):
    """Parses PDF files using Docling (text-based and scanned via OCR).

    Docling handles layout analysis, table detection, and heading hierarchy
    automatically. This parser maps Docling output to DocNest's RawDocument
    model, section-by-section.

    Usage:
        parser = DoclingPDFParser()
        raw = parser.parse("/path/to/report.pdf")
        # raw.sections        → list of Section objects
        # raw.sections[n].tables → list of TableData objects
    """

    # Pages-per-chunk threshold: files larger than this get auto-chunked.
    # 20 pages keeps peak RAM under ~1 GB for typical dense PDFs.
    _AUTO_CHUNK_THRESHOLD_PAGES = 30

    def __init__(
        self,
        ocr: bool = False,
        table_structure: bool = True,
        generate_images: bool = False,
        images_scale: float = 1.0,
        chunk_pages: int = 0,
        pdf_backend: str = "pypdfium2",
        ocr_engine: str = "auto",
        ocr_lang: Optional[list[str]] = None,
        tesseract_cmd: Optional[str] = None,
        tessdata_path: Optional[str] = None,
        force_full_page_ocr: bool = False,
    ) -> None:
        """Initialise the PDF parser.

        Args:
            ocr: Enable OCR for scanned PDFs (requires downloading ML models).
                 Default False — text-based PDFs don't need OCR.
            ocr_engine: Which OCR engine to use when ``ocr=True``.
                 ``"auto"`` (default) — Docling's built-in default (RapidOCR;
                 Latin/CJK scripts). ``"easyocr"`` — EasyOCR, pure-Python (no
                 system binary), supports Devanagari/Hindi and many scripts.
                 ``"tesseract"`` — Tesseract CLI (needs the system binary +
                 language packs), also supports Devanagari/Hindi.
            ocr_lang: OCR language codes for the chosen engine. Engine-specific:
                 EasyOCR uses 2-letter codes (``["hi", "en"]``); Tesseract uses
                 ISO 639-2 codes (``["hin", "eng"]``). Default None → the
                 engine's own default.
            tesseract_cmd: Path to the ``tesseract`` executable (Tesseract engine
                 only). Default None → resolve ``tesseract`` from PATH.
            tessdata_path: Directory holding Tesseract ``*.traineddata`` files
                 (Tesseract engine only). Default None → Tesseract's own default
                 / the ``TESSDATA_PREFIX`` environment variable.
            force_full_page_ocr: OCR the entire page rather than only detected
                 bitmap regions — needed for fully-scanned/image pages. Default
                 False.
            table_structure: Use ML table structure analysis. Default True,
                 set False for faster parsing without ML model downloads.
            generate_images: Render page/picture images (increases RAM usage
                 significantly). Default False.
            images_scale: Rendering scale for page images (lower = less RAM).
                 Only relevant when generate_images=True. Default 1.0.
            chunk_pages: Process this many pages at a time to cap memory usage.
                 0 = auto (uses _AUTO_CHUNK_THRESHOLD_PAGES for files >30 pages).
                 Set explicitly, e.g. chunk_pages=20, to override auto behaviour.
                 Chunking splits the PDF via PyMuPDF (fitz), processes each chunk
                 with full Docling quality, then merges sections — no quality loss.
            pdf_backend: PDF rendering backend to use.
                 ``"pypdfium2"`` (default) — memory-efficient, constant ~3.9 GB RAM,
                 no memory accumulation across pages.
                 ``"docling"`` — default Docling C++ backend (dlparse), higher
                 quality but can accumulate memory on large PDFs causing OOM.
        """
        self._ocr = ocr
        self._table_structure = table_structure
        self._generate_images = generate_images
        self._images_scale = images_scale
        self._chunk_pages = chunk_pages
        self._pdf_backend = pdf_backend
        self._ocr_engine = ocr_engine
        self._ocr_lang = ocr_lang
        self._tesseract_cmd = tesseract_cmd
        self._tessdata_path = tessdata_path
        self._force_full_page_ocr = force_full_page_ocr
        # Lazy-loaded — Docling model init is expensive (~3-5 s first call)
        self._converter: object | None = None

    # ------------------------------------------------------------------ #
    #  IParser interface                                                   #
    # ------------------------------------------------------------------ #

    def supports(self, file_path: str) -> bool:
        """Return True for .pdf files."""
        return file_path.lower().endswith(".pdf")

    def parse(self, file_path: str) -> RawDocument:
        """Parse a PDF into a RawDocument.

        For large PDFs the file is automatically split into page chunks so that
        Docling's ML models run on each chunk sequentially — capping peak RAM
        while preserving full table-structure quality.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            RawDocument with sections, tables, and images extracted.
            Section ids (§N) are NOT assigned here — the Normaliser does that.

        Raises:
            ParseError: File missing, empty, or Docling conversion failed.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise ParseError(f"PDF not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"PDF is empty: {path}")

        # Decide whether to chunk based on page count
        total_pages = self._count_pages(path)
        chunk_size = self._chunk_pages or (
            self._AUTO_CHUNK_THRESHOLD_PAGES
            if total_pages > self._AUTO_CHUNK_THRESHOLD_PAGES
            else 0
        )

        if chunk_size and total_pages > chunk_size:
            return self._parse_chunked(path, total_pages, chunk_size)

        return self._parse_single(path, file_path)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _count_pages(self, path: Path) -> int:
        """Return page count using PyMuPDF (fitz) if available, else 0."""
        try:
            import fitz  # type: ignore[import]
            with fitz.open(str(path)) as pdf:
                return len(pdf)
        except Exception:
            return 0  # fitz not installed or failed → skip chunking

    def _parse_single(self, path: Path, original_path: str) -> RawDocument:
        """Run Docling on the whole file and return a RawDocument."""
        try:
            result = self._get_converter().convert(str(path))  # type: ignore[union-attr]
        except Exception as exc:
            raise ParseError(
                f"Docling failed to convert '{path.name}': {exc}"
            ) from exc

        # Warn on partial success (std::bad_alloc etc.)
        try:
            from docling.datamodel.base_models import ConversionStatus  # type: ignore[import]
            if result.status == ConversionStatus.PARTIAL_SUCCESS:
                failed_pages = [
                    p.page_no for p in result.pages
                    if getattr(p, "status", None) not in (
                        None, "success", ConversionStatus.SUCCESS
                    )
                ]
                import warnings
                warnings.warn(
                    f"Docling processed '{path.name}' with partial success — "
                    f"{len(failed_pages)} page(s) failed "
                    f"(pages {failed_pages[:10]}{'...' if len(failed_pages) > 10 else ''}). "
                    f"Tip: DoclingPDFParser(chunk_pages=20) processes large PDFs in "
                    f"memory-bounded chunks with no quality loss.",
                    RuntimeWarning,
                    stacklevel=4,
                )
            elif result.status not in (
                ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS
            ):
                raise ParseError(
                    f"Docling conversion failed for '{path.name}' "
                    f"(status={result.status}). "
                    f"Try DoclingPDFParser(chunk_pages=20) for large PDFs."
                )
        except ImportError:
            pass  # older Docling without ConversionStatus

        doc = result.document
        title = self._extract_title(doc, path)
        sections = self._build_sections(doc, doc)

        # Full-page OCR fallback: when a page is a single image, Docling places
        # the OCR'd text in ``doc.texts`` but the body tree (iterate_items) holds
        # only the picture — so _build_sections recovers no text. Rebuild from
        # ``doc.texts`` directly so scanned/image-only pages aren't lost.
        if not any((s.text or "").strip() for s in sections):
            recovered = self._sections_from_texts(doc)
            if recovered:
                sections = recovered

        return RawDocument(
            doc_id=self._make_doc_id(original_path),
            title=title,
            source=str(path),
            format="pdf",
            sections=sections,
        )

    def _parse_chunked(
        self, path: Path, total_pages: int, chunk_size: int
    ) -> RawDocument:
        """Split the PDF into page chunks, run Docling on each, merge sections.

        This keeps peak RAM proportional to chunk_size (not total_pages), while
        preserving full Docling ML quality (TableFormer etc.) on every page.

        Requires PyMuPDF (pip install pymupdf) for splitting.
        """
        import tempfile
        import os
        try:
            import fitz  # type: ignore[import]
        except ImportError as exc:
            raise ParseError(
                "PyMuPDF (fitz) is required for chunked parsing. "
                "Run: pip install pymupdf"
            ) from exc

        all_sections: list[Section] = []
        title: str = ""
        n_chunks = (total_pages + chunk_size - 1) // chunk_size

        src_pdf = fitz.open(str(path))
        try:
            for chunk_idx in range(n_chunks):
                start = chunk_idx * chunk_size
                end   = min(start + chunk_size - 1, total_pages - 1)  # fitz is 0-indexed

                # Write chunk to a temp file
                chunk_doc = fitz.open()
                chunk_doc.insert_pdf(src_pdf, from_page=start, to_page=end)

                tmp = tempfile.NamedTemporaryFile(
                    suffix=".pdf", delete=False, prefix=f"docnest_chunk{chunk_idx}_"
                )
                tmp.close()
                try:
                    chunk_doc.save(tmp.name)
                    chunk_doc.close()

                    chunk_raw = self._parse_single(Path(tmp.name), str(path))

                    # Use title from first chunk (usually has the doc title)
                    if not title and chunk_raw.title:
                        title = chunk_raw.title

                    all_sections.extend(chunk_raw.sections)

                finally:
                    os.unlink(tmp.name)

        finally:
            src_pdf.close()

        return RawDocument(
            doc_id=self._make_doc_id(str(path)),
            title=title or _filename_to_title(path.stem),
            source=str(path),
            format="pdf",
            sections=all_sections,
        )

    def _get_converter(self) -> object:
        """Lazy-init the Docling DocumentConverter with configurable options.

        By default OCR is disabled (no ML model download needed for text PDFs).
        Set ocr=True in __init__ to enable scanned PDF support.

        Backend selection:
          - ``"pypdfium2"`` (default): uses PyPdfiumDocumentBackend — constant
            memory footprint (~3.9 GB), no accumulation across pages. Recommended
            for large PDFs and memory-constrained environments.
          - ``"docling"`` (legacy): uses the default Docling C++ dlparse backend.
            Higher layout quality but accumulates memory on large PDFs (OOM risk).
        """
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter  # type: ignore[import]
                from docling.datamodel.base_models import InputFormat  # type: ignore[import]
                from docling.datamodel.pipeline_options import (  # type: ignore[import]
                    PdfPipelineOptions,
                )
                from docling.document_converter import PdfFormatOption  # type: ignore[import]
            except ImportError as exc:
                raise ParseError(
                    "Docling is not installed. Run: pip install docling"
                ) from exc

            pipeline_opts = PdfPipelineOptions()
            pipeline_opts.do_ocr = self._ocr
            pipeline_opts.do_table_structure = self._table_structure

            # Select a non-default OCR engine when requested. Both EasyOCR and
            # Tesseract support scripts (incl. Devanagari/Hindi) the default
            # engine can't. EasyOCR is pure-Python (no system binary); Tesseract
            # uses its CLI binary.
            if self._ocr and self._ocr_engine == "easyocr":
                try:
                    from docling.datamodel.pipeline_options import (  # type: ignore[import]
                        EasyOcrOptions,
                    )
                    ocr_opts = EasyOcrOptions(
                        force_full_page_ocr=self._force_full_page_ocr,
                    )
                    if self._ocr_lang:
                        ocr_opts.lang = self._ocr_lang
                    pipeline_opts.ocr_options = ocr_opts
                except ImportError:
                    import warnings
                    warnings.warn(
                        "EasyOCR options unavailable in this Docling build; "
                        "falling back to the default OCR engine.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
            elif self._ocr and self._ocr_engine == "tesseract":
                try:
                    from docling.datamodel.pipeline_options import (  # type: ignore[import]
                        TesseractCliOcrOptions,
                    )
                    ocr_opts = TesseractCliOcrOptions(
                        force_full_page_ocr=self._force_full_page_ocr,
                    )
                    if self._ocr_lang:
                        ocr_opts.lang = self._ocr_lang
                    if self._tesseract_cmd:
                        ocr_opts.tesseract_cmd = self._tesseract_cmd
                    if self._tessdata_path:
                        ocr_opts.path = self._tessdata_path
                    pipeline_opts.ocr_options = ocr_opts
                except ImportError:
                    import warnings
                    warnings.warn(
                        "Tesseract OCR options unavailable in this Docling build; "
                        "falling back to the default OCR engine.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
            # Disable image rendering by default — each page image can consume
            # 50-200 MB of RAM, triggering std::bad_alloc on large PDFs.
            pipeline_opts.generate_page_images = self._generate_images
            pipeline_opts.generate_picture_images = self._generate_images
            if self._generate_images:
                pipeline_opts.images_scale = self._images_scale

            # Resolve backend class
            backend_cls = None
            if self._pdf_backend == "pypdfium2":
                try:
                    from docling.backend.pypdfium2_backend import (  # type: ignore[import]
                        PyPdfiumDocumentBackend,
                    )
                    backend_cls = PyPdfiumDocumentBackend
                except ImportError:
                    import warnings
                    warnings.warn(
                        "pypdfium2 backend not available (pip install pypdfium2). "
                        "Falling back to default Docling backend.",
                        RuntimeWarning,
                        stacklevel=3,
                    )

            fmt_option = (
                PdfFormatOption(pipeline_options=pipeline_opts, backend=backend_cls)
                if backend_cls is not None
                else PdfFormatOption(pipeline_options=pipeline_opts)
            )

            self._converter = DocumentConverter(
                format_options={InputFormat.PDF: fmt_option}
            )
        return self._converter

    def _extract_title(self, doc: object, path: Path) -> str:
        """Return document title from Docling metadata, or derive from filename."""
        for item, _ in doc.iterate_items():  # type: ignore[attr-defined]
            if str(item.label).lower() == "title":
                text = getattr(item, "text", "").strip()
                if text:
                    return text
        return _filename_to_title(path.stem)

    def _build_sections(self, doc: object, docling_doc: object = None) -> list[Section]:
        """Walk Docling items and group content into Section objects.

        Rules:
        - section_header / title  → starts a new Section
        - text / list_item / etc. → appended to the current Section's text
        - table                   → TableData added to current Section
        - picture                 → ImageRef added to current Section
        - page_header/footer      → ignored
        - Content before first heading → implicit 'Introduction' Section (level 1)
        """
        sections: list[Section] = []
        current: Optional[Section] = None
        table_counter = 0
        image_counter = 0

        for item, depth in doc.iterate_items():  # type: ignore[attr-defined]
            label = str(item.label).lower()

            if label in _IGNORE_LABELS:
                continue

            if label in _HEADING_LABELS:
                if current is not None:
                    current.text = current.text.strip()
                    sections.append(current)
                heading_text = getattr(item, "text", "").strip() or "Section"
                # Docling's depth = nesting level in doc tree; clamp to 1-6
                h_level = max(1, min(6, depth if depth and depth > 0 else 1))
                current = Section(
                    id="",          # Normaliser assigns §ids
                    title=heading_text,
                    level=h_level,
                    text="",
                )

            elif label in _TEXT_LABELS:
                text = getattr(item, "text", "").strip()
                if not text:
                    continue
                if current is None:
                    current = Section(id="", title="Introduction", level=1, text="")
                current.text += text + "\n\n"

            elif label == _TABLE_LABEL:
                table_counter += 1
                table_data = self._extract_table(item, table_counter, docling_doc)
                if table_data:
                    if current is None:
                        current = Section(id="", title="Tables", level=1, text="")
                    current.tables.append(table_data)

            elif label == _PICTURE_LABEL:
                image_counter += 1
                image_ref = self._extract_image_ref(item, image_counter)
                if image_ref:
                    if current is None:
                        current = Section(id="", title="Figures", level=1, text="")
                    current.images.append(image_ref)

        if current is not None:
            current.text = current.text.strip()
            sections.append(current)

        return sections

    def _sections_from_texts(self, doc: object) -> list[Section]:
        """Build sections from Docling's flat ``doc.texts`` list.

        Fallback for pages where the body tree holds no text items (e.g. a
        full-page image whose OCR'd text Docling keeps in ``doc.texts`` only).
        Groups by heading just like :meth:`_build_sections`.
        """
        sections: list[Section] = []
        current: Optional[Section] = None

        for item in getattr(doc, "texts", []) or []:
            label = str(getattr(item, "label", "")).lower()
            if label in _IGNORE_LABELS:
                continue
            text = (getattr(item, "text", "") or "").strip()

            if label in _HEADING_LABELS:
                if current is not None:
                    current.text = current.text.strip()
                    sections.append(current)
                current = Section(id="", title=text or "Section", level=1, text="")
            elif text:
                if current is None:
                    current = Section(id="", title="Introduction", level=1, text="")
                current.text += text + "\n\n"

        if current is not None:
            current.text = current.text.strip()
            sections.append(current)

        return sections

    def _extract_table(
        self, item: object, counter: int, docling_doc: object = None
    ) -> Optional[TableData]:
        """Convert a Docling TableItem to a TableData model.

        Tries DataFrame export first (cleanest), then falls back to raw cell
        iteration so we don't depend on pandas being installed.
        """
        table_id = f"tbl_{counter:03d}"

        # Attempt 1: pandas DataFrame export (pass doc to avoid deprecation warning)
        try:
            if docling_doc is not None:
                df = item.export_to_dataframe(doc=docling_doc)  # type: ignore[attr-defined]
            else:
                df = item.export_to_dataframe()  # type: ignore[attr-defined]
            headers = [str(c) for c in df.columns.tolist()]
            rows = [[str(v) for v in row] for row in df.values.tolist()]
            if headers:
                return TableData(table_id=table_id, headers=headers, rows=rows)
        except Exception:
            pass

        # Attempt 2: raw cell iteration via item.data.table_cells
        try:
            cells = item.data.table_cells  # type: ignore[attr-defined]
            if not cells:
                return None
            num_cols = max(c.start_col_offset_idx + 1 for c in cells)
            num_rows = max(c.start_row_offset_idx + 1 for c in cells)
            grid: list[list[str]] = [[""] * num_cols for _ in range(num_rows)]
            for cell in cells:
                grid[cell.start_row_offset_idx][cell.start_col_offset_idx] = (
                    cell.text.strip()
                )
            headers = grid[0]
            rows = grid[1:]
            return TableData(table_id=table_id, headers=headers, rows=rows)
        except Exception:
            return None

    def _extract_image_ref(self, item: object, counter: int) -> Optional[ImageRef]:
        """Build an ImageRef from a Docling PictureItem."""
        try:
            caption = ""
            captions = getattr(item, "captions", [])  # type: ignore[attr-defined]
            if captions:
                caption = " ".join(
                    getattr(c, "text", "") for c in captions
                ).strip()
            return ImageRef(
                image_id=f"img_{counter:03d}",
                alt=caption or None,
                asset_path=f"assets/img_{counter:03d}.png",
            )
        except Exception:
            return None


# ------------------------------------------------------------------ #
#  Utility                                                             #
# ------------------------------------------------------------------ #

def _filename_to_title(stem: str) -> str:
    """Convert a filename stem to a readable title.

    Handles CamelCase, hyphens, underscores, and digit boundaries.

    Examples:
        annual_report_2024  → Annual Report 2024
        Q3-earnings-summary → Q3 Earnings Summary
        GunjanTailor        → Gunjan Tailor
        SampleReport2024    → Sample Report 2024
    """
    import re as _re
    # Split CamelCase (lowercase→uppercase transition)
    s = _re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    # Split at letter-digit boundaries
    s = _re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = _re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    # Replace hyphens/underscores with spaces
    s = _re.sub(r"[-_]+", " ", s)
    # Collapse whitespace and title-case
    return " ".join(s.split()).title()
