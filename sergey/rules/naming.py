"""Naming rules: NAM002."""

import ast

from sergey.rules import base


class NAM002(base.Rule):
    """Flag single-character variable names as insufficiently descriptive.

    Applies to all variable bindings: assignments, for-loops, comprehensions,
    with-statements, augmented assignments, and walrus expressions.
    The conventional throwaway name `_` is exempt.

    Allowed:
        _ = some_function()     # conventional throwaway
        idx = 0                 # descriptive

    Flagged:
        x = 1
        for i in range(10): ...
        [x for x in items]
        (n := compute())
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every single-character variable binding."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Name):
                    continue
                if not isinstance(node.ctx, ast.Store):
                    continue
                if len(node.id) != 1 or node.id == "_":
                    continue
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="NAM002",
                        message=(
                            f"Variable name `{node.id}` is not descriptive;"
                            f" use a meaningful name"
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
