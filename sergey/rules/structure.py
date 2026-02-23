"""Structure rules: STR002, STR003, STR004."""

import ast
from collections.abc import Iterator

from sergey.rules import base

_MAX_DEPTH: int = 4

_SCOPE_TYPES: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)

# ast.TryStar (try/except*) was added in Python 3.11.
_TRY_STAR: tuple[type[ast.AST], ...] = (ast.TryStar,) if hasattr(ast, "TryStar") else ()

_OTHER_NESTING: tuple[type[ast.AST], ...] = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
    *_TRY_STAR,
)


def _make_diagnostic(node: ast.stmt, depth: int) -> base.Diagnostic:
    return base.Diagnostic(
        rule_id="STR002",
        message=(
            f"Nesting depth {depth} exceeds the maximum of {_MAX_DEPTH};"
            f" extract logic to reduce nesting"
        ),
        line=node.lineno,
        col=node.col_offset,
        end_line=node.end_lineno or node.lineno,
        end_col=node.end_col_offset or node.col_offset,
        severity=base.Severity.WARNING,
    )


def _dispatch(node: ast.AST, depth: int, diagnostics: list[base.Diagnostic]) -> None:
    """Dispatch a single AST node, tracking control-flow nesting depth."""
    if isinstance(node, _SCOPE_TYPES):
        # Function, class, or lambda bodies reset the depth counter.
        for child in ast.iter_child_nodes(node):
            _dispatch(child, 0, diagnostics)
    elif isinstance(node, ast.If):
        _enter_if(node, depth, diagnostics, is_elif=False)
    elif isinstance(node, _OTHER_NESTING):
        _enter(node, depth, diagnostics)
    else:
        for child in ast.iter_child_nodes(node):
            _dispatch(child, depth, diagnostics)


def _enter(node: ast.AST, depth: int, diagnostics: list[base.Diagnostic]) -> None:
    """Enter a nesting construct, incrementing depth and emitting if over limit."""
    new_depth = depth + 1
    if new_depth > _MAX_DEPTH and depth == _MAX_DEPTH:
        diagnostics.append(_make_diagnostic(node, new_depth))  # type: ignore[arg-type]
    for child in ast.iter_child_nodes(node):
        _dispatch(child, new_depth, diagnostics)


def _enter_if(
    node: ast.If,
    depth: int,
    diagnostics: list[base.Diagnostic],
    *,
    is_elif: bool,
) -> None:
    """Enter an If node, treating elif branches at the same depth as the if.

    This prevents elif chains from being penalised as extra nesting levels.
    Only the leading `if` emits a diagnostic when over the limit.
    """
    new_depth = depth + 1
    if not is_elif and new_depth > _MAX_DEPTH and depth == _MAX_DEPTH:
        diagnostics.append(_make_diagnostic(node, new_depth))

    _dispatch(node.test, new_depth, diagnostics)
    for stmt in node.body:
        _dispatch(stmt, new_depth, diagnostics)

    if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
        # elif: use the same base depth so it counts as the same level.
        _enter_if(node.orelse[0], depth, diagnostics, is_elif=True)
    else:
        for stmt in node.orelse:
            _dispatch(stmt, new_depth, diagnostics)


