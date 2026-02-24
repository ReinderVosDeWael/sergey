# sergey

A Python linter with opinionated rules about import style, naming, and code structure. Runs as a CLI tool or as an LSP server for editor integration.

The primary intent of Sergey is to enforce my personal stylistic rules upon agentic code.
However, you may also find these useful in standard development. Simultaneously, it is a testing
space for me for agentic coding. 

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

| Rule       | Description                                                                                                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **IMP001** | `from module import name` is disallowed when `name` is not itself a submodule. Use `import module` and reference `module.name` at call sites. Typing modules, `__future__`, and `collections.abc` are exempt (see IMP002 and IMP004). |
| **IMP002** | `import typing` and `import typing_extensions` are disallowed. Use `from typing import X` and `from typing_extensions import X` to import names directly.                                                                             |
| **IMP003** | Dotted plain imports (`import os.path`) are disallowed. Use `from os import path` instead. `collections.abc` is exempt (see IMP004).                                                                                                  |
| **IMP004** | `import collections.abc` is disallowed. Use `from collections.abc import X` to import names directly.                                                                                                                                 |

The four rules together enforce a consistent import style: every name you use is either a bare module you imported at the top level, or a submodule you accessed via `from package import submodule`.

### Naming

| Rule       | Description                                                                                                                                                                                                                         |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **NAM001** | Functions annotated `-> bool` must start with a predicate prefix: `is_`, `has_`, `can_`, `should_`, `will_`, `did_`, or `was_`. Dunder methods are exempt. Leading underscores on private helpers are ignored (`_is_valid` passes). |
| **NAM002** | Single-character variable names are disallowed in assignments, for-loops, comprehensions, with-statements, and walrus expressions. The conventional throwaway `_` is exempt.                                                        |
| **NAM003** | Single-character function and method parameter names are disallowed. Covers positional-only, regular, and keyword-only parameters. `_`, `*args`, and `**kwargs` are exempt. Lambda parameters are not checked.                      |

### Documentation

| Rule       | Description                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **DOC001** | Functions that contain explicit `raise` statements must include a `Raises` section in their docstring. Bare re-raises (`raise` with no argument) are exempt. Raises inside nested functions or classes belong to those scopes and are not counted against the outer function. Functions with no docstring are not checked. Both Google style (`Raises:`) and NumPy style (`Raises` / `------`) are accepted. |

### Pydantic

| Rule       | Description                                                                                                                                                                                                                                                                          |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **PDT001** | Every `BaseModel` subclass must have `model_config = ConfigDict(frozen=...)` with `frozen` explicitly set. This forces a deliberate decision about mutability. Both `frozen=True` and `frozen=False` are accepted; omitting `frozen` or omitting `model_config` entirely is flagged. |
| **PDT002** | Frozen `BaseModel` subclasses (`frozen=True`) must not have fields annotated with mutable types such as `list`, `dict`, `set`, `deque`, etc. Use immutable alternatives (`tuple`, `frozenset`, …) instead. The check recurses into generic parameters and union syntax, so `Optional[list[str]]` and `str \| list[int]` are both caught. `ClassVar` annotations are exempt. |

### Structure

| Rule       | Description                                                                                                                                                                                                                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **STR002** | Control-flow blocks nested deeper than 4 levels are flagged. Counted constructs: `if`/`elif`/`else`, `for`, `while`, `with`, `try`, `match`. `elif` branches count at the same depth as their leading `if`. Function, class, and lambda definitions reset the counter, so nested functions are judged independently. |
| **STR003** | `try` bodies containing more than 4 statements are flagged. Statements are counted recursively (an `if` with branches contributes 1 plus all contained statements). Only the `try:` body is counted — `except` and `finally` blocks are not subject to this rule. Nested functions and classes reset the count. |
| **STR004** | List and set literals inside functions that are never mutated and are not part of the function output (`return`/`yield`) should use immutable alternatives: `tuple` instead of `[]` and `frozenset` instead of `{}`. Only plain literals are checked; constructor calls and comprehensions are not covered. |

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
