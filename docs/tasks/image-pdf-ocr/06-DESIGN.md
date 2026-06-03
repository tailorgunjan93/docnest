# Task 3 — Image/Scanned-PDF OCR · Phase 2: Design

## 1. DSA / performance
- **Text-layer gate (per page):** `len(page.get_text("text").strip()) >= text_layer_min_chars`
  → O(page text), negligible; **eliminates OCR on text pages** (the big win: text-layer sample 27s→~0).
- **Downscale:** cap the rendered image's long edge to `ocr_max_px` → bounds OCR input pixels,
  cutting EasyOCR time on huge images with minor accuracy loss.
- Per-page OCR is O(pixels) (engine-inherent); we minimise *when* (skip text pages) and
  *how big* (downscale). One-time model load (~13s EasyOCR) amortised.

## 2. Architecture / SOLID
- **SRP:** parser owns extraction; OCR delegated entirely to an **`IOCRProvider`** (no
  easyocr/tesseract imports in the parser — wrapper rule satisfied).
- **OCP:** OCR is **additive** behind `ocr=False` default; OCR-off path byte-for-byte unchanged.
- **DIP:** parser depends on the `IOCRProvider` abstraction; engine is injectable.
- **Pattern:** Strategy (OCR engine) + the existing Template-ish parse flow. Docling OCR
  stays as the heavy alternative (no change).

## 3. Signatures (locked)

### `docnest/parsers/pymupdf_pdf.py`
```python
from docnest.providers.ocr import IOCRProvider  # type-only / lazy

class PyMuPDFParser(IParser):
    def __init__(
        self,
        heading_threshold: float = 1.15,
        ocr: bool = False,
        ocr_provider: "IOCRProvider | None" = None,
        ocr_languages: list[str] | None = None,   # default ["en"]; e.g. ["hi","en"]
        ocr_dpi: int = 200,
        ocr_max_px: int = 2000,                    # downscale long edge cap
        text_layer_min_chars: int = 20,            # skip-OCR threshold per page
    ) -> None: ...
```

**OCR provider resolution (graceful, EasyOCR default):**
```python
if ocr and ocr_provider is None:
    from docnest.providers.ocr import EasyOCRProvider, NullOCRProvider
    cand = EasyOCRProvider(languages=ocr_languages or ["en"])
    self._ocr_provider = cand if cand.available else NullOCRProvider()  # warn on fallback
else:
    self._ocr_provider = ocr_provider  # may be None when ocr=False
self._ocr = ocr
```

**Per-page logic (inside the existing `_extract_blocks` page loop):**
```python
for page in doc:
    spans = _collect_spans(page)            # existing behaviour
    if spans:
        blocks.extend(spans)
    elif self._ocr and self._ocr_provider is not None:
        txt = self._ocr_page(page)          # render + downscale + provider.extract_text
        if txt.strip():
            blocks.append({"text": txt, "size": median_size, "bold": False})
```

```python
def _ocr_page(self, page) -> str:
    pix = page.get_pixmap(dpi=self._ocr_dpi)
    png = pix.tobytes("png")
    if max(pix.width, pix.height) > self._ocr_max_px:
        png = _downscale_png(png, self._ocr_max_px)   # PIL thumbnail → re-encode
    return self._ocr_provider.extract_text(png)       # IOCRProvider; never raises in our use
```

> OCR text is appended as body text (uniform size → lands under the page/Introduction
> section). Good enough for retrieval; no font/heading info exists in a scanned image.

### `docnest/providers/ocr.py`
No interface change. `EasyOCRProvider` / `NullOCRProvider` reused. (If `extract_text` can
raise `ImportError`, the parser guards with `.available`; OCR errors already return `""`.)

## 4. Wrapper / dependency
- No new dependency in core; EasyOCR is an **optional extra** (`docnest-ai[ocr-easyocr]`),
  accessed only via `IOCRProvider`. Missing engine → `NullOCRProvider` → empty text (graceful).

## 5. Backward compatibility
- `ocr=False` default → identical output + identical deps for existing users.
- Additive ctor args; no `.udf`/`UDF_VERSION`/public-API change.

## 6. Tests (Phase 3 preview)
- **Offline unit (mock `IOCRProvider`):** text-layer page → provider **not** called;
  image-only page → provider called once; `_downscale_png` caps dimensions; `ocr_languages`
  passed to default EasyOCR; engine-missing → `NullOCRProvider` fallback (no crash).
- **Gated real e2e (local PDFs, skip in CI):** Hindi image sample → Devanagari extracted;
  text-layer sample → text layer used, OCR **not** invoked.

## 7. ADR
Recorded as **[ADR-0002](../../adr/0002-lightweight-pymupdf-ocr.md)**.
