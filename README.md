# sergey

A Python linter with opinionated rules about import style, naming, and code structure. Runs as a CLI tool or as an LSP server for editor integration.

## Installation

```bash
uv add sergey
```

## Usage

### CLI

```bash
sergey check path/to/file.py     # check a single file
sergey check src/ tests/         # check directories (recursive)
sergey check .                   # check the whole project
```

Exits with code `0` if no violations are found, `1` if any are found.

### LSP server

```bash
sergey serve
```

Communicates over stdio using the Language Server Protocol. Configure your editor to launch this command as a language server for Python files.

## Rules

### Imports

| Rule | Description |
|------|-------------|
| **IMP001** | `from module import name` is disallowed when `name` is not itself a submodule. Use `import module` and reference `module.name` at call sites. Typing modules and `__future__` are exempt (see IMP002). |
| **IMP002** | `from typing import X` and `from typing_extensions import X` are disallowed. Use `import typing` and write `typing.X`. |
| **IMP003** | Dotted plain imports (`import os.path`) are disallowed. Use `from os import path` instead. |

The three rules together enforce a consistent import style: every name you use is either a bare module you imported at the top level, or a submodule you accessed via `from package import submodule`.

### Naming

| Rule | Description |
|------|-------------|
| **NAM001** | Functions annotated `-> bool` must start with a predicate prefix: `is_`, `has_`, `can_`, `should_`, `will_`, `did_`, or `was_`. Dunder methods are exempt. Leading underscores on private helpers are ignored (`_is_valid` passes). |
| **NAM002** | Single-character variable names are disallowed in assignments, for-loops, comprehensions, with-statements, and walrus expressions. The conventional throwaway `_` is exempt. |
| **NAM003** | Single-character function and method parameter names are disallowed. Covers positional-only, regular, and keyword-only parameters. `_`, `*args`, and `**kwargs` are exempt. Lambda parameters are not checked. |

### Structure

| Rule | Description |
|------|-------------|
| **STR002** | Control-flow blocks nested deeper than 4 levels are flagged. Counted constructs: `if`/`elif`/`else`, `for`, `while`, `with`, `try`, `match`. `elif` branches count at the same depth as their leading `if`. Function, class, and lambda definitions reset the counter, so nested functions are judged independently. |

## Suppression

### Suppress a single line

```python
x = some_function()  # sergey: noqa
x = some_function()  # sergey: noqa: NAM002
x = some_function()  # sergey: noqa: NAM002, IMP001
```

### Suppress an entire file

Place this comment anywhere in the file (position does not matter):

```python
# sergey: disable-file
# sergey: disable-file: IMP001
# sergey: disable-file: IMP001, IMP002
```

## Development

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run ty check            # type check
uv run pytest              # run tests
uv run sergey check .      # run sergey on itself
```

### Adding a rule

1. Create or extend a module in `sergey/rules/` with a class that subclasses `base.Rule` and implements `check(tree, source) -> list[Diagnostic]`.
2. Register the rule in `sergey/rules/__init__.py` by adding an instance to `ALL_RULES`.
3. Add tests in `tests/rules/`.

Rule IDs follow the pattern `CAT###` where `CAT` is a short category prefix (`IMP`, `NAM`, `STR`, …) and `###` is a three-digit number.
