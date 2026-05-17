# Contributing to DOCNEST

First off — thank you. DOCNEST is being built in the open and every contribution matters.

---

## Ways to Contribute

### 🐛 Report a Bug
Open an issue using the **Bug Report** template. Include:
- DOCNEST version
- Document format you were processing
- Expected vs actual behavior
- Minimal reproducible example if possible

### 💡 Suggest a Feature
Open an issue using the **Feature Request** template. Describe:
- The problem you are trying to solve
- Your proposed solution
- Any alternatives you considered

### 🔨 Contribute Code
1. Find an issue labeled `good first issue` or `help wanted`
2. Comment on it to claim it — we will assign it to you
3. Fork the repo, create a branch: `git checkout -b feat/your-feature`
4. Make your changes following the guidelines below
5. Open a Pull Request — fill in the PR template

### 📖 Improve Documentation
Documentation PRs are always welcome. No issue required for small fixes.

---

## Development Setup

```bash
git clone https://github.com/tailorgunjan93/DOCNESTd
cd DOCNESTd
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/ -v
```

### Prerequisites
- Python 3.11+
- Ollama (for integration tests): https://ollama.ai
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```

---

## Code Guidelines

### Style
- Formatter: `black` (line length 100)
- Linter: `ruff`
- Type hints: required on all public functions
- Docstrings: Google style

```bash
black DOCNEST/
ruff check DOCNEST/
mypy DOCNEST/
```

### Architecture principles (SOLID)
- **Single Responsibility** — one class, one job. `PDFParser` only parses. `Quantizer` only quantizes.
- **Open/Closed** — extend via new implementations, not modifications. New format = new `IParser` class.
- **Dependency Inversion** — depend on abstractions. `DOCNESTPipeline` takes `IEmbedder`, not `NomicEmbedder`.

See [docs/SPEC_DOCNEST_PYPI.md](docs/SPEC_DOCNEST_PYPI.md) for the full design.

### Tests
- Every new feature needs unit tests
- Use `tests/fixtures/` for sample documents — add minimal files only
- Mock LLM calls in unit tests — use `pytest-mock`
- Target coverage: 85%+ on new code

```bash
pytest tests/ -v --cov=DOCNEST --cov-report=term-missing
```

---

## Pull Request Process

1. Run `black`, `ruff`, `mypy`, and `pytest` before opening a PR
2. Fill in the PR template completely
3. One PR = one logical change
4. Link to the issue: `Closes #123`
5. A maintainer will review within 3 business days

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add PPTX parser via Docling
fix: handle empty tables in Excel parser
docs: add connector setup guide
test: add fixtures for scanned PDF parsing
refactor: extract quantizer to standalone module
```

---

## Adding a New Parser

1. Create `DOCNEST/parsers/yourformat.py`
2. Implement `IParser` abstract base class
3. Register in `DOCNEST/parsers/factory.py`
4. Add test fixtures in `tests/fixtures/`
5. Add tests in `tests/test_parsers.py`
6. Update supported formats table in `README.md`

See `DOCNEST/parsers/pdf.py` as the reference implementation.

---

## Adding a New Connector

1. Create `DOCNEST/connectors/yourservice.py`
2. Implement `IConnector` abstract base class
3. Add integration test (mock the external API)
4. Document required config (API token, base URL, etc.)

---

## Code of Conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## Questions?

Open a [Discussion](https://github.com/tailorgunjan93/DOCNESTd/discussions) — not an issue. Discussions are for questions, ideas, and architecture conversations.
