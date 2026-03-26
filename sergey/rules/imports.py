"""Import-style rules: IMP001, IMP002, IMP003, and IMP004."""

import ast
from importlib import util as importlib_util
from typing import Final

from sergey.rules import base

# Modules excluded from IMP001 — covered by IMP002/IMP004 or are special syntax.
_IMP001_EXCLUDED: Final[frozenset[str]] = frozenset(
    {"__future__", "typing", "typing_extensions", "collections.abc"}
)

# Typing modules covered by IMP002.
_TYPING_MODULES: Final[frozenset[str]] = frozenset({"typing", "typing_extensions"})

# Modules excluded from IMP003 — they are covered by a more specific rule.
_IMP003_EXCLUDED: Final[frozenset[str]] = frozenset({"collections.abc"})

# Collections modules covered by IMP004.
_COLLECTIONS_MODULES: Final[frozenset[str]] = frozenset({"collections.abc"})


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


def _has_name_conflict(
    name: str,
    exclude_names: set[str],
    tree: ast.Module,
) -> bool:
    """Return True if *name* is already used in *tree* outside *exclude_names*."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == name and n.id not in exclude_names:
            return True
        if isinstance(n, ast.Import):
            for alias in n.names:
                local = alias.asname or (
                    alias.name if "." not in alias.name else None
                )
                if local == name and local not in exclude_names:
                    return True
        if isinstance(n, ast.ImportFrom):
            for alias in n.names:
                if alias.name != "*":
                    local = alias.asname or alias.name
                    if local == name and local not in exclude_names:
                        return True
    return False


def _imp001_fix(
    node: ast.ImportFrom,
    bad_aliases: list[ast.alias],
    tree: ast.Module,
) -> base.Fix | None:
    """Build a fix for an IMP001 violation on *node*.

    Rewrites the import statement and all call-site references so that the
    module is imported directly and names are accessed as attributes.  The
    replacement import is always IMP003-compliant: dotted absolute modules use
    ``from parent import leaf`` syntax rather than ``import parent.leaf``.

    When the leaf name would conflict with an existing binding, an ``as``
    alias is added using the full module path with dots replaced by
    underscores (e.g. ``from os import path as os_path``).

    Returns ``None`` when a star import is involved (cannot be fixed
    automatically).
    """
    if any(alias.name == "*" for alias in bad_aliases):
        return None

    module = node.module or ""
    level = node.level
    indent = " " * node.col_offset
    dots = "." * level

    good_aliases = [alias for alias in node.names if alias not in bad_aliases]

    # --- Build the replacement import statement(s) ---
    parts: list[str] = []

    if good_aliases:
        good_names = ", ".join(
            f"{alias.name} as {alias.asname}" if alias.asname else alias.name
            for alias in good_aliases
        )
        parts.append(f"from {dots}{module} import {good_names}")

    # Determine the IMP003-compliant import and the local name used for rewrites.
    bad_local_names = {alias.asname or alias.name for alias in bad_aliases}
    if level == 0 and "." in module:
        # Absolute dotted: use ``from parent import leaf`` (IMP003-compliant).
        parent, _, leaf = module.rpartition(".")
        if _has_name_conflict(leaf, bad_local_names, tree):
            module_local = module.replace(".", "_")
            parts.append(f"from {parent} import {leaf} as {module_local}")
        else:
            module_local = leaf
            parts.append(f"from {parent} import {leaf}")
        ref_prefix = module_local
    elif level == 0:
        # Absolute non-dotted: ``import <module>``
        parts.append(f"import {module}")
        ref_prefix = module
    elif "." in module:
        # Relative with dotted module: ``from .<parent> import <leaf>``
        parent, _, leaf = module.rpartition(".")
        parts.append(f"from {dots}{parent} import {leaf}")
        ref_prefix = leaf
    else:
        # Simple relative: ``from <dots> import <module>``
        parts.append(f"from {dots} import {module}")
        ref_prefix = module

    replacement = f"\n{indent}".join(parts)

    # --- Map local names to their qualified replacements ---
    name_map: dict[str, str] = {}
    for alias in bad_aliases:
        local_name = alias.asname or alias.name
        name_map[local_name] = f"{ref_prefix}.{alias.name}"

    # --- Collect reference edits ---
    additional_edits = [
        base.TextEdit(
            line=ref.lineno,
            col=ref.col_offset,
            end_line=ref.end_lineno or ref.lineno,
            end_col=ref.end_col_offset or (ref.col_offset + len(ref.id)),
            replacement=name_map[ref.id],
        )
        for ref in ast.walk(tree)
        if isinstance(ref, ast.Name)
        and isinstance(ref.ctx, ast.Load)
        and ref.id in name_map
    ]

    return base.Fix(replacement=replacement, additional_edits=additional_edits)


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
            elif node.level > 0 and not module:
                # Bare relative imports (e.g. `from . import rules`) are used to
                # import sibling submodules.  We cannot verify submodule status
                # without knowing the package root, so we skip them entirely to
                # avoid false positives.
                continue
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
                    fix=_imp001_fix(node, bad_aliases, tree),
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
