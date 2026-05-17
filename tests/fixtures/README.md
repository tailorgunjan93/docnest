# Test Fixtures

Place sample documents here for use in tests.

## Document Fixtures

| Filename | Purpose |
|---|---|
| `sample_text.pdf` | Text-based PDF with at least 3 headings and 1 table |
| `sample_scanned.pdf` | Scanned PDF for OCR testing |
| `sample.docx` | Word document with headings and a table |
| `sample_with_tables.xlsx` | Excel file with at least 2 sheets, each with headers |
| `sample.html` | HTML file with h1–h3 headings and a `<table>` |
| `sample.md` | Markdown with headings, a table, and code block |

## UDF Fixtures

| Filename | Purpose |
|---|---|
| `sample_fast.udf` | Minimal UDF built with `--fast` (embeddings only, no LLM intelligence) |
| `sample_full.udf` | Full UDF with LLM intelligence: summary, insights, key_numbers |
| `sample_binary.udf` | UDF with `embeddings.bin` binary blob (`embedding_format: "binary"`) |
| `sample_base64.udf` | UDF with legacy base64 per-section embeddings (backward-compat testing) |
| `sample_docmeta.udf` | UDF with all DocMeta fields: owner, department, tags, access_roles |

## Library Fixtures

| Filename | Purpose |
|---|---|
| `library.json` | Sample `library.json` index with 3 entries and `keywords_bag` populated |

## Guidelines

- Keep files small (< 500KB each) — they are committed to the repo
- Use synthetic/public-domain content only — no confidential data
- Name files clearly and consistently — see tables above
- If you create a new parser, add a matching document fixture and test
- If you create a new vector backend, add tests that use the UDF fixtures above

## Generating fixtures

You can generate minimal synthetic fixtures using the scripts in `docs/examples/`.

To regenerate the UDF fixtures from the document fixtures:

```bash
# Fast (no LLM required)
docnest convert tests/fixtures/sample_text.pdf --fast --out tests/fixtures/sample_fast.udf

# Full (requires Ollama running)
docnest convert tests/fixtures/sample_text.pdf \
  --llm-provider ollama --llm-model llama3.2 \
  --out tests/fixtures/sample_full.udf
```
