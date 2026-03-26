# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

This project uses `uv` (not pip). Always use `uv` for dependency and environment management:

```bash
uv add <package>          # Add a runtime dependency
uv add --dev <package>    # Add a dev dependency
uv run <command>          # Run a command in the project environment
uv sync                   # Sync dependencies from uv.lock
```

## Commands

```bash
uv run ruff check .                # Lint
uv run ruff check --fix .          # Lint with auto-fix
uv run ruff format .               # Format
uv run ty check                    # Type check
uv run pytest                      # Run tests
uv run sergey check <path>...      # Run sergey on files or directories
uv run sergey check .              # Check the whole repository
uv run sergey serve                # Run LSP server over stdio
```

## Linting

Ruff is configured with `select = ["ALL"]` — all rules enabled. Docstrings follow Google convention (`pydocstyle.convention = "google"`). The formatter uses double quotes and spaces.

`ty` (Astral's type checker) is used instead of mypy or pyright.

## Python Version

Python 3.14 (see `.python-version`). CI also tests against Python 3.11 for compatibility.

## Adding a Rule

When adding or modifying a rule, always update the `Rules` section in `README.md` to reflect the change. Keep rule descriptions in the README accurate and in sync with the implementation.

---

## Codebase Structure

```
sergey/
├── __init__.py         # Package docstring
├── __main__.py         # CLI entry point (check, serve commands)
├── analyzer.py         # Core analysis orchestration + suppression logic
├── config.py           # Configuration loading from pyproject.toml
├── server.py           # LSP server via pygls
└── rules/
    ├── __init__.py     # ALL_RULES tuple (single source of truth)
    ├── base.py         # Rule ABC, Diagnostic, Fix, TextEdit, Severity
    ├── docs.py         # DOC001
    ├── imports.py      # IMP001, IMP002, IMP003, IMP004
    ├── naming.py       # NAM001, NAM002, NAM003
    ├── pydantic.py     # PDT001, PDT002, PDT003
    └── structure.py    # STR002, STR003, STR004, STR005, STR006

tests/
├── test_config.py
├── test_suppression.py
└── rules/
    ├── test_docs.py
    ├── test_imports.py
    ├── test_naming.py
    ├── test_pydantic.py
    └── test_structure.py
```

## Rule Architecture

### Base Types (`sergey/rules/base.py`)

- **`Rule`** (ABC): All rules implement `check(tree: ast.Module, source: str) -> list[Diagnostic]` and optionally `configure(options: dict) -> Rule`.
- **`Diagnostic`**: Holds `rule_id`, `message`, line/col (1-indexed lines, 0-indexed cols), `severity`, and an optional `Fix`.
- **`Fix`**: Holds `replacement` text and optional `additional_edits: list[TextEdit]`. Apply edits bottom→top to preserve offsets.
- **`Severity`**: `ERROR`, `WARNING`, `INFORMATION`, `HINT`.

### Rule ID Convention

Rule IDs follow the pattern `CAT###`:
- `IMP` — import style
- `NAM` — naming
- `DOC` — documentation
- `PDT` — Pydantic
- `STR` — code structure

The class name matches the rule ID exactly (e.g., `class IMP001(base.Rule)`).

### Registering a New Rule

1. Implement the rule class in the appropriate module under `sergey/rules/`.
2. Add an instance to `ALL_RULES` in `sergey/rules/__init__.py`.
3. Add tests in `tests/rules/test_<category>.py`.
4. Update the `Rules` section in `README.md`.

### Auto-Fix Guidelines

- Return a `Fix` on `Diagnostic` when the transformation is unambiguous and safe.
- Return `fix=None` when ambiguous (e.g., star imports, name conflicts).
- `additional_edits` in a `Fix` are applied bottom→top, right→left to keep offsets stable.
- The CLI `--fix` flag applies fixes via `_apply_fixes()` in `__main__.py`.

### Configurable Rules

Rules may accept per-rule options from `[tool.sergey.rules.RULEID]` in `pyproject.toml`:

```toml
[tool.sergey.rules]
STR002 = { max_depth = 5 }
STR003 = { max_body_stmts = 5 }
```

Implement by overriding `configure(options: dict) -> Rule` to return a new instance with updated state.

## Suppression System

Suppressions are handled in `sergey/analyzer.py`:

- **Line-level**: `# sergey: noqa` (suppress all rules on that line) or `# sergey: noqa: IMP001, NAM002`
- **File-level**: `# sergey: disable-file` (suppress all rules in the file) or `# sergey: disable-file: IMP001`

Rule IDs in suppression comments are case-insensitive.

## Configuration (`sergey/config.py`)

`load_config(start)` walks up from the given directory to find `pyproject.toml` and reads `[tool.sergey]`:

```toml
[tool.sergey]
select = ["IMP001", "NAM001"]  # Run only these rules (default: all)
ignore = ["DOC001"]             # Always skip these rules
```

`filter_rules()` applies `select` then `ignore`. `configure_rules()` passes per-rule options dict to `rule.configure()`.

## LSP Server (`sergey/server.py`)

Uses `pygls`. Handles three notifications:
- `textDocument/didOpen` — analyze and publish diagnostics
- `textDocument/didChange` — re-analyze on every change
- `textDocument/didClose` — clear diagnostics

Severity mapping: `ERROR → 1`, `WARNING → 2`, `INFORMATION → 3`, `HINT → 4`.

## Testing Conventions

- Tests use pytest with class-based organization (e.g., `class TestIMP001`).
- Use focused `Analyzer` instances with only the relevant rules to avoid test interference.
- Use `textwrap.dedent()` for readable multi-line code strings.
- Helper `_ids(diagnostics)` extracts rule IDs for concise assertions.
- Tests in `tests/**` have relaxed ruff rules: no `S101` (asserts OK), no `D1`/`D2` (docstrings optional), `PLR2004` (magic values OK).

## CI/CD

- **`ci.yml`**: Runs `uv run pytest` on a matrix of Python 3.11 and 3.14 × Ubuntu, macOS, Windows.
- **`publish.yml`**: Publishes to PyPI via trusted publisher when a release tag matching `v*.*.*` is created.
