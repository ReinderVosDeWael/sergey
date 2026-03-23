"""Documentation rules: DOC001."""

import ast
import re
from typing import Final

from sergey.rules import base

# Scope boundaries: raises inside these nodes belong to a different function.
_NESTED_SCOPE: Final[tuple[type[ast.AST], ...]] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)


def _exc_class_name(exc: ast.expr) -> str | None:
    """Return the exception class name from a raise expression, or None.

    Only names starting with an uppercase letter or attribute access are
    treated as class names; lowercase names are variable re-raises and are
    skipped so they do not produce false positives.
    """
    if isinstance(exc, ast.Call):
        return _exc_class_name(exc.func)
    if isinstance(exc, ast.Attribute):
        return exc.attr
    if isinstance(exc, ast.Name) and exc.id[:1].isupper():
        return exc.id
    return None


def _collect_raises(node: ast.AST) -> list[ast.Raise]:
    """Return all non-bare raise nodes in node, excluding nested scopes.

    Bare ``raise`` (re-raise inside an except block) is exempt.
    Raises inside nested functions or classes belong to those scopes.
    """
    result: list[ast.Raise] = []
    if isinstance(node, ast.Raise):
        if node.exc is not None:
            result.append(node)
        return result
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED_SCOPE):
            continue
        result.extend(_collect_raises(child))
    return result


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


def _raises_section_content(docstring: str) -> str | None:
    """Return the text of the Raises section, or None if absent.

    Recognises Google style (``Raises:``) and NumPy style
    (``Raises`` followed by a line of dashes).  Returns None when no
    Raises section is present so callers can distinguish "absent" from
    "present but empty".
    """
    lines = docstring.splitlines()
    content: list[str] = []
    in_raises = False
    skip_next = False
    raises_indent = 0

    for idx, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if not in_raises:
            if stripped == "Raises:":
                in_raises = True
                raises_indent = indent
            elif stripped == "Raises" and idx + 1 < len(lines):
                nxt = lines[idx + 1].strip()
                if nxt and all(char == "-" for char in nxt):
                    in_raises = True
                    raises_indent = indent
                    skip_next = True
        else:
            if stripped and indent <= raises_indent:
                nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
                if stripped.endswith(":") or (nxt and all(char == "-" for char in nxt)):
                    break
            content.append(stripped)

    return "\n".join(content) if in_raises else None


def _check_doc(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[base.Diagnostic]:
    """Return DOC001 diagnostics for a single function."""
    docstring = _get_docstring(func)
    if docstring is None:
        return []
    raises = _collect_raises(func)
    if not raises:
        return []
    raises_content = _raises_section_content(docstring)
    if raises_content is None:
        return [
            base.Diagnostic(
                rule_id="DOC001",
                message=(
                    f"Function `{func.name}` raises exceptions but its"
                    f" docstring has no `Raises` section"
                ),
                line=func.lineno,
                col=func.col_offset,
                end_line=func.end_lineno or func.lineno,
                end_col=func.end_col_offset or func.col_offset,
                severity=base.Severity.WARNING,
            )
        ]
    diagnostics: list[base.Diagnostic] = []
    seen: set[str] = set()
    for raise_node in raises:
        if raise_node.exc is None:
            continue
        name = _exc_class_name(raise_node.exc)
        if name is None or name in seen:
            continue
        seen.add(name)
        if re.search(r"\b" + re.escape(name) + r"\b", raises_content):
            continue
        diagnostics.append(
            base.Diagnostic(
                rule_id="DOC001",
                message=(
                    f"Function `{func.name}` raises `{name}` but the"
                    f" `Raises` section does not document it"
                ),
                line=raise_node.lineno,
                col=raise_node.col_offset,
                end_line=raise_node.end_lineno or raise_node.lineno,
                end_col=raise_node.end_col_offset or raise_node.col_offset,
                severity=base.Severity.WARNING,
            )
        )
    return diagnostics


class DOC001(base.Rule):
    """Flag functions whose docstring Raises section is absent or incomplete.

    If a function has a docstring and contains explicit ``raise`` statements:

    1. The docstring must include a ``Raises`` section.
    2. Every raised exception class must be named in that section.

    Bare re-raises (``raise`` with no argument) and variable re-raises
    (e.g. ``raise exc``) are exempt.  Raises inside nested functions or
    classes belong to those scopes and do not affect the outer function.
    Functions with no docstring at all are not checked by this rule.

    Both Google style (``Raises:``) and NumPy style (``Raises`` / ``------``)
    headings are accepted.

    Allowed:
        def parse(text: str) -> int:
            # docstring has a Raises section that lists ValueError
            raise ValueError("empty")

    Flagged:
        def parse(text: str) -> int:
            # docstring exists but has no Raises section at all
            raise ValueError("empty")

        def parse(text: str) -> int:
            # docstring has a Raises section, but ValueError is not listed
            raise ValueError("empty")
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return diagnostics for functions with incomplete Raises documentation."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    diagnostics.extend(_check_doc(node))
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics
