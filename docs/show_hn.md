# TITLE (keep under 80 chars)
Show HN: DOCNEST – PDF parser that preserves table structure for RAG

# URL
https://github.com/tailorgunjan93/docnest

# BODY (this goes in the comments, not the submission — HN strips body from Show HN)
I built a document normalization engine for RAG pipelines that solves the
table-destruction problem.

Standard PDF → chunk → embed loses all table structure. A row like
"45.2% | Q3 | Europe" arrives at the LLM with no column headers and no context.
DOCNEST reads structure first: every heading becomes a §section, every table
becomes { caption, headers, rows[] } JSON, every section gets a BM25 keyword
index and a quantized embedding.

Queries resolve through 5 layers — BM25+cosine at layer 1 answers ~70% of
questions with zero LLM tokens. LLM only fires when the question genuinely
needs it.

Also handles large PDFs (600+ pages) by auto-chunking through PyMuPDF into
N-page pieces, running Docling at full ML quality on each, then merging.
Peak RAM stays bounded regardless of file size.

Tested against a 500-page nutrition textbook: 24/25 questions correct (96%)
out of the box, no fine-tuning.

pip install docnest-ai

Would love feedback from anyone who's hit the table-extraction problem in
production RAG.

# WHEN TO POST
Tuesday, Wednesday, or Thursday — between 8am-10am US Eastern time.
That's when HN front page is most competitive but also most active.
