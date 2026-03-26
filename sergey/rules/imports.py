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


# ---------------------------------------------------------------------------
# Shared helpers for fix functions
# ---------------------------------------------------------------------------


def _is_attr_chain(node: ast.AST, parts: list[str]) -> bool:
    """Return True when *node* is an attribute chain ``parts[0].parts[1]...``."""
    for part in reversed(parts[1:]):
        if not (isinstance(node, ast.Attribute) and node.attr == part):
            return False
        node = node.value
    return isinstance(node, ast.Name) and node.id == parts[0]


def _chain_root(node: ast.AST) -> ast.Name | None:
    """Walk down ``.value`` links and return the innermost ``ast.Name``."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node if isinstance(node, ast.Name) else None


def _has_name_conflict(
    tree: ast.Module,
    name: str,
    exclude_node: ast.AST,
) -> bool:
    """Return True when *name* is already bound at module level."""
    return any(
        _did_stmt_bind_name(stmt, name)
        for stmt in tree.body
        if stmt is not exclude_node
    )


def _did_stmt_bind_name(stmt: ast.stmt, name: str) -> bool:
    """Return True when a single statement binds *name*."""
    if isinstance(stmt, ast.Import):
        return any(
            (alias.asname or alias.name.split(".")[0]) == name for alias in stmt.names
        )
    if isinstance(stmt, ast.ImportFrom):
        return any(
            alias.name != "*" and (alias.asname or alias.name) == name
            for alias in stmt.names
        )
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return stmt.name == name
    if isinstance(stmt, ast.Assign):
        return any(
            isinstance(target, ast.Name) and target.id == name
            for target in stmt.targets
        )
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return stmt.target.id == name
    return False


def _conflict_alias(parent: str, leaf: str) -> str:
    """Build a collision-safe alias: ``immediateParent_leaf``."""
    immediate = parent.rpartition(".")[2] or parent
    return f"{immediate}_{leaf}"


def _is_root_imported(
    tree: ast.Module,
    root: str,
    exclude_node: ast.AST,
) -> bool:
    """Return True when *root* is already bound by another ``import`` statement."""
    for stmt in tree.body:
        if stmt is exclude_node:
            continue
        if isinstance(stmt, ast.Import) and any(
            (alias.asname or alias.name.split(".")[0]) == root for alias in stmt.names
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# IMP003 fix
# ---------------------------------------------------------------------------


def _imp003_rewrite_alias(
    alias: ast.alias,
    tree: ast.Module,
    node: ast.Import,
) -> tuple[str, list[base.TextEdit], str | None]:
    """Process a single dotted alias for IMP003.

    Returns:
        A tuple of (import_statement, additional_edits, root_needing_import).
    """
    parent, _, leaf = alias.name.rpartition(".")

    if alias.asname:
        return f"from {parent} import {leaf} as {alias.asname}", [], None

    # Determine the reference name (with conflict resolution).
    if _has_name_conflict(tree, leaf, node):
        ref_name = _conflict_alias(parent, leaf)
        stmt = f"from {parent} import {leaf} as {ref_name}"
    else:
        ref_name = leaf
        stmt = f"from {parent} import {leaf}"

    # Rewrite attribute-chain references (e.g. os.path.join → path.join).
    dotted_parts = alias.name.split(".")
    root = dotted_parts[0]
    matched_root_ids: set[int] = set()
    edits: list[base.TextEdit] = []

    for ref in ast.walk(tree):
        if not isinstance(ref, ast.Attribute):
            continue
        if not _is_attr_chain(ref, dotted_parts):
            continue
        edits.append(
            base.TextEdit(
                line=ref.lineno,
                col=ref.col_offset,
                end_line=ref.end_lineno or ref.lineno,
                end_col=ref.end_col_offset or (ref.col_offset + len(alias.name)),
                replacement=ref_name,
            )
        )
        root_node = _chain_root(ref)
        if root_node is not None:
            matched_root_ids.add(id(root_node))

    # Check for standalone root usage.
    extra_root: str | None = None
    if not _is_root_imported(tree, root, node) and any(
        isinstance(ref, ast.Name)
        and ref.id == root
        and isinstance(ref.ctx, ast.Load)
        and id(ref) not in matched_root_ids
        for ref in ast.walk(tree)
    ):
        extra_root = root

    return stmt, edits, extra_root


def _imp003_fix(node: ast.Import, tree: ast.Module) -> base.Fix:
    """Build the replacement text for an IMP003 violation on *node*.

    Each dotted alias is rewritten as ``from parent import name``; non-dotted
    aliases are kept as plain ``import`` statements.  Call-site references are
    rewritten to use the leaf name.  When the leaf name conflicts with an
    existing binding, an ``as parent_leaf`` alias is generated.
    """
    indent = " " * node.col_offset
    parts: list[str] = []
    additional_edits: list[base.TextEdit] = []
    extra_root_imports: set[str] = set()

    for alias in node.names:
        if "." not in alias.name or alias.name in _IMP003_EXCLUDED:
            stmt = f"import {alias.name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
            parts.append(stmt)
            continue

        stmt, edits, extra_root = _imp003_rewrite_alias(alias, tree, node)
        parts.append(stmt)
        additional_edits.extend(edits)
        if extra_root is not None:
            extra_root_imports.add(extra_root)

    parts.extend(f"import {root}" for root in sorted(extra_root_imports))

    return base.Fix(
        replacement=f"\n{indent}".join(parts),
        additional_edits=additional_edits,
    )


# ---------------------------------------------------------------------------
# IMP001 fix
# ---------------------------------------------------------------------------


def _resolve_module_import(
    module: str,
    level: int,
    tree: ast.Module,
    node: ast.ImportFrom,
) -> tuple[str, str]:
    """Determine the import statement and reference prefix for IMP001.

    Returns:
        A tuple of (import_statement, ref_prefix).
    """
    dots = "." * level

    if level == 0 and "." not in module:
        return f"import {module}", module

    # Dotted module (absolute or relative) — split into parent/leaf.
    if "." in module:
        parent, _, leaf = module.rpartition(".")
        prefix = f"{dots}{parent}" if level else parent
    else:
        # Simple relative: ``from <dots> import <module>``
        parent, leaf, prefix = "", module, dots

    if _has_name_conflict(tree, leaf, node):
        safe = _conflict_alias(parent, leaf) if parent else f"{'_' * level}{leaf}"
        return f"from {prefix} import {leaf} as {safe}", safe
    return f"from {prefix} import {leaf}", leaf


def _imp001_fix(
    node: ast.ImportFrom,
    bad_aliases: list[ast.alias],
    tree: ast.Module,
) -> base.Fix | None:
    """Build a fix for an IMP001 violation on *node*.

    Rewrites the import statement and all call-site references so that the
    module is imported directly and names are accessed as attributes.

    The generated import is IMP003-compliant: for dotted modules
    (e.g. ``os.path``) the fix emits ``from os import path`` rather than
    ``import os.path``.  When the leaf name conflicts with an existing
    binding, an ``as parent_leaf`` alias is used.

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

    mod_stmt, ref_prefix = _resolve_module_import(module, level, tree, node)
    parts.append(mod_stmt)

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
                        fix=_imp003_fix(node, tree),
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
