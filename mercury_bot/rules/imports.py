"""Import-style rules: IMP001 and IMP002."""

import ast

from mercury_bot.rules.base import Diagnostic, Rule, Severity

# Modules excluded from IMP001 — they are covered by IMP002 or are special syntax.
_IMP001_EXCLUDED: frozenset[str] = frozenset({"__future__", "typing"})

# Typing modules covered by IMP002.
_TYPING_MODULES: frozenset[str] = frozenset({"typing", "typing_extensions"})


class IMP001(Rule):
    """Flag from-imports that import names (classes/functions) instead of modules.

    Allowed:
        import os
        import os.path

    Flagged:
        from os.path import join
        from collections import OrderedDict
    """

    def check(self, tree: ast.Module, source: str) -> list[Diagnostic]:
        """Return a diagnostic for every non-typing from-import."""
        diagnostics: list[Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = node.module or ""
                if module in _IMP001_EXCLUDED:
                    continue
                names = ", ".join(alias.name for alias in node.names)
                dots = "." * node.level
                module_display = f"{dots}{module}" if module else dots
                diagnostics.append(
                    Diagnostic(
                        rule_id="IMP001",
                        message=(
                            f"Import the module directly instead of importing"
                            f" `{names}` from `{module_display}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=Severity.WARNING,
                    )
                )
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics


class IMP002(Rule):
    """Flag from-imports of typing modules; require `import typing` instead.

    Allowed:
        import typing

    Flagged:
        from typing import Optional
        from typing_extensions import Protocol
    """

    def check(self, tree: ast.Module, source: str) -> list[Diagnostic]:
        """Return a diagnostic for every from-import of a typing module."""
        diagnostics: list[Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module not in _TYPING_MODULES:
                    continue
                names = ", ".join(alias.name for alias in node.names)
                diagnostics.append(
                    Diagnostic(
                        rule_id="IMP002",
                        message=(
                            f"Use `import {node.module}` instead of"
                            f" importing `{names}` from `{node.module}`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=Severity.WARNING,
                    )
                )
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics
