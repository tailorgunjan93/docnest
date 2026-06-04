# Retrospective — RAG Eval + Traversal Audit (2026-06-03)

> **Thesis (the one thing to remember):** In DocNest, *the library is the brain.*
> The LLM is a last-mile narrator, not the reasoning engine. Today we have it
> backwards — the LLM does the thinking on **both** ends (enrichment at ingest,
> answering at query) and DocNest has almost **no deterministic reasoning of its
> own**. This document proves that with evidence and lays out the algorithmic
> work to fix it.

---

## Part 1 — What the eval showed (numbers)

Model: `cerebras/gpt-oss-120b` (a *reasoning* model). Judge: local numeric+keyword
judge with a Gemini fallback. 10 docs, 88 questions, 5 formats.

| Run | Cap | Overall | Pass | Empty answers | Notes |
|-----|-----|---------|------|---------------|-------|
| `baseline_gptoss` | 1024 | **8.1** | 84% | 4 | reference |
| `after_tables`    | 1024 | **7.9** | 85% | 7 | table fix (not in eval path) → run-to-run noise |
| `after_tables_2048` | 2048 | _TBD_ | _TBD_ | _TBD_ | cap raised — finalize on completion |

**Two hard data points that frame the whole retrospective:**

1. **Acme Q1** ("sum the Q1 column = 12550"): answer text was *correct* — `12,550` —
   yet scored **0/10 (1024)**, **5/10 (2048)**, **10/10 (baseline)**. Same correct
   answer, three different scores. → A **judge/normalization artifact** on number
   formatting (`12 550` / `12,550` vs `12550`), not a retrieval failure.
2. **Acme Q8** ("sum ARR of Enterprise-tier rows = 7,600"): answer **empty → 0/10
   at 1024 *and* 2048.** Not a token-budget problem. The model simply won't do the
   filter-then-sum, and **DocNest has no deterministic fallback to do it instead.**

Most zero-scores (7 of 9 in `after_tables`) were **empty completions** — the
reasoning model burned its budget on hidden chain-of-thought and emitted nothing.
The retrieved sections were *present and correct* (e.g. BIS Q5 quoted §46 verbatim →
9/10). So retrieval is doing its job; the failures cluster on the **LLM answer step**
and the **judge**, not the layers.

---

## Part 2 — Failure taxonomy (root cause, not symptom)

| Bucket | Example | Root cause | Whose job is it? |
|--------|---------|-----------|------------------|
| **Empty/truncated answer** | BIS Q1–Q3, Acme Q8 | LLM emits nothing under reasoning-token pressure; no fallback | **DocNest** must have an extractive fallback |
| **Arithmetic over rows** | Acme Q8 (ΣARR), Q1 (Σcolumn), Q2 (Σrow) | LLM asked to filter+sum a table; unreliable | **DocNest** must do relational aggregation |
| **Number formatting** | Acme Q1 `12 550` vs `12550` | No canonical numeric normalization | **DocNest** must normalize numbers/units |
| **Sub-topic mis-targeting** | BIS Q4 (asked "AI herding", got CRE §43) | Section-level retrieval too coarse for multi-aspect Qs | **DocNest** retrieval (sentence-level / aspect) |
| **Judge artifact** | Acme Q1 correct→0/10 | Grader's number parser | Eval harness (not the library) |

The first three buckets are the majority of lost points, and **all three are
deterministic problems that the LLM is being (mis)trusted to solve.**

---

## Part 3 — Traversal audit: `test_docs/sample_report.udf`

I opened the `.udf` and walked it as the production reader would.

**What's healthy (✅ traversable):**
- **Section tree** — `parent_id` / `children` / `level` fully populated. Walking
  `§1 → §1.2 → §1.2.2` works. Hierarchy is intact.
- **Content layer** — every section's `text` is preserved faithfully; tables/images
  arrays present (empty here because the source is prose Markdown).
- **Embeddings** — 384-dim float16 per section (`all-MiniLM-L6-v2`). Semantic search
  has vectors to work with.

**What's broken (❌ the gap):** the **intelligence layer is entirely empty.**

| Field (catalogue) | Value in this `.udf` | Should contain |
|---|---|---|
| `doc.summary` | `""` | 3-sentence doc summary |
| `doc.insights` | `[]` | top findings |
| `doc.key_numbers` | `[]` | **99.97% uptime, $14,350 spend, 22% cost cut, 24 engineers, 142ms…** |
| `section.keywords` (all) | `[]` | 5–8 index terms per section |
| `section.summary` (all) | `""` | one-line gist per section |

