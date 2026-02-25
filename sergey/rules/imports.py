"""Import-style rules: IMP001, IMP002, IMP003, and IMP004."""

import ast
from importlib import util as importlib_util

from sergey.rules import base

# Modules excluded from IMP001 — covered by IMP002/IMP004 or are special syntax.
_IMP001_EXCLUDED: frozenset[str] = frozenset(
    {"__future__", "typing", "typing_extensions", "collections.abc"}
)

# Typing modules covered by IMP002.
_TYPING_MODULES: frozenset[str] = frozenset({"typing", "typing_extensions"})

# Modules excluded from IMP003 — they are covered by a more specific rule.
_IMP003_EXCLUDED: frozenset[str] = frozenset({"collections.abc"})

# Collections modules covered by IMP004.
_COLLECTIONS_MODULES: frozenset[str] = frozenset({"collections.abc"})


def _imp003_fix(node: ast.Import) -> base.Fix:
    """Build the replacement text for an IMP003 violation on *node*.

    Each dotted alias is rewritten as ``from parent import name``; non-dotted
    aliases are kept as plain ``import`` statements.  When the node contains
    multiple aliases the replacements are joined with newlines, preserving the
    original indentation for every subsequent line.
    """
    indent = " " * node.col_offset
    parts: list[str] = []
    for alias in node.names:
        if "." in alias.name and alias.name not in _IMP003_EXCLUDED:
            parent, _, name = alias.name.rpartition(".")
            stmt = f"from {parent} import {name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
        else:
            stmt = f"import {alias.name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
        parts.append(stmt)
    return base.Fix(replacement=f"\n{indent}".join(parts))


def _imp001_fix(
    node: ast.ImportFrom, bad_aliases: list[ast.alias]
) -> base.Fix | None:
    """Build the replacement for an IMP001 violation on *node*.

    Converts non-module from-imports to module-level imports:

    - Absolute: ``from os.path import join`` → ``import os.path``
    - Relative: ``from .utils import Helper`` → ``from . import utils``

    Good aliases (those that resolve to real submodules) are preserved in a
    separate from-import statement.  Returns ``None`` when no unambiguous fix
    exists (e.g. ``from . import Name`` with no module component).
    """
    indent = " " * node.col_offset
    module = node.module or ""
    dots = "." * node.level
    parts: list[str] = []

    # Keep submodule imports that were not flagged.
    bad_ids = {id(a) for a in bad_aliases}
    good_aliases = [a for a in node.names if id(a) not in bad_ids]
    if good_aliases:
        names_str = ", ".join(
            f"{a.name} as {a.asname}" if a.asname else a.name
            for a in good_aliases
        )
        parts.append(f"from {dots}{module} import {names_str}")

    # Build the replacement import for the flagged module.
    if node.level == 0:
        # Absolute: import the module directly.
        if not module:
            return None
        parts.append(f"import {module}")
    else:
        # Relative: convert from-import to a relative module import.
        if not module:
            return None  # ``from . import Name`` — no module component.
        if "." in module:
            parent, _, name = module.rpartition(".")
            parts.append(f"from {dots}{parent} import {name}")
        else:
            parts.append(f"from {dots} import {module}")

    return base.Fix(replacement=f"\n{indent}".join(parts))


def _is_submodule(parent: str, name: str) -> bool:
    """Return True if `parent.name` resolves to an importable module or package."""
    try:
        return importlib_util.find_spec(f"{parent}.{name}") is not None
    except Exception:  # noqa: BLE001
        return False


class IMP001(base.Rule):
    """Flag from-imports that import names (classes/functions) instead of modules.

    Submodule imports are allowed — only names that cannot be resolved as a
    module are flagged.

    Allowed:
        import os
        from os import path
        from lsprotocol import types   # types is a submodule

    Flagged:
        from os.path import join
        from collections import OrderedDict
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every non-typing from-import of a non-module name."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if module in _IMP001_EXCLUDED:
                continue

            # For absolute imports, skip names that resolve to submodules.
            if node.level == 0 and module:
                bad_aliases = [
                    alias
                    for alias in node.names
                    if not _is_submodule(module, alias.name)
                ]
            else:
                bad_aliases = list(node.names)

            if not bad_aliases:
                continue

            names = ", ".join(alias.name for alias in bad_aliases)
            dots = "." * node.level
            module_display = f"{dots}{module}" if module else dots
            diagnostics.append(
                base.Diagnostic(
                    rule_id="IMP001",
                    message=(
                        f"Import the module directly instead of importing"
                        f" `{names}` from `{module_display}`"
                    ),
                    line=node.lineno,
                    col=node.col_offset,
                    end_line=node.end_lineno or node.lineno,
                    end_col=node.end_col_offset or node.col_offset,
                    severity=base.Severity.WARNING,
                    fix=_imp001_fix(node, bad_aliases),
                )
            )
        return diagnostics


class IMP002(base.Rule):
    """Flag plain imports of typing modules; require from-imports instead.

    Allowed:
        from typing import Optional
        from typing_extensions import Protocol

    Flagged:
        import typing
        import typing_extensions
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every plain import of a typing module."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.name not in _TYPING_MODULES:
                    continue
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="IMP002",
                        message=(
                            f"Use `from {alias.name} import ...`"
                            f" instead of `import {alias.name}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                    )
                )
        return diagnostics


class IMP003(base.Rule):
    """Flag dotted plain imports; require `from X import Y` for submodule access.

    Allowed:
        import os
        from os import path
        from pygls.lsp import server

    Flagged:
        import os.path
        import pygls.lsp.server
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every dotted plain import."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if "." not in alias.name:
                    continue
                if alias.name in _IMP003_EXCLUDED:
                    continue
                parent, _, name = alias.name.rpartition(".")
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="IMP003",
                        message=(
                            f"Use `from {parent} import {name}`"
                            f" instead of `import {alias.name}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                        fix=_imp003_fix(node),
                    )
                )
        return diagnostics


class IMP004(base.Rule):
    """Flag plain imports of collections.abc; require from-imports instead.

    Allowed:
        from collections.abc import Mapping
        from collections.abc import Callable, Sequence

    Flagged:
        import collections.abc
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every plain import of a collections module."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.name not in _COLLECTIONS_MODULES:
                    continue
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="IMP004",
                        message=(
                            f"Use `from {alias.name} import ...`"
                            f" instead of `import {alias.name}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                    )
                )
        return diagnostics
