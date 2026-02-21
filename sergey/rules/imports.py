"""Import-style rules: IMP001, IMP002, and IMP003."""

import ast
from importlib import util as importlib_util

from sergey.rules import base

# Modules excluded from IMP001 — they are covered by IMP002 or are special syntax.
_IMP001_EXCLUDED: frozenset[str] = frozenset({"__future__", "typing"})

# Typing modules covered by IMP002.
_TYPING_MODULES: frozenset[str] = frozenset({"typing", "typing_extensions"})


def _is_submodule(parent: str, name: str) -> bool:
    """Return True if `parent.name` resolves to an importable module or package."""
    try:
        return importlib_util.find_spec(f"{parent}.{name}") is not None
    except (ModuleNotFoundError, ValueError):
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
        try:
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
                    )
                )
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics


class IMP002(base.Rule):
    """Flag from-imports of typing modules; require `import typing` instead.

    Allowed:
        import typing

    Flagged:
        from typing import Optional
        from typing_extensions import Protocol
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every from-import of a typing module."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module not in _TYPING_MODULES:
                    continue
                names = ", ".join(alias.name for alias in node.names)
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="IMP002",
                        message=(
                            f"Use `import {node.module}` instead of"
                            f" importing `{names}` from `{node.module}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                    )
                )
        except Exception:  # noqa: BLE001, S110
            pass
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
        try:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Import):
                    continue
                for alias in node.names:
                    if "." not in alias.name:
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
                        )
                    )
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics
