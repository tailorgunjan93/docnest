"""Observer's Tax eval — how many tokens does the LLM "pay" to answer a query?

The "Observer's Tax" is the token cost the system imposes on the LLM to *observe* (read)
context per query. DocNest's premise: Layer 0 (precomputed) and Layer 1 (BM25+cosine)
answer for **0 tokens**; only Layers 2–4 pay. This harness runs a question set through the
**production `.udf` reader** (`UDFIndex.query`) — the layered path the accuracy eval never
measured — and reports:

  • Layer distribution (0/1/2/3/4)
  • Zero-token answer rate (Layers 0+1)  ← Charter goal: 70% of queries at 0 tokens
  • Average tokens/query (the tax) vs a naive-RAG baseline (always reads the whole doc)
  • Accuracy by layer (is the free path also correct?)

Local, no quota: defaults to Ollama llama3.2:1b for Layers 2–4.

Run:  python eval/observers_tax_eval.py --udf test_docs/sample_report.udf
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docnest.reader import UDFIndex  # noqa: E402

# (question, expected key number/phrase). Ground truth from sample_report.md.
SAMPLE_REPORT_QUESTIONS = [
    ("What was the platform uptime percentage?", "99.97"),
    ("What did monthly cloud spend drop to after rightsizing?", "14350"),
    ("How many total engineers are there?", "24"),
    ("By what percentage were infrastructure costs reduced?", "22"),
    ("What was the average response time after migration?", "142"),
    ("How many microservices were migrated to Azure?", "14"),
    ("What was the mean time to deploy after improvements?", "8"),
    ("What is the monthly cost savings?", "4050"),
    ("What percentage of critical user journeys do the tests cover?", "87"),
    ("How many new hires were there?", "3"),
]


def _norm_num(s: str) -> str:
    return re.sub(r"[,\s]", "", s)


def _correct(answer: str, expected: str) -> bool:
    a = _norm_num(answer.lower())
    return _norm_num(expected.lower()) in a


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def main() -> None:
    ap = argparse.ArgumentParser(description="Observer's Tax eval")
    ap.add_argument("--udf", default="test_docs/sample_report.udf")
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default="llama3.2:1b")
    args = ap.parse_args()

    idx = UDFIndex.load(args.udf)

    # Naive-RAG baseline: every query reads the entire document text.
    section_ids = getattr(idx, "_section_ids", None) or [
        e["id"] for e in idx._catalogue.get("section_index", [])
    ]
    full_chars = sum(len(idx._get_section_text(sid) or "") for sid in section_ids)
    naive_tokens_per_q = _est_tokens("x" * full_chars)

    rows = []
    for q, expected in SAMPLE_REPORT_QUESTIONS:
        t0 = time.perf_counter()
        try:
            res = idx.query(q, llm_provider=args.provider, llm_model=args.model)
            ans, layer, toks = res.answer, res.layer_used, res.tokens_used
        except Exception as e:
            ans, layer, toks = f"[error: {e}]", -1, 0
        rows.append({
            "q": q, "expected": expected, "answer": ans, "layer": layer,
            "tokens": toks, "ok": _correct(ans, expected), "ms": (time.perf_counter() - t0) * 1000,
        })
        print(f"  L{layer} {toks:>5} tok  {'OK ' if rows[-1]['ok'] else '.. '} {q[:54]}")

    n = len(rows)
    by_layer = {}
    for r in rows:
        by_layer.setdefault(r["layer"], []).append(r)
    zero_tok = sum(1 for r in rows if r["tokens"] == 0)
    dn_tax = sum(r["tokens"] for r in rows)
    naive_tax = naive_tokens_per_q * n
    acc = sum(1 for r in rows if r["ok"]) / n

    print("\n" + "=" * 64)
    print("OBSERVER'S TAX REPORT —", Path(args.udf).name, f"({args.provider}/{args.model})")
    print("=" * 64)
    print(f"Questions                : {n}")
    print(f"Zero-token answers (L0+1): {zero_tok}/{n}  ({100*zero_tok/n:.0f}%)   [Charter goal: 70%]")
    print(f"Accuracy                 : {100*acc:.0f}%")
    print(f"\nLayer distribution:")
    for L in sorted(by_layer):
        g = by_layer[L]
        okc = sum(1 for r in g if r["ok"])
        print(f"  Layer {L}: {len(g):>2} q  | avg {sum(r['tokens'] for r in g)//max(len(g),1):>5} tok"
              f"  | acc {100*okc//len(g):>3}%")
    print(f"\nObserver's Tax (total tokens to answer all {n} queries):")
    print(f"  DocNest (layered) : {dn_tax:>8,} tokens   ({dn_tax//n:,}/query avg)")
    print(f"  Naive RAG (full)  : {naive_tax:>8,} tokens   ({naive_tokens_per_q:,}/query)")
    if naive_tax:
        print(f"  Tax reduction     : {100*(naive_tax-dn_tax)/naive_tax:.1f}%")


if __name__ == "__main__":
    main()
