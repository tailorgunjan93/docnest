# Contributing to DOCNEST

First off — thank you. DOCNEST is being built in the open and every contribution matters.

---

## Ways to Contribute

### 🐛 Report a Bug
Open an issue using the **Bug Report** template. Include:
- DOCNEST version (`docnest --version`)
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

### Optional dependencies for vector backends

```bash
pip install faiss-cpu   # FAISS vector backend
pip install chromadb    # ChromaDB vector backend
```

### Prerequisites
- Python 3.11+
- Ollama (for local LLM integration tests): https://ollama.ai
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
black docnest/
ruff check docnest/
mypy docnest/
```

### Architecture principles (SOLID)
- **Single Responsibility** — one class, one job. `PDFParser` only parses. `Quantizer` only quantizes.
- **Open/Closed** — extend via new implementations, not modifications. New format = new `IParser` class.
- **Dependency Inversion** — depend on abstractions. `DocNestPipeline` takes `IEmbedder`, not a concrete class.

See [docs/SPEC_DOCNEST_PYPI.md](docs/SPEC_DOCNEST_PYPI.md) for the full design.

### Tests
- Every new feature needs unit tests
- Use `tests/fixtures/` for sample documents — add minimal files only
- Mock LLM calls in unit tests — use `pytest-mock`
- Target coverage: 85%+ on new code

```bash
pytest tests/ -v --cov=docnest --cov-report=term-missing
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
docs: add vector backend guide to CONTRIBUTING.md
test: add fixtures for scanned PDF parsing
refactor: extract quantizer to standalone module
```

---

## Adding a New Parser

1. Create `docnest/parsers/yourformat.py`
2. Implement `IParser` abstract base class (see `docnest/parsers/base.py`)
3. Register in `docnest/parsers/factory.py`
4. Add test fixtures in `tests/fixtures/`
5. Add tests in `tests/test_parsers.py`
6. Update the supported formats table in `README.md`

See `docnest/parsers/pdf.py` as the reference implementation.

Key things every parser must do:
- Call `self._make_doc_id(file_path)` for slug generation (handles CamelCase, digits, separators)
- Return a `RawDocument` with a populated `sections` list
- Assign `§id` hierarchy via `SectionNormalizer` (or delegate to it)

---

## Adding a New Vector Backend

1. Create (or add to) `docnest/providers/vector.py`
2. Subclass `IVectorBackend`
3. Implement the four required methods:

```python
class MyVectorBackend(IVectorBackend):
    def build(self, ids: list[str], matrix: np.ndarray) -> None:
        """Index the embedding matrix. Called once after embeddings are loaded."""
        ...

    def search(self, query: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """Return up to k (section_id, score) pairs, highest score first."""
        ...

    def is_available(self) -> bool:
        """Return True if the required library is installed."""
        ...

    def is_ready(self) -> bool:
        """Return True if build() has been called and the index is populated."""
        ...
```

4. Register in `get_vector_backend()` factory at the bottom of `vector.py`
5. Export from `docnest/providers/__init__.py`
6. Add install instructions to `README.md` provider table
7. Add tests in `tests/test_vector_backends.py`

See `NumpyVectorBackend` as the simplest reference. See `FAISSVectorBackend` for an example with optional persistence.

---

## Adding a New Search Provider

1. Add to `docnest/providers/search.py`
2. Subclass `ISearchProvider`
3. Implement `index(ids, texts)` and `search(query, k)` → `list[tuple[str, float]]`
4. Register in `get_search_provider()` factory
5. Export from `docnest/providers/__init__.py`

---

## Adding a New Storage Backend

1. Add to `docnest/providers/storage.py`
2. Subclass `IStorageBackend`
3. Implement `read(key)` → `bytes` and `write(key, data)`
4. Register in `get_storage_backend()` factory
5. Export from `docnest/providers/__init__.py`

---

## Adding a New Connector

1. Create `docnest/connectors/yourservice.py`
2. Implement `IConnector` abstract base class
3. Add integration test (mock the external API)
4. Document required config (API token, base URL, etc.)

---

## Code of Conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## Questions?

Open a [Discussion](https://github.com/tailorgunjan93/DOCNESTd/discussions) — not an issue. Discussions are for questions, ideas, and architecture conversations.
