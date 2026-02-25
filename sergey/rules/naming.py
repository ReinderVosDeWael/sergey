"""Naming rules: NAM001, NAM002, NAM003."""

import ast

from sergey.rules import base

_PREDICATE_PREFIXES: frozenset[str] = frozenset(
    {"is_", "has_", "can_", "should_", "will_", "did_", "was_"}
)


class NAM001(base.Rule):
    """Flag bool-returning functions whose names lack a predicate prefix.

    Functions annotated `-> bool` should be named with a predicate prefix
    (is_, has_, can_, should_, will_, did_, was_) so the caller can tell at a
    glance that the function is a question, not an action. Dunder methods are
    exempt because their names are fixed by the data model.

    Allowed:
        def is_valid(self) -> bool: ...
        def has_permission(user: User) -> bool: ...
        def __eq__(self, other: object) -> bool: ...  # dunder exempt

    Flagged:
        def check(self) -> bool: ...
        def validate(item: Item) -> bool: ...
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Flag bool-returning functions whose names lack a predicate prefix."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if name.startswith("__") and name.endswith("__"):
                continue
            if not isinstance(node.returns, ast.Name) or node.returns.id != "bool":
                continue
            # Strip leading underscores so private helpers like `_is_valid`
            # are treated the same as their public equivalents.
            public_name = name.lstrip("_")
            if any(public_name.startswith(prefix) for prefix in _PREDICATE_PREFIXES):
                continue
            prefixes = ", ".join(sorted(_PREDICATE_PREFIXES))
            diagnostics.append(
                base.Diagnostic(
                    rule_id="NAM001",
                    message=(
                        f"Function `{name}` returns `bool` but its name does not"
                        f" start with a predicate prefix ({prefixes})"
                    ),
                    line=node.lineno,
                    col=node.col_offset,
                    end_line=node.end_lineno or node.lineno,
                    end_col=node.end_col_offset or node.col_offset,
                    severity=base.Severity.WARNING,
                )
            )
        return diagnostics


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
        return diagnostics


class NAM003(base.Rule):
    """Flag single-character function and method parameter names.

    Extends NAM002 to function parameters (`ast.arg` nodes). The conventional
    throwaway name `_` is exempt. Variadic parameters (`*args`, `**kwargs`)
    are also exempt. Lambda parameters are not checked.

    Allowed:
        def process(value: int, count: int) -> None: ...
        def apply(_, transform: Callable) -> None: ...  # _ is exempt

    Flagged:
        def process(x: int, y: int) -> None: ...
        def apply(f: Callable, n: int) -> None: ...
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every single-character parameter name."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            checked = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            diagnostics.extend(
                base.Diagnostic(
                    rule_id="NAM003",
                    message=(
                        f"Parameter name `{arg.arg}` is not descriptive;"
                        f" use a meaningful name"
                    ),
                    line=arg.lineno,
                    col=arg.col_offset,
                    end_line=arg.end_lineno or arg.lineno,
                    end_col=arg.end_col_offset or arg.col_offset,
                    severity=base.Severity.WARNING,
                )
                for arg in checked
                if len(arg.arg) == 1 and arg.arg != "_"
            )
        return diagnostics
