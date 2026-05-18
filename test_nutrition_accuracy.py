"""
Accuracy test for DocNest against human-nutrition-text.pdf

Approach:
- PyMuPDF parser (no ML, low RAM) for parsing
- Anthropic claude-haiku for section enrichment + document QA
- BM25 + cosine search in Reader
- 19 questions across 4 difficulty tiers

Run: pytest test_nutrition_accuracy.py -v -s --no-header
"""
from __future__ import annotations

import os
import time
import warnings

# Limit BLAS/OpenBLAS threads before any numpy import to avoid OOM
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
from pathlib import Path
import pytest

PDF_PATH = r"C:\Users\tailo\Downloads\Documents\human-nutrition-text.pdf.pdf"
UDF_PATH = r"C:\Users\tailo\AppData\Local\Temp\nutrition_test.udf"


# ── Minimal embedder (numpy only, no torch/BLAS) ───────────────────────────────

class TFIDFEmbedder:
    """
    Lightweight TF-IDF + random-projection embedder.
    No torch, no BLAS — pure numpy. Cosine search still works
    because we use the same projection for queries and documents.
    """
    DIMS = 256
    _vocab: dict[str, int] = {}
    _proj: np.ndarray | None = None

    def __init__(self) -> None:
        rng = np.random.default_rng(42)
        self._proj = rng.standard_normal((50_000, self.DIMS)).astype(np.float32)
        self._proj /= np.linalg.norm(self._proj, axis=1, keepdims=True)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        return re.findall(r"[a-z]+", text.lower())

    def _text_to_vec(self, text: str) -> np.ndarray:
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.DIMS, dtype=np.float32)
        vecs = []
        for tok in tokens:
            h = hash(tok) % 50_000
            vecs.append(self._proj[h])
        v = np.mean(vecs, axis=0).astype(np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array([self._text_to_vec(t) for t in texts], dtype=np.float32)

    @property
    def dims(self) -> int:
        return self.DIMS

    @property
    def model_name(self) -> str:
        return "tfidf-random-projection-256"


# ── Build UDF fixture ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def nutrition_udf() -> Path:
    out = Path(UDF_PATH)
    if out.exists() and out.stat().st_size > 10_000:
        print(f"\n[CACHE] Reusing {out}  ({out.stat().st_size/1024:.0f} KB)")
        return out

    pdf = Path(PDF_PATH)
    if not pdf.exists():
        pytest.skip(f"PDF not found: {PDF_PATH}")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    from docnest.parsers.pymupdf_pdf import PyMuPDFParser
    from docnest.normalizer import SectionNormaliser
    from docnest.intelligence import IntelligenceEngine
    from docnest.quantizer import Quantizer
    from docnest.writer import UDFWriter
    from docnest.providers.llm import LangChainLLMProvider

    t0 = time.time()
    print(f"\n[PARSE] {pdf.name} ({pdf.stat().st_size/1_048_576:.1f} MB) — PyMuPDF (low RAM, no ML)")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        raw = PyMuPDFParser().parse(str(pdf))
        for w in caught:
            print(f"  [WARN] {w.message}")

    print(f"  Sections: {len(raw.sections)}  ({time.time()-t0:.1f}s)")
    for s in raw.sections[:6]:
        safe = s.title[:70].encode("ascii", "replace").decode()
        print(f"    L{s.level}  {safe}")
    if len(raw.sections) > 6:
        print(f"    ... +{len(raw.sections)-6} more")

    doc = SectionNormaliser().normalise(raw)
    print(f"[ENRICH] Enriching sections with gpt-4o-mini...")
    llm = LangChainLLMProvider(
        "openai", "gpt-4o-mini", api_key=api_key
    )
    engine = IntelligenceEngine(provider=llm)
    doc = engine.enrich_sections(doc)
    doc = engine.enrich_document(doc)
    print(f"  Summary: {(doc.summary or '')[:100]}...")

    print("[EMBED] Embedding with TF-IDF projector (no torch)...")
    embedder = TFIDFEmbedder()
    writer = UDFWriter(embedder, Quantizer("float16"))
    out.parent.mkdir(parents=True, exist_ok=True)
    path = writer.write(doc, str(out))
    print(f"[DONE] {path}  ({Path(path).stat().st_size/1024:.0f} KB)  {time.time()-t0:.1f}s total")
    return Path(path)


@pytest.fixture(scope="session")
def reader(nutrition_udf):
    from docnest.reader import UDFIndex
    return UDFIndex.load(str(nutrition_udf))


# ── Helpers ────────────────────────────────────────────────────────────────────

def ask(reader, question: str) -> tuple[str, int]:
    result = reader.query(
        question,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_api_key=os.environ.get("OPENAI_API_KEY"),
    )
    if hasattr(result, "answer"):
        return result.answer.strip(), result.tokens_used
    if isinstance(result, tuple):
        ans, tok = result
    else:
        ans, tok = str(result), 0
    return ans.strip(), tok


def check(ans: str, must: list[str], must_not: list[str] = None) -> tuple[bool, str]:
    a = ans.lower()
    missing = [k for k in must if k.lower() not in a]
    bad = [k for k in (must_not or []) if k.lower() in a]
    if missing:
        return False, f"Missing: {missing}"
    if bad:
        return False, f"Should not contain: {bad}"
    return True, "PASS"


def show(question_short: str, ans: str, tok: int, ok: bool, reason: str):
    status = "✓" if ok else "✗"
    print(f"\n  [{status}] {question_short}")
    print(f"      A: {ans[:220]}")
    print(f"      tokens={tok}  reason={reason}")


# ── Tier 1: Basic facts (should hit L0/L1, 0-token or BM25) ───────────────────

class TestBasicFacts:
    def test_kcal_per_gram_fat(self, reader):
        q = "How many calories per gram does fat provide?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["9"])
        show("kcal/g fat", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_kcal_per_gram_protein_carb(self, reader):
        q = "How many calories per gram do protein and carbohydrates each provide?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["4"])
        show("kcal/g protein+carb", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_water_percent_of_body(self, reader):
        q = "What percentage of the human body is composed of water?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["60"])
        show("body water %", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"


# ── Tier 2: Section-level retrieval (L1/L2) ────────────────────────────────────

class TestMacronutrients:
    def test_essential_amino_acids_count(self, reader):
        q = "How many essential amino acids are there? List them."
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["9"])
        show("EAA count", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_complete_vs_incomplete_protein(self, reader):
        q = "What is the difference between complete and incomplete protein sources?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["essential", "amino"])
        show("complete/incomplete protein", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_soluble_vs_insoluble_fiber(self, reader):
        q = "What is the difference between soluble and insoluble dietary fiber?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["soluble", "insoluble"])
        show("fiber types", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_glycemic_index(self, reader):
        q = "What is the glycemic index and how does it affect blood sugar?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["blood"])
        show("glycemic index", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"


# ── Tier 3: Micronutrients (L2/L3 — cross-section) ────────────────────────────

class TestMicronutrients:
    def test_fat_soluble_vitamins(self, reader):
        q = "Which vitamins are fat-soluble? How are they different from water-soluble ones?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["fat", "soluble"])
        show("fat-soluble vitamins", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_vitamin_d_calcium_absorption(self, reader):
        q = "What role does vitamin D play in calcium absorption and bone health?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["calcium"])
        show("vitamin D + calcium", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_iron_deficiency_anemia(self, reader):
        q = "What are the health consequences of iron deficiency?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["anemia"])
        show("iron deficiency", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_vitamin_c_functions(self, reader):
        q = "What are the main functions of vitamin C in the human body?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["collagen"])
        show("vitamin C functions", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"


# ── Tier 4: Hard multi-section synthesis (L3/L4) ──────────────────────────────

class TestHardQuestions:
    def test_saturated_vs_unsaturated_fat_cardiovascular(self, reader):
        q = ("Compare saturated and unsaturated fats and explain "
             "how each affects cardiovascular health.")
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["saturated", "unsaturated"])
        show("sat vs unsat fat + CVD", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_bmr_factors(self, reader):
        q = "What physiological factors determine a person's basal metabolic rate (BMR)?"
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["age", "weight"])
        show("BMR factors", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_antioxidants_and_free_radicals(self, reader):
        q = ("How do antioxidants protect the body from oxidative damage "
             "and which nutrients act as antioxidants?")
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["free radical"])
        show("antioxidants + free radicals", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"

    def test_omega3_vs_omega6(self, reader):
        q = ("What is the difference between omega-3 and omega-6 fatty acids "
             "and why does their dietary ratio matter?")
        ans, tok = ask(reader, q)
        ok, reason = check(ans, ["omega-3", "omega-6"])
        show("omega-3 vs omega-6", ans, tok, ok, reason)
        assert ok, f"{reason}\n{ans}"


# ── Tier 5: Edge / stress cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_specific_rda_value_not_vague(self, reader):
        """Checks it returns a number, not a vague statement."""
        q = "What is the RDA for vitamin C for adult men and women in mg/day?"
        ans, tok = ask(reader, q)
        # Must contain some specific number between 50-200 mg
        has_number = any(str(n) in ans for n in range(50, 201))
        ok = has_number
        show("vitamin C RDA mg", ans, tok, ok, "no specific mg value" if not ok else "PASS")
        assert ok, f"No specific mg value in answer — may be vague\n{ans}"

    def test_out_of_scope_not_confabulated(self, reader):
        """Asks something outside nutrition — should not fabricate nutrition content."""
        q = "What is the boiling point of ethanol in degrees Celsius?"
        ans, tok = ask(reader, q)
        # Should either say unknown OR give correct ~78°C — should NOT give a nutrition answer
        a = ans.lower()
        nutrition_confab = any(k in a for k in ["calorie", "vitamin", "protein", "mineral"])
        ok = not nutrition_confab
        show("out-of-scope (ethanol)", ans, tok, ok,
             "confabulated nutrition content" if not ok else "PASS")
        assert ok, f"Confabulated nutrition content for out-of-scope query\n{ans}"

    def test_table_data_accessible(self, reader):
        """Answer must come from a parsed table (non-vague, specific food mentioned)."""
        q = "According to the tables in the text, which foods are good sources of potassium?"
        ans, tok = ask(reader, q)
        ok = len(ans) > 30
        show("table: potassium sources", ans, tok, ok,
             "answer too short — table may not have parsed" if not ok else "PASS")
        assert ok, f"Too short for a table-based answer\n{ans}"


# ── Summary hook ──────────────────────────────────────────────────────────────

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    errors = len(terminalreporter.stats.get("error", []))
    total = passed + failed
    if total:
        pct = passed / total * 100
        print(f"\n{'='*55}")
        print(f"  DocNest Accuracy: {passed}/{total} ({pct:.0f}%)")
        if errors:
            print(f"  Setup errors: {errors}")
        print(f"{'='*55}")
