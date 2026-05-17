# Test Fixtures

Place sample documents here for use in tests.

## Required files

| Filename | Purpose |
|---|---|
| `sample_text.pdf` | Text-based PDF with at least 3 headings and 1 table |
| `sample_scanned.pdf` | Scanned PDF for OCR testing |
| `sample.docx` | Word document with headings and a table |
| `sample_with_tables.xlsx` | Excel file with at least 2 sheets, each with headers |
| `sample.html` | HTML file with h1-h3 headings and a `<table>` |
| `sample.md` | Markdown with headings, a table, and code block |

## Guidelines

- Keep files small (< 500KB each) — they are committed to the repo
- Use synthetic/public-domain content only — no confidential data
- Name files clearly and consistently — see table above
- If you create a new parser, add a matching fixture file and test

## Generating fixtures

You can generate minimal synthetic fixtures using the scripts in `docs/examples/`.
