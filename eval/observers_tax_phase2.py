"""Observer's Tax — Phase 2 (PDFs), with-LLM vs deterministic-only (no-LLM).

Builds a .udf per PDF from the cached parse + deterministic enrichment (key_numbers +
keywords, no LLM), then runs each question in two modes:
  • deterministic-only (allow_llm=False): Layers 0/1 only — 0 tokens, no LLM. Measures how
    far DocNest's own logic carries real PDFs.
  • with-LLM (Ollama): full layered stack.
Reports, per mode: coverage/zero-token rate, accuracy, layer distribution, token tax.

Run:  python eval/observers_tax_phase2.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pickle  # noqa: E402

from docnest.key_numbers import enrich_key_numbers  # noqa: E402
from docnest.keywords import enrich_keywords  # noqa: E402
from docnest.writer import UDFWriter  # noqa: E402
from docnest.embedder import SentenceTransformerEmbedder  # noqa: E402
from docnest.reader import UDFIndex  # noqa: E402
from rag_accuracy_eval import PDF_DOCUMENTS  # noqa: E402

CACHE = Path("eval/cache")
OUT = Path("test_output")
OUT.mkdir(exist_ok=True)
STOP = set("the a an of to from in on at by for and or is are was were be this that what "
           "which how many much does did do with as it its about above below than into".split())


def _nums(t: str) -> set:
    return set(re.findall(r"\d[\d,]*\.?\d*", str(t).replace(",", "")))


def _kw(t: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{3,}", str(t).lower()) if w not in STOP}


def _correct(answer: str, truth: str) -> bool:
    """Use the SAME tuned judge as rag_accuracy_eval (≥7/10 = correct) for a fair number."""
    if not answer.strip():
        return False
    try:
        from rag_accuracy_eval import _local_judge
        score, _ = _local_judge("", answer, truth)
        return score >= 7
    except Exception:
        a_n, t_n = _nums(answer), _nums(truth)
        if t_n and (a_n & t_n):
            return True
        tk = _kw(truth)
        return bool(tk) and len(_kw(answer) & tk) / len(tk) >= 0.35


def _find_pickle(short: str):
    for f in CACHE.glob("*.pkl"):
        if short.replace("_", "") in f.stem.replace("_", "").lower():
            return f
    return None


def _build_udf(short: str) -> str | None:
    pk = _find_pickle(short)
    if not pk:
        return None
    out = OUT / f"{short}_kn.udf"
    doc = pickle.load(open(pk, "rb"))
    enrich_key_numbers(doc)
    enrich_keywords(doc)
    UDFWriter(embedder=SentenceTransformerEmbedder()).write(doc, str(out))
    return str(out)


def main() -> None:
    docs = PDF_DOCUMENTS
    agg = {"det": {"answered": 0, "correct": 0, "tok": 0},
           "llm": {"correct": 0, "tok": 0, "layers": {}}}
    total_q = 0
    for cfg in docs:
        udf = _build_udf(cfg["short"])
        if not udf:
            print(f"  (skip {cfg['short']} — no cached parse)")
            continue
        idx = UDFIndex.load(udf)
        print(f"\n### {cfg['name']}  ({udf})")
        for qa in cfg["questions"]:
            q, truth = qa["q"], qa.get("truth") or qa.get("truth_hint", "")
            total_q += 1
            # deterministic-only
            d = idx.query(q, allow_llm=False)
            d_ans = d.layer_used >= 0
            d_ok = d_ans and _correct(d.answer, truth)
            agg["det"]["answered"] += int(d_ans)
            agg["det"]["correct"] += int(d_ok)
            # with-LLM (Ollama)
            try:
                L = idx.query(q, llm_provider="ollama", llm_model="llama3.2:1b")
                l_ok = _correct(L.answer, truth)
            except Exception:
                L = type("X", (), {"layer_used": -1, "tokens_used": 0})()
                l_ok = False
            agg["llm"]["correct"] += int(l_ok)
            agg["llm"]["tok"] += L.tokens_used
            agg["llm"]["layers"][L.layer_used] = agg["llm"]["layers"].get(L.layer_used, 0) + 1
            print(f"  det:{'L'+str(d.layer_used) if d_ans else '— ':3} {'OK' if d_ok else '..'}"
                  f"   llm:L{L.layer_used} {L.tokens_used:>4}t {'OK' if l_ok else '..'}  {q[:48]}")

    n = total_q or 1
    print("\n" + "=" * 70)
    print(f"OBSERVER'S TAX — PHASE 2 (PDFs)   {total_q} questions")
    print("=" * 70)
    det = agg["det"]
    print(f"DETERMINISTIC-ONLY (no LLM, 0 tokens):")
    print(f"  answered (L0/L1) : {det['answered']}/{n} ({100*det['answered']//n}%)")
    print(f"  correct          : {det['correct']}/{n} ({100*det['correct']//n}%)   "
          f"[of answered: {100*det['correct']//max(det['answered'],1)}%]")
    print(f"  tokens           : 0")
    llm = agg["llm"]
    print(f"\nWITH-LLM (full layered stack, Ollama):")
    print(f"  correct          : {llm['correct']}/{n} ({100*llm['correct']//n}%)")
    print(f"  tokens           : {llm['tok']:,} ({llm['tok']//n}/query)")
    print(f"  layer dist       : {dict(sorted(llm['layers'].items()))}")


if __name__ == "__main__":
    main()
