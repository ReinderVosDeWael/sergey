"""Import-style rules: IMP001, IMP002, IMP003, IMP004, and IMP005."""

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


def _collect_simple_attr_refs(
    local_name: str,
    tree: ast.Module,
) -> tuple[list[ast.Attribute], bool]:
    """Collect ``local_name.attr`` attribute references (Load context only).

    Returns a pair ``(attr_refs, has_unsafe)`` where *has_unsafe* is ``True``
    when *local_name* appears in any context other than as the direct value of
    one of the returned ``Attribute`` nodes (e.g. a bare name reference).
    """
    attr_refs: list[ast.Attribute] = []
    safe_name_ids: set[int] = set()

    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == local_name
            and isinstance(n.ctx, ast.Load)
        ):
            attr_refs.append(n)
            safe_name_ids.add(id(n.value))

    has_unsafe = any(
        isinstance(n, ast.Name) and n.id == local_name and id(n) not in safe_name_ids
        for n in ast.walk(tree)
    )
    return attr_refs, has_unsafe


def _collect_dotted_attr_refs(
    outer: str,
    inner: str,
    tree: ast.Module,
) -> tuple[list[ast.Attribute], bool]:
    """Collect ``outer.inner.attr`` references (Load context only).

    Returns ``(refs, has_unsafe)``.  *has_unsafe* is ``True`` when *outer* or
    ``outer.inner`` appear in a context that cannot be automatically rewritten
    (e.g. ``outer.inner`` used as a value without a further attribute access).
    """
    # First pass: locate all ``outer.inner`` Attribute nodes.
    inner_attr_ids: set[int] = set()
    outer_name_ids_in_inner: set[int] = set()

    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == outer
            and n.attr == inner
        ):
            inner_attr_ids.add(id(n))
            outer_name_ids_in_inner.add(id(n.value))

    # Second pass: locate ``outer.inner.attr`` Attribute nodes.
    attr_refs: list[ast.Attribute] = []
    safe_inner_ids: set[int] = set()

    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Attribute)
            and id(n.value) in inner_attr_ids
            and isinstance(n.ctx, ast.Load)
        ):
            attr_refs.append(n)
            safe_inner_ids.add(id(n.value))

    has_unsafe_inner = any(k not in safe_inner_ids for k in inner_attr_ids)
    has_unsafe_outer = any(
        isinstance(n, ast.Name)
        and n.id == outer
        and id(n) not in outer_name_ids_in_inner
        for n in ast.walk(tree)
    )
    return attr_refs, has_unsafe_inner or has_unsafe_outer


def _imp002_fix(node: ast.Import, tree: ast.Module) -> base.Fix | None:
    """Build a fix for all IMP002 violations in *node*.

    Converts each ``import typing`` / ``import typing_extensions`` alias into
    a ``from <module> import <names>`` statement, collecting the attribute
    names actually referenced in the file.  Non-typing aliases in the same
    statement are preserved as plain ``import`` statements.

    Returns ``None`` when any typing alias is used in a way that cannot be
    automatically rewritten (bare name reference, name conflict, or no
    attribute accesses found).
    """
    indent = " " * node.col_offset
    parts: list[str] = []
    additional_edits: list[base.TextEdit] = []

    for alias in node.names:
        if alias.name not in _TYPING_MODULES:
            stmt = f"import {alias.name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
            parts.append(stmt)
            continue

        local_name = alias.asname or alias.name
        attr_refs, has_unsafe = _collect_simple_attr_refs(local_name, tree)
        if has_unsafe or not attr_refs:
            return None

        names = sorted({ref.attr for ref in attr_refs})
        if any(_has_name_conflict(name, {local_name}, tree) for name in names):
            return None

        parts.append(f"from {alias.name} import {', '.join(names)}")
        additional_edits.extend(
            base.TextEdit(
                line=ref.lineno,
                col=ref.col_offset,
                end_line=ref.end_lineno or ref.lineno,
                end_col=ref.end_col_offset or ref.col_offset,
                replacement=ref.attr,
            )
            for ref in attr_refs
        )

    return base.Fix(
        replacement=f"\n{indent}".join(parts),
        additional_edits=additional_edits,
    )


