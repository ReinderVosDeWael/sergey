"""Documentation rules: DOC001."""

import ast

from sergey.rules import base

# Scope boundaries: raises inside these nodes belong to a different function.
_NESTED_SCOPE: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)


def _has_explicit_raise(node: ast.AST) -> bool:
    """Return True if node contains a non-bare raise outside nested scopes.

    Bare ``raise`` (re-raise inside an except block) is exempt because it
    propagates an already-caught exception rather than introducing a new one.
    Raises inside nested functions or classes belong to those scopes and are
    not counted.
    """
    if isinstance(node, ast.Raise):
        return node.exc is not None
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED_SCOPE):
            continue
        if _has_explicit_raise(child):
            return True
    return False


def _get_docstring(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    """Return the docstring of func, or None if it has none."""
    if (
        func.body
        and isinstance(func.body[0], ast.Expr)
        and isinstance(func.body[0].value, ast.Constant)
        and isinstance(func.body[0].value.value, str)
    ):
        return func.body[0].value.value
    return None


def _has_raises_section(docstring: str) -> bool:
    """Return True if the docstring contains a Raises section.

    Recognises Google style (``Raises:``) and NumPy style
    (``Raises`` followed by a line of dashes).
    """
    lines = docstring.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Raises:":
            return True
        if stripped == "Raises" and idx + 1 < len(lines):
            next_stripped = lines[idx + 1].strip()
            if next_stripped and all(char == "-" for char in next_stripped):
                return True
    return False


class DOC001(base.Rule):
    """Flag functions that raise without a Raises section in the docstring.

    If a function has a docstring and contains explicit ``raise`` statements,
    the docstring must include a Raises section. Bare re-raises (``raise``
    with no argument) are exempt. Raises inside nested functions or classes
    belong to those scopes and do not affect the outer function. Functions
    with no docstring at all are not checked by this rule.

    Both Google style (``Raises:``) and NumPy style (``Raises`` / ``------``)
    headings are accepted.

    Allowed:
        def parse(text: str) -> int:
            # docstring contains a Raises section
            ...

    Flagged:
        def parse(text: str) -> int:
            # docstring exists but has no Raises section
            ...
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for each function missing a Raises section."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            docstring = _get_docstring(node)
            if docstring is None:
                continue
            if not _has_explicit_raise(node):
                continue
            if _has_raises_section(docstring):
                continue
            diagnostics.append(
                base.Diagnostic(
                    rule_id="DOC001",
                    message=(
                        f"Function `{node.name}` raises exceptions but its"
                        f" docstring has no `Raises` section"
                    ),
                    line=node.lineno,
                    col=node.col_offset,
                    end_line=node.end_lineno or node.lineno,
                    end_col=node.end_col_offset or node.col_offset,
                    severity=base.Severity.WARNING,
                )
            )
        return diagnostics
