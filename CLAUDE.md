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
uv run ruff check .                          # Lint
uv run ruff check --fix .                    # Lint with auto-fix
uv run ruff format .                         # Format
uv run ty check                              # Type check
uv run pytest                                # Run tests
uv run sergey check <path>...           # Run sergey on files or directories
uv run sergey check .                   # Check the whole repository
uv run sergey serve                     # Run LSP server over stdio
```

## Linting

Ruff is configured with `select = ["ALL"]` — all rules enabled. Docstrings follow Google convention (`pydocstyle.convention = "google"`). The formatter uses double quotes and spaces.

`ty` (Astral's type checker) is used instead of mypy or pyright.

## Python Version

Python 3.14 (see `.python-version`).