def _imp004_fix(node: ast.Import, tree: ast.Module) -> base.Fix | None:
    """Build a fix for all IMP004 violations in *node*.

    Converts each ``import collections.abc`` alias into a
    ``from collections.abc import <names>`` statement.  When an ``as`` alias
    is present the local name is used directly; otherwise the two-level
    ``collections.abc.X`` reference pattern is matched.

    Returns ``None`` when the alias is used in a way that cannot be
    automatically rewritten.
    """
    indent = " " * node.col_offset
    parts: list[str] = []
    additional_edits: list[base.TextEdit] = []

    for alias in node.names:
        if alias.name not in _COLLECTIONS_MODULES:
            stmt = f"import {alias.name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
            parts.append(stmt)
            continue

        if alias.asname:
            attr_refs, has_unsafe = _collect_simple_attr_refs(alias.asname, tree)
            exclude = {alias.asname}
        else:
            outer, _, inner = alias.name.rpartition(".")
            attr_refs, has_unsafe = _collect_dotted_attr_refs(outer, inner, tree)
            exclude = {outer}

        if has_unsafe or not attr_refs:
            return None

        names = sorted({ref.attr for ref in attr_refs})
        if any(_has_name_conflict(name, exclude, tree) for name in names):
            return None

        parts.append(f"from {alias.name} import {', '.join(names)}")
        additional_edits.extend(
            base.TextEdit(
                line=ref.lineno,
                col=ref.col_offset,
                end_line=ref.end_lineno or ref.lineno,
                end_col=ref.end_col_offset or ref.col_offset,
                replacement=ref.attr,
            )
            for ref in attr_refs
        )

    return base.Fix(
        replacement=f"\n{indent}".join(parts),
        additional_edits=additional_edits,
    )


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
    """Return True if `parent.name` resolves to an importable module or package.

    When the *parent* package itself cannot be resolved (e.g. it is not
    installed in the current environment), we conservatively return ``True``
    to avoid false positives on imports from unknown packages.
    """
    try:
        parent_spec = importlib_util.find_spec(parent)
    except Exception:  # noqa: BLE001
        return True

    if parent_spec is None:
        return True

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
            if not any(alias.name in _TYPING_MODULES for alias in node.names):
                continue
            fix = _imp002_fix(node, tree)
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
                        fix=fix,
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
            if not any(alias.name in _COLLECTIONS_MODULES for alias in node.names):
                continue
            fix = _imp004_fix(node, tree)
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
                        fix=fix,
                    )
                )
        return diagnostics


def _imp005_submodule_attrs(
    local_name: str,
    module_name: str,
    tree: ast.Module,
) -> frozenset[str]:
    """Return attribute names on *local_name* that are submodules of *module_name*."""
    submodules: set[str] = set()
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == local_name
            and isinstance(n.ctx, ast.Load)
            and _is_submodule(module_name, n.attr)
        ):
            submodules.add(n.attr)
    return frozenset(submodules)


def _imp005_fix(
    node: ast.Import,
    violating: dict[ast.alias, frozenset[str]],
    tree: ast.Module,
) -> base.Fix | None:
    """Build a fix for IMP005 violations in *node*.

    For each violating alias, emits a ``from module import sub1, sub2`` line and
    rewrites ``local.sub`` attribute references to bare ``sub``.  If the module
    is also used for non-submodule attribute access, the original ``import X``
    line is kept alongside the new from-import.  Returns ``None`` when a
    submodule name would conflict with an existing binding in scope.
    """
    indent = " " * node.col_offset
    parts: list[str] = []
    additional_edits: list[base.TextEdit] = []

    for alias in node.names:
        if alias not in violating:
            stmt = f"import {alias.name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
            parts.append(stmt)
            continue

        submodule_names = violating[alias]
        local_name = alias.asname or alias.name
        module_name = alias.name

        # Check for name conflicts with the submodule names we plan to introduce.
        for sub in sorted(submodule_names):
            if _has_name_conflict(sub, {local_name}, tree):
                return None

        # Collect all local_name.attr refs and determine whether the original
        # import must be kept (non-submodule attribute access or bare name usage).
        all_attr_refs, has_unsafe = _collect_simple_attr_refs(local_name, tree)
        non_sub_refs = [ref for ref in all_attr_refs if ref.attr not in submodule_names]
        needs_original = has_unsafe or bool(non_sub_refs)

        if needs_original:
            stmt = f"import {module_name}"
            if alias.asname:
                stmt += f" as {alias.asname}"
            parts.append(stmt)

        parts.append(f"from {module_name} import {', '.join(sorted(submodule_names))}")

        # Rewrite local_name.sub → sub at every reference site.
        sub_refs = [ref for ref in all_attr_refs if ref.attr in submodule_names]
        additional_edits.extend(
            base.TextEdit(
                line=ref.lineno,
                col=ref.col_offset,
                end_line=ref.end_lineno or ref.lineno,
                end_col=ref.end_col_offset or ref.col_offset,
                replacement=ref.attr,
            )
            for ref in sub_refs
        )

    return base.Fix(
        replacement=f"\n{indent}".join(parts),
        additional_edits=additional_edits,
    )


class IMP005(base.Rule):
    """Flag plain imports used to access submodules via attribute; require from-imports.

    When a module is imported with ``import X`` and subsequently accessed as
    ``X.submodule.something`` where ``submodule`` is a real importable submodule,
    prefer ``from X import submodule`` to make the submodule dependency explicit.

    Allowed:
        from os import path
        import os; os.getcwd()        # os itself, not a submodule access

    Flagged:
        import os; os.path.join(...)
        import docx; docx.declarative.Document()
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every plain import used via submodule access."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import):
                continue

            violating: dict[ast.alias, frozenset[str]] = {}
            for alias in node.names:
                # Skip dotted imports — IMP003 already handles those.
                if "." in alias.name:
                    continue
                local_name = alias.asname or alias.name
                submodules = _imp005_submodule_attrs(local_name, alias.name, tree)
                if submodules:
                    violating[alias] = submodules

            if not violating:
                continue

            fix = _imp005_fix(node, violating, tree)

            for alias, submodule_names in violating.items():
                names_str = ", ".join(sorted(submodule_names))
                local_name = alias.asname or alias.name
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="IMP005",
                        message=(
                            f"Use `from {alias.name} import {names_str}`"
                            f" instead of accessing submodule(s) via `{local_name}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                        fix=fix,
                    )
                )

        return diagnostics