This document is *dense* with hard facts, and `key_numbers` captured **zero** of
them. So the headline promise — **"Layer 0 answers many queries with 0 LLM tokens"** —
has nothing to answer *from*. Every query is forced down to the LLM layers.

**Why is it empty?** See Part 4 — because populating it is delegated to an LLM that
wasn't run at ingest.

---

## Part 4 — The core defect: LLM on both ends, no deterministic core

`docnest/intelligence.py` is explicit ([lines 1–9](../../docnest/intelligence.py)):
the intelligence layer is produced by **LLM calls at ingest**.

- `key_numbers` ← `_call_doc_intelligence()` (LLM)
- `keywords`    ← `_extract_keywords()` (LLM, with a weak word-split fallback)
- section `summary` ← `_summarise_section()` (LLM)
- doc `summary` / `insights` ← LLM

Combine that with the query path (Layers 2–4 all call an LLM to compose the answer),
and the picture is:

```
            INGEST                         QUERY
   source ──► parse ──► [LLM enrich] ──► .udf ──► retrieve ──► [LLM answer] ──► user
                          ▲                                       ▲
                          └─────────  the "brain" is here  ───────┘
                                   (outside DocNest, twice)
```

**Consequences observed:**
- No LLM at ingest → empty intelligence layer (this `.udf`).
- LLM fails/truncates at query → empty answer, no fallback (BIS, Acme Q8).
- LLM does arithmetic → wrong/again-empty (Acme Q8).
- LLM formats numbers freely → judge/consumer mismatch (Acme Q1).

**The fix is architectural, not a prompt tweak:** move the deterministic work
*into* DocNest. The LLM should only be invoked for genuine free-text synthesis,
and even then over context DocNest has already reasoned about.

---

## Part 5 — Optimization research (algorithms to build into DocNest)

Each is deterministic, local-first, offline, and behind a wrapper (per protocol).
Complexity noted; all are O(n) or near it over section text.

### 5.1 Deterministic key-number extraction  ⟶ replaces LLM `key_numbers`
**Why:** numbers are the highest-value, most-asked facts and the most deterministic
to extract. **Algorithm:** finite-state / regex scan for numeric patterns —
currency (`$18,400`), percent (`99.97%`), counts (`24 engineers`), durations
(`8 minutes`), ratios (`5.8x`), dates — then **label association** by nearest
preceding noun-phrase / bullet label / table header (proximity + simple dependency
heuristic). Normalize each to `{label, value (canonical float), unit, raw, section}`.
**Libraries to wrap:** `quantulum3` (quantities+units) and/or a hand-rolled regex
set; spaCy/Stanford-style `MONEY/PERCENT/DATE/CARDINAL` rule tags as a cross-check.
**Complexity:** O(n) per section. **Math:** regular-language recognition; label
binding as nearest-labeled-token (1-D proximity argmin).

> **Proof of concept (validated 2026-06-03).** A ~90-line prototype
> (`eval/debug_keynum_prototype.py`, not shipped) run against the *same*
> `sample_report` content that `intelligence.py` left empty extracted **37 key
> numbers with zero LLM calls**, including every headline fact — `99.97%` uptime,
> `$18,400→$14,350` cloud spend, `$4,050` savings, `142ms` response time, `87%`
> coverage, `24 engineers`, `22%` cost cut — with correct label binding
> (`Uptime`, `Cost savings`, `Total engineers`, `Monthly cloud spend`).
> It also exposed the precision rules a production version needs: suppress bare
> years (`2025`), ordered-list markers (`1–4`), and alphanumeric identifiers
> (`ISO 27001`, `AZ-204`); require a bound label to emit. **Conclusion: the
> deterministic path is real, not hypothetical.**

### 5.2 Deterministic keyword/keyphrase extraction  ⟶ replaces LLM `keywords`
**Choice: YAKE** (best accuracy among unsupervised, language-agnostic, no external
stoplist, fast). It scores terms from five statistical features — casing, position,
frequency, context dispersion (left/right entropy), and sentence spread — needing no
training and no network. RAKE is a lighter fallback; TextRank loses to both.
**Complexity:** ~O(n) over tokens. **Math:** feature-weighted statistical scoring;
candidate phrases ranked by a multiplicative term score.

### 5.3 Extractive section/doc summaries  ⟶ replaces LLM summaries
**Choice: TextRank** (PageRank over a sentence-similarity graph) or a centroid /
lead-k baseline. Build a graph where nodes = sentences, edge weight =
cosine/overlap similarity; run power iteration to convergence; take top sentences.
Fully deterministic, uses the embeddings we already store. **Complexity:** O(s²) in
sentences per section (small s). **Math:** dominant eigenvector of the row-normalized
similarity matrix (PageRank).

### 5.4 Deterministic table-query / aggregation engine  ⟶ replaces LLM arithmetic
**Why:** directly fixes Acme Q8/Q1/Q2. DocNest already stores tables as structured
rows. Add a small **relational-algebra** layer: σ (filter rows by a column predicate),
π (project a column), and aggregates (Σ, count, max/min, avg). A deterministic
intent→operation mapping ("total … from Enterprise tier" → filter `tier=Enterprise`,
sum `ARR`). **Complexity:** O(rows). **Math:** relational algebra over the table
relation; exact arithmetic, no model.

### 5.5 Query-intent router  ⟶ decides *who* answers
A deterministic classifier (rules + lightweight features) routes each query:
- **Lookup** ("what is X") → extractive value from `key_numbers` / section text (often 0 LLM tokens).
- **Aggregate** ("total/average/how many") → §5.4 table engine.
- **Synthesis** ("what does the report say about…") → LLM, over DocNest-assembled context.

Only the last bucket *needs* the model. This is the lever that takes the LLM off the
critical path for the majority of factual queries.

### 5.6 Extractive answer fallback  ⟶ never return empty
If the LLM returns empty/degenerate output, DocNest returns the top-ranked
sentence(s)/rows from the retrieved section (MMR-selected for relevance−redundancy).
A raw extract always beats `""` (BIS Q1–Q3 would have scored > 0).

### 5.7 Number/unit normalization  ⟶ canonical values everywhere
Store and emit numbers as `{canonical_float, display, unit}`. Fixes the
`12 550`/`12550` class of mismatches at the source — for the judge *and* downstream
consumers.

### What NOT to do (research conclusion)
**Don't swap the retriever.** Hybrid BM25+dense (what we have) is the de-facto robust
choice across in-domain and zero-shot; learned-sparse (SPLADE) needs domain training
and breaks local-first/offline. Effort is better spent on §5.1–5.7 than on retriever
churn. Retrieval's one real gap is **sub-topic granularity** (BIS Q4) — address with
**sentence-level dense vectors + graph expansion**, not a new backbone.

---

## Part 6 — Prioritized roadmap (impact × determinism)

| # | Work item | Fixes | Effort | LLM removed from |
|---|-----------|-------|--------|------------------|
| 1 | **Key-number extraction (§5.1)** | empty `key_numbers`, lookups | M | ingest enrichment |
| 2 | **Table aggregation engine (§5.4)** | Acme Q8/Q1/Q2 | M | query arithmetic |
| 3 | **Extractive answer fallback (§5.6)** | all empty answers | S | query safety net |
| 4 | **Keyword extraction — YAKE (§5.2)** | empty `keywords`, routing/BM25 | S | ingest enrichment |
| 5 | **Query-intent router (§5.5)** | token cost, robustness | M | majority of queries |
| 6 | **Number normalization (§5.7)** | format mismatches | S | — |
| 7 | **Extractive summaries — TextRank (§5.3)** | empty summaries | S | ingest enrichment |
| 8 | **Sentence-level retrieval (§5 note)** | sub-topic misses (BIS Q4) | L | — |

**Sequencing:** 1 → 3 → 2 → 4 → 5 keeps each step shippable and regression-tested.
After 1+4+7, re-write `intelligence.py` so the LLM enrichment becomes *optional
augmentation* on top of a deterministic baseline — DocNest produces a full
intelligence layer **with or without** a model.

Each item follows the protocol: BA/Dev/QA docs + roadmap, ADR for the new wrapper,
test-first, full regression suite, temp branch → green → merge → CHANGELOG.

---

## Part 7 — Per-failure traversal (2048 run, completed set)

⚠️ **Caveat:** the 2048 run terminated early on a **daily token-quota limit**
(the 2× cap exhausted the quota). Only **49 of 88 questions** completed —
the structured formats plus a thin slice of PDFs. The hard PDF failure modes
(empty answers, sub-topic misses) from the full 1024 runs are **not** re-sampled
here and still stand. The headline "8.7/10" is **not comparable** to the 88-Q
baselines — it's a smaller, easier sample. Treat the score as void; the value is
in the per-failure diagnosis below.

I traced every failure (< 7/10) through DocNest: which section was retrieved,
whether the data was present, and where the point was actually lost.

