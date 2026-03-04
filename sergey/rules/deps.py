"""Dependency-aware rules: IMP005."""

from __future__ import annotations

import ast
import contextlib
import functools
import pathlib
import re
import tomllib
import typing

from sergey.rules import base

# ast.TryStar (try/except*) was added in Python 3.11.
_TRY_STAR_TYPE: tuple[type[ast.AST], ...] = (
    (ast.TryStar,) if hasattr(ast, "TryStar") else ()
)

_SCOPE_TYPES: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


def _find_pyproject(start: pathlib.Path) -> pathlib.Path | None:
    """Walk up from *start* to find the nearest pyproject.toml."""
    for directory in [start, *start.parents]:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _parse_dep_name(dep_spec: str) -> str:
    """Extract and normalise the package name from a PEP 508 dependency spec.

    Strips extras, version specifiers, and environment markers, then
    lowercases and replaces hyphens with underscores so the result can be
    compared directly against import names.

    Args:
        dep_spec: A raw dependency string such as ``"numpy>=1.0"``,
            ``"my-pkg[extra]; python_version>'3.8'"``.

    Returns:
        Normalised package name, e.g. ``"my_pkg"``.
    """
    # Strip extras: "package[extra]" → "package"
    name = dep_spec.split("[", maxsplit=1)[0]
    # Strip version specifiers, environment markers, and URL markers
    name = re.split(r"[><=!;~\s@]", name)[0]
    return name.strip().lower().replace("-", "_")


def _collect_dep_names(section: dict[str, object]) -> set[str]:
    """Collect normalised package names from a ``{group: [dep, ...]}`` mapping.

    Args:
        section: A mapping of group names to lists of dependency strings.

    Returns:
        Set of normalised package names found across all groups.
    """
    names: set[str] = set()
    for group_deps in section.values():
        if not isinstance(group_deps, list):
            continue
        for dep in group_deps:
            if isinstance(dep, str):
                names.add(_parse_dep_name(dep))
    return names


@functools.lru_cache(maxsize=32)
def _load_optional_deps(pyproject: pathlib.Path) -> frozenset[str]:
    """Return normalised optional dependency names from *pyproject*.

    Sources (both are checked):

    * ``[project.optional-dependencies]`` — PEP 621 extras; all groups
      are included.
    * ``[dependency-groups]`` — PEP 735 / uv groups; all groups *except*
      ``dev`` are included, as ``dev`` typically contains development-only
      tooling that is not an optional runtime dependency.

    Args:
        pyproject: Absolute path to a ``pyproject.toml`` file.

    Returns:
        Frozenset of normalised package names, or an empty frozenset if
        the file cannot be read or contains no optional dependencies.
    """
    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return frozenset()

    names: set[str] = set()

    # [project.optional-dependencies] — all groups
    opt_deps: dict[str, object] = data.get("project", {}).get(
        "optional-dependencies", {}
    )
    names.update(_collect_dep_names(opt_deps))

    # [dependency-groups] — all groups except "dev"
    dep_groups: dict[str, object] = data.get("dependency-groups", {})
    non_dev_groups: dict[str, object] = {
        group: deps for group, deps in dep_groups.items() if group != "dev"
    }
    names.update(_collect_dep_names(non_dev_groups))

    return frozenset(names)


def _discover_optional_deps() -> frozenset[str]:
    """Find and return optional deps from the nearest ``pyproject.toml``.

    Searches upward from the current working directory.

    Returns:
        Frozenset of normalised package names, or an empty frozenset when
        no ``pyproject.toml`` is found.
    """
    pyproject = _find_pyproject(pathlib.Path.cwd())
    if pyproject is None:
        return frozenset()
    return _load_optional_deps(pyproject)


def _visit_try_like(
    body: list[ast.stmt],
    handlers: list[ast.ExceptHandler],
    orelse: list[ast.stmt],
    finalbody: list[ast.stmt],
    *,
    protected: set[int],
) -> None:
    """Visit a try-like node, marking only the *body* stmts as protected.

    Args:
        body: Statements in the ``try:`` body (will be visited as protected).
        handlers: Exception handler nodes (visited as unprotected).
        orelse: ``else:`` block statements (visited as unprotected).
        finalbody: ``finally:`` block statements (visited as unprotected).
        protected: Accumulator for protected import node ids.
    """
    for stmt in body:
        _visit(stmt, in_try_body=True, protected=protected)
    for handler in handlers:
        for stmt in handler.body:
            _visit(stmt, in_try_body=False, protected=protected)
    for stmt in orelse:
        _visit(stmt, in_try_body=False, protected=protected)
    for stmt in finalbody:
        _visit(stmt, in_try_body=False, protected=protected)


def _visit(node: ast.AST, *, in_try_body: bool, protected: set[int]) -> None:
    """Recursive visitor that marks try-body import nodes as protected.

    Traversal stops at :data:`_SCOPE_TYPES` boundaries (function, class,
    lambda definitions), each of which resets the *in_try_body* flag.

    Args:
        node: Current AST node being visited.
        in_try_body: Whether *node* is directly inside a try body.
        protected: Accumulator for protected import node ids.
    """
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if in_try_body:
            protected.add(id(node))
        return

    if isinstance(node, _SCOPE_TYPES):
        for child in ast.iter_child_nodes(node):
            _visit(child, in_try_body=False, protected=protected)
        return

    if isinstance(node, ast.Try):
        _visit_try_like(
            node.body,
            [h for h in node.handlers if isinstance(h, ast.ExceptHandler)],
            node.orelse,
            node.finalbody,
            protected=protected,
        )
        return

    if _TRY_STAR_TYPE and isinstance(node, _TRY_STAR_TYPE):
        try_star = typing.cast("ast.TryStar", node)
        _visit_try_like(
            try_star.body, try_star.handlers, try_star.orelse, try_star.finalbody,
            protected=protected,
        )
        return

    for child in ast.iter_child_nodes(node):
        _visit(child, in_try_body=in_try_body, protected=protected)


def _top_level_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Return the top-level package names referenced by *node*.

    For ``import a.b, c`` returns ``["a", "c"]``.
    For ``from pkg.sub import x`` returns ``["pkg"]``.
    For relative imports (``from . import x``) returns ``[]``.

    Args:
        node: An :class:`ast.Import` or :class:`ast.ImportFrom` node.

    Returns:
        List of top-level package name strings (may contain duplicates when
        multiple aliases share a root, e.g. ``import numpy.linalg, numpy.random``).
    """
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    # ImportFrom
    if node.level > 0 or not node.module:
        return []
    return [node.module.split(".")[0]]


class IMP005(base.Rule):
    """Flag imports of optional dependencies not guarded by try/except.

    Optional dependencies — packages listed under
    ``[project.optional-dependencies]`` or in any non-``dev``
    ``[dependency-groups]`` group of the nearest ``pyproject.toml`` — may not
    be installed in every environment.  Importing them without a
    ``try/except ImportError`` guard will raise an :class:`ImportError` for
    users who did not install that extra.

    The ``dev`` group in ``[dependency-groups]`` is intentionally excluded
    because it typically contains development tooling that is not a runtime
    concern.

    Allowed:
        try:
            import numpy as np
            HAS_NUMPY = True
        except ImportError:
            HAS_NUMPY = False

    Flagged:
        import numpy          # optional dep, no guard
        from pandas import DataFrame  # optional dep, no guard
    """

    def __init__(self, optional_deps: frozenset[str] | None = None) -> None:
        """Initialise with an explicit set of optional dependency names.

        Args:
            optional_deps: Pre-computed set of normalised package names.
                When ``None`` (the default) the rule discovers them from the
                nearest ``pyproject.toml`` at check time.
        """
        self._optional_deps = optional_deps

    def _get_optional_deps(self) -> frozenset[str]:
        if self._optional_deps is not None:
            return self._optional_deps
        return _discover_optional_deps()

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for each unguarded optional-dependency import."""
        optional_deps = self._get_optional_deps()
        if not optional_deps:
            return []

        protected: set[int] = set()
        with contextlib.suppress(Exception):
            _visit(tree, in_try_body=False, protected=protected)

        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if id(node) in protected:
                continue

            names = _top_level_names(node)
            # Deduplicate while preserving order (e.g. import numpy.a, numpy.b)
            seen: dict[str, None] = {}
            for name in names:
                seen[name] = None
            optional_names = [
                name
                for name in seen
                if name.lower().replace("-", "_") in optional_deps
            ]
            if not optional_names:
                continue

            name_str = ", ".join(f"`{n}`" for n in optional_names)
            noun = "dependency" if len(optional_names) == 1 else "dependencies"
            diagnostics.append(
                base.Diagnostic(
                    rule_id="IMP005",
                    message=(
                        f"{name_str} is an optional {noun};"
                        f" guard this import with try/except ImportError"
                    ),
                    line=node.lineno,
                    col=node.col_offset,
                    end_line=node.end_lineno or node.lineno,
                    end_col=node.end_col_offset or node.col_offset,
                    severity=base.Severity.WARNING,
                )
            )
        return diagnostics