class STR002(base.Rule):
    """Flag control-flow blocks nested deeper than the maximum allowed depth.

    The nesting constructs counted are: if/elif/else, for, while, with, try,
    and match. elif branches are treated as the same depth as their parent if,
    so an if/elif/else chain only adds one level regardless of the number of
    branches. Function, class, and lambda definitions reset the nesting counter,
    so nested functions are evaluated independently.

    Default maximum depth: 4.

    Allowed:
        def foo():
            for item in items:          # depth 1
                for sub in item.subs:   # depth 2
                    if sub.active:      # depth 3
                        with lock:      # depth 4 — OK

    Flagged:
        def foo():
            for item in items:          # depth 1
                for sub in item.subs:   # depth 2
                    if sub.active:      # depth 3
                        with lock:      # depth 4
                            if flag:    # depth 5 — flagged
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for each block that exceeds the maximum nesting depth."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for child in ast.iter_child_nodes(tree):
                _dispatch(child, 0, diagnostics)
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics


_DEFAULT_MAX_TRY_BODY: int = 4


def _child_stmt_lists(node: ast.AST) -> list[list[ast.stmt]]:
    """Return child statement lists of a compound statement node.

    Used by ``_count_stmts`` to recurse into nested control flow without
    crossing function or class scope boundaries.
    """
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        return [node.body, node.orelse]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [node.body]
    if isinstance(node, ast.Try):
        bodies: list[list[ast.stmt]] = [node.body, node.orelse, node.finalbody]
        bodies.extend(handler.body for handler in node.handlers)
        return bodies
    if hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
        ts_bodies: list[list[ast.stmt]] = [node.body, node.orelse, node.finalbody]
        ts_bodies.extend(handler.body for handler in node.handlers)
        return ts_bodies
    if isinstance(node, ast.Match):
        return [case.body for case in node.cases]
    return []


def _count_stmts(stmts: list[ast.stmt]) -> int:
    """Count statements recursively, not descending into new scopes."""
    total = 0
    for stmt in stmts:
        total += 1
        if isinstance(stmt, _SCOPE_TYPES):
            continue
        for child_list in _child_stmt_lists(stmt):
            total += _count_stmts(child_list)
    return total


class STR003(base.Rule):
    """Flag try blocks whose body contains too many statements.

    A large try body makes it hard to identify which operation can raise.
    Extract logic into helper functions to keep the guarded scope minimal.

    Statements are counted recursively: an ``if`` with three branches
    containing two statements each contributes 7 to the total (1 for the
    ``if`` itself plus 6 for its contents). Nested functions and classes
    reset the count and are not included.

    Only the ``try:`` body is counted — ``except`` and ``finally`` blocks
    are not subject to this rule.

    Default maximum: 4 statements (5 or more is flagged).

    Allowed:
        try:
            result = fetch(url)
        except RequestError:
            handle()

    Flagged (default threshold):
        try:
            for item in items:    # 1 (for) + 4 (body) = 5 — flagged
                a = step_one()
                b = step_two()
                c = step_three()
                d = step_four()
        except Exception:
            pass
    """

    def __init__(self, max_body_stmts: int = _DEFAULT_MAX_TRY_BODY) -> None:
        """Initialise with the maximum allowed number of statements in a try body.

        Args:
            max_body_stmts: Maximum number of statements allowed in the try body
                before a diagnostic is emitted.
        """
        self._max_body_stmts = max_body_stmts

    def configure(self, options: dict[str, int | str | bool]) -> base.Rule:
        """Return a new STR003 with options applied.

        Args:
            options: Recognises ``max_body_stmts`` (int).

        Returns:
            A new STR003 instance with the configured threshold, or self if
            the option is absent or not an integer.
        """
        max_body_stmts = options.get("max_body_stmts", self._max_body_stmts)
        if isinstance(max_body_stmts, int):
            return STR003(max_body_stmts=max_body_stmts)
        return self

    def _check_try_node(self, node: ast.Try) -> list[base.Diagnostic]:
        """Return a diagnostic if *node*'s body exceeds the statement limit."""
        stmt_count = _count_stmts(node.body)
        if stmt_count <= self._max_body_stmts:
            return []
        return [
            base.Diagnostic(
                rule_id="STR003",
                message=(
                    f"try body has {stmt_count} statements"
                    f" (maximum {self._max_body_stmts});"
                    f" extract logic to narrow the guarded scope"
                ),
                line=node.lineno,
                col=node.col_offset,
                end_line=node.end_lineno or node.lineno,
                end_col=node.end_col_offset or node.col_offset,
                severity=base.Severity.WARNING,
            )
        ]

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every try body exceeding the statement limit."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    diagnostics.extend(self._check_try_node(node))
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics


# ---------------------------------------------------------------------------
# STR004 — prefer tuples for unmodified lists
# ---------------------------------------------------------------------------

_LIST_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "sort",
    }
)


def _iter_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield all descendant nodes within the current function scope.

    Does not descend into nested function, class, or lambda definitions.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_TYPES):
            continue
        yield child
        yield from _iter_scope(child)


def _contains_name_ref(node: ast.AST, name: str) -> bool:
    """Return True if *node* contains a reference to *name*."""
    if isinstance(node, ast.Name) and node.id == name:
        return True
    return any(_contains_name_ref(child, name) for child in ast.iter_child_nodes(node))


def _name_used_in_nested_scope(node: ast.AST, name: str) -> bool:
    """Return True if *name* is referenced inside a nested scope under *node*."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_TYPES):
            for inner in ast.walk(child):
                if isinstance(inner, ast.Name) and inner.id == name:
                    return True
        elif _name_used_in_nested_scope(child, name):
            return True
    return False


def _target_has_name(target: ast.AST, name: str) -> bool:
    """Return True if *target* binds *name* (handles tuple/list unpacking)."""
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_has_name(elt, name) for elt in target.elts)
    if isinstance(target, ast.Starred):
        return _target_has_name(target.value, name)
    return False


def _is_list_mutated(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> bool:
    """Return True if the list bound to *name* is mutated in-place."""
    for node in _iter_scope(func):
        # Mutating method calls: name.append(...), name.extend(...), etc.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == name
            and node.func.attr in _LIST_MUTATING_METHODS
        ):
            return True
        # Augmented assignment: name += [...]
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return True
        # Subscript assignment: name[i] = value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == name
                ):
                    return True
        # Subscript deletion: del name[i]
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == name
                ):
                    return True
    return False


def _is_in_function_output(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> bool:
    """Return True if *name* appears in a return or yield expression."""
    for node in _iter_scope(func):
        if (
            isinstance(node, ast.Return)
            and node.value is not None
            and _contains_name_ref(node.value, name)
        ):
            return True
        if (
            isinstance(node, (ast.Yield, ast.YieldFrom))
            and node.value is not None
            and _contains_name_ref(node.value, name)
        ):
            return True
    return False


def _node_binds_name(node: ast.AST, name: str) -> bool:
    """Return True if *node* binds *name* through any form of assignment."""
    if isinstance(node, ast.Assign):
        return any(_target_has_name(target, name) for target in node.targets)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return _target_has_name(node.target, name)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _target_has_name(node.target, name)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return any(
            item.optional_vars is not None
            and _target_has_name(item.optional_vars, name)
            for item in node.items
        )
    if isinstance(node, ast.NamedExpr):
        return node.target.id == name
    return False


def _is_name_rebound(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    creation: ast.stmt,
) -> bool:
    """Return True if *name* is assigned more than once (ignoring *creation*)."""
    return any(
        _node_binds_name(node, name)
        for node in _iter_scope(func)
        if node is not creation
    )


def _has_global_or_nonlocal(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> bool:
    """Return True if *name* is declared ``global`` or ``nonlocal``."""
    for node in _iter_scope(func):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return True
    return False


def _does_list_escape(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> bool:
    """Return True if the list may escape via attribute or subscript storage."""
    for node in _iter_scope(func):
        if not isinstance(node, ast.Assign):
            continue
        if not _contains_name_ref(node.value, name):
            continue
        for target in node.targets:
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                return True
    return False


def _collect_list_assignments(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, ast.stmt]]:
    """Return ``(name, assign_node)`` pairs for list-literal assignments."""
    candidates: list[tuple[str, ast.stmt]] = []
    for node in _iter_scope(func):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.List)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            candidates.append((node.targets[0].id, node))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.value, ast.List)
            and isinstance(node.target, ast.Name)
        ):
            candidates.append((node.target.id, node))
    return candidates


def _should_skip(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    assign_node: ast.stmt,
) -> bool:
    """Return True if the list should *not* be flagged."""
    return (
        _has_global_or_nonlocal(func, name)
        or _is_name_rebound(func, name, assign_node)
        or _is_list_mutated(func, name)
        or _is_in_function_output(func, name)
        or _name_used_in_nested_scope(func, name)
        or _does_list_escape(func, name)
    )


class STR004(base.Rule):
    """Flag list literals in functions that are never modified and not returned.

    When a list is created inside a function body and is never mutated
    (via ``append``, ``extend``, ``insert``, ``pop``, ``remove``, ``clear``,
    ``sort``, ``reverse``, augmented assignment, or item assignment/deletion)
    and is not part of the function output (``return`` / ``yield``), an
    immutable ``tuple`` should be used instead.

    Only plain list literals (``[...]``) are checked; ``list()`` calls and
    list comprehensions are not covered.

    Allowed:
        def build():
            items = []
            items.append(1)
            return items

    Flagged:
        def process():
            colors = ["red", "green", "blue"]
            for color in colors:
                print(color)
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for each unmodified list that should be a tuple."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    diagnostics.extend(self._check_function(node))
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics

    def _check_function(
        self,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[base.Diagnostic]:
        """Check a single function for unmodified list literals."""
        candidates = _collect_list_assignments(func)
        diagnostics: list[base.Diagnostic] = []
        for name, assign_node in candidates:
            if _should_skip(func, name, assign_node):
                continue
            diagnostics.append(
                base.Diagnostic(
                    rule_id="STR004",
                    message=(
                        f"List `{name}` is never modified; use a tuple for immutability"
                    ),
                    line=assign_node.lineno,
                    col=assign_node.col_offset,
                    end_line=assign_node.end_lineno or assign_node.lineno,
                    end_col=assign_node.end_col_offset or assign_node.col_offset,
                    severity=base.Severity.WARNING,
                )
            )
        return diagnostics