| Q | Retrieved | DocNest answer | Ground truth | Data present? | **Real gap** | Fix |
|---|-----------|----------------|--------------|---------------|--------------|-----|
| Acme Q1 | §1 ✅ | `12,550` ✅ | `…= 12550` | yes | **Judge** — `12,550`≠`12550` (num=0.17) | §5.7 normalize |
| Acme Q2 | §1 ✅ | `DataSync Pro, 23,400` ✅ | `4200+5100+6300+7800=23400` | yes | **Judge** — GT lists addends, answer gives result (num=0.20) | §5.7 + judge |
| Acme Q8 | §5 ✅ | *(empty)* ❌ | `ΣARR Enterprise = 7,600` | **full table in prompt** | **Aggregation** — LLM won't filter+sum; no fallback | **§5.4** |
| Acme Q12 | §8 ✅ | `R&D 210 000, S&M 170000` ✅ | `210,000 / 170,000` | yes | **Judge** — space/comma mismatch (num=0.00) | §5.7 normalize |
| TechV Q5 | §2 ✅ | `$1.55–1.62B` ✅(partial) | `1.55-1.62B, +25-31% YoY` | yes | **Partial** — missing the YoY half | §5.5 multi-part intent |
| TechV Q9 | §10 ✅ | `Germany, S.Korea, Australia` ✅ | same | yes | **Judge** — kw=0.78, no numbers (num=0.00) | judge threshold |
| Nexus Q3 | §1.2.1 ✅ | `POST /documents/{id}/parse` ✅(partial) | `… — Trigger AI parsing, 5/min` | yes | **Partial** — missing `5/min` rate limit | §5.5 multi-part intent |

**What the traversal proves:**
1. **Retrieval is not the problem.** Every one of the 7 retrieved the *correct*
   section, and the answer data was present in the prompt in all 7. Zero
   retrieval-layer failures in this set.
2. **The judge causes most of the lost points.** 4 of 7 (Q1, Q2, Q12, Q9) have
   **correct answers** scored down by number-format mismatch (`12,550`/`210 000`
   vs bare digits) or keyword-overlap thresholds. These are **harness** defects,
   not DocNest defects.
3. **One true library gap: aggregation (Acme Q8).** Full table in the prompt,
   LLM returns empty, DocNest has no deterministic fallback to filter-then-sum.
   This is the single highest-value fix → **§5.4 table-query engine** (+ §5.6
   extractive fallback so it can never be empty).
4. **Two "partial" answers (Q5, Q3)** are multi-part questions where DocNest
   answered one half. A deterministic **multi-part intent** decomposition (§5.5)
   would ensure every asked sub-fact is covered.

**Net:** on the completed set, DocNest's *own* logic is sound — the losses are
**judge normalization (4) + one aggregation gap (1) + two partial-coverage (2)**.
This is strong support for the thesis: fix the deterministic core (aggregation,
normalization, intent) and most of the gap closes **without touching the LLM**.

> **Action items added to roadmap from this pass:** prioritise §5.4 (aggregation)
> and §5.7 (normalization); also fix the **eval judge** to normalize numbers
> (strip `,`/spaces) and to credit result-vs-formula equivalence — so future runs
> measure DocNest, not formatting. And **revert the eval cap to 1024** (2048
> exhausts the daily quota and can't finish 88 Q); pursue empty-answer reduction
> via the extractive fallback (§5.6) inside DocNest instead.

---

## Sources (optimization research)
- [Keyword Extraction — Benchmark of 7 Algorithms (Towards Data Science)](https://towardsdatascience.com/keyword-extraction-a-benchmark-of-7-algorithms-in-python-8a905326d93f/)
- [RAKE vs YAKE (ML Digest)](https://ml-digest.com/rake-and-yake-keyword-extractor/)
- [A Comparative Assessment of Unsupervised Keyword Extraction Tools (ResearchGate)](https://www.researchgate.net/publication/376630050_A_Comparative_Assessment_of_Unsupervised_Keyword_Extraction_Tools)
- [Stanford CoreNLP NER — rule-based NUMBER/MONEY/PERCENT/DATE](https://stanfordnlp.github.io/CoreNLP/ner.html)
- [spaCy linguistic features (NER, dependency parsing)](https://spacy.io/usage/linguistic-features)
- [Two-Step SPLADE (arXiv 2404.13357)](https://arxiv.org/pdf/2404.13357)
- [SPLADE for Sparse Vector Search (Pinecone)](https://www.pinecone.io/learn/splade/)
- [Dense–Sparse Hybrid Retrieval (EmergentMind)](https://www.emergentmind.com/topics/dense-sparse-hybrid-retrieval)
