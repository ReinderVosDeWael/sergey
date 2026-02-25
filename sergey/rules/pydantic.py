"""Pydantic rules: PDT001, PDT002."""

import ast

from sergey.rules import base


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    """Return True if the class appears to subclass pydantic BaseModel."""
    for base_node in node.bases:
        if isinstance(base_node, ast.Name) and base_node.id == "BaseModel":
            return True
        if isinstance(base_node, ast.Attribute) and base_node.attr == "BaseModel":
            return True
    return False


def _find_model_config(node: ast.ClassDef) -> ast.expr | None:
    """Return the assigned value of model_config in the class body, or None."""
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "model_config":
                    return stmt.value
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "model_config"
        ):
            return stmt.value  # None if declared without assignment
    return None


def _is_config_dict_call(node: ast.expr) -> bool:
    """Return True if the expression is a ConfigDict(...) call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "ConfigDict") or (
        isinstance(func, ast.Attribute) and func.attr == "ConfigDict"
    )


def _has_frozen_kwarg(call: ast.Call) -> bool:
    """Return True if the call includes a `frozen` keyword argument."""
    return any(kw.arg == "frozen" for kw in call.keywords)


def _is_frozen_true(call: ast.Call) -> bool:
    """Return True if the ConfigDict call has `frozen=True`."""
    for kw in call.keywords:
        if kw.arg == "frozen":
            return isinstance(kw.value, ast.Constant) and kw.value.value is True
    return False


def _is_class_var(annotation: ast.expr) -> bool:
    """Return True if the annotation is or wraps ClassVar."""
    if isinstance(annotation, ast.Name):
        return annotation.id == "ClassVar"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "ClassVar"
    if isinstance(annotation, ast.Subscript):
        return _is_class_var(annotation.value)
    return False


#: Type names that are mutable and therefore disallowed on frozen models.
_MUTABLE_TYPES: frozenset[str] = frozenset(
    {
        # builtins
        "list",
        "dict",
        "set",
        "bytearray",
        # typing / typing_extensions capitalized aliases
        "List",
        "Dict",
        "Set",
        "Deque",
        "DefaultDict",
        "OrderedDict",
        # collections
        "deque",
        "Counter",
        "defaultdict",
        # collections.abc explicitly-mutable ABCs
        "MutableSequence",
        "MutableMapping",
        "MutableSet",
    }
)


def _mutable_types_in(annotation: ast.expr) -> list[str]:
    """Return names of mutable types found anywhere in *annotation*.

    Recurses into generic arguments, union syntax (``X | Y``), and
    ``Annotated`` / ``Optional`` wrappers so that e.g.
    ``Optional[list[str]]`` is still flagged.
    """
    if isinstance(annotation, ast.Name):
        return [annotation.id] if annotation.id in _MUTABLE_TYPES else []
    if isinstance(annotation, ast.Attribute):
        return [annotation.attr] if annotation.attr in _MUTABLE_TYPES else []
    if isinstance(annotation, ast.Subscript):
        return _mutable_types_in(annotation.value) + _mutable_types_in(annotation.slice)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _mutable_types_in(annotation.left) + _mutable_types_in(annotation.right)
    if isinstance(annotation, ast.Tuple):
        found: list[str] = []
        for elt in annotation.elts:
            found.extend(_mutable_types_in(elt))
        return found
    return []


class PDT001(base.Rule):
    """Flag Pydantic BaseModel subclasses without an explicit `frozen` setting.

    Every model must have `model_config = ConfigDict(frozen=...)` with `frozen`
    explicitly set. This forces a deliberate decision about mutability rather
    than relying on Pydantic's mutable default.

    Allowed:
        class User(BaseModel):
            model_config = ConfigDict(frozen=True)
            name: str

        class Draft(BaseModel):
            model_config = ConfigDict(frozen=False, validate_assignment=True)
            body: str

    Flagged:
        class User(BaseModel):              # no model_config at all
            name: str

        class User(BaseModel):              # frozen not set
            model_config = ConfigDict()
            name: str
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every Pydantic model missing a frozen setting."""
        diagnostics: list[base.Diagnostic] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not _is_pydantic_model(node):
                continue

            config_value = _find_model_config(node)

            if config_value is None:
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="PDT001",
                        message=(
                            f"Pydantic model `{node.name}` has no `model_config`;"
                            f" add `model_config = ConfigDict(frozen=...)`"
                        ),
                        line=node.lineno,
                        col=node.col_offset,
                        end_line=node.end_lineno or node.lineno,
                        end_col=node.end_col_offset or node.col_offset,
                        severity=base.Severity.WARNING,
                    )
                )
            elif not _is_config_dict_call(config_value):
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="PDT001",
                        message=(
                            f"Pydantic model `{node.name}` `model_config` is not a"
                            f" `ConfigDict(...)` call;"
                            f" use `model_config = ConfigDict(frozen=...)`"
                        ),
                        line=config_value.lineno,
                        col=config_value.col_offset,
                        end_line=config_value.end_lineno or config_value.lineno,
                        end_col=(
                            config_value.end_col_offset or config_value.col_offset
                        ),
                        severity=base.Severity.WARNING,
                    )
                )
            elif isinstance(config_value, ast.Call) and not _has_frozen_kwarg(
                config_value
            ):
                diagnostics.append(
                    base.Diagnostic(
                        rule_id="PDT001",
                        message=(
                            f"Pydantic model `{node.name}` `model_config` does not"
                            f" set `frozen`; add `frozen=True` or `frozen=False`"
                            f" explicitly"
                        ),
                        line=config_value.lineno,
                        col=config_value.col_offset,
                        end_line=config_value.end_lineno or config_value.lineno,
                        end_col=(
                            config_value.end_col_offset or config_value.col_offset
                        ),
                        severity=base.Severity.WARNING,
                    )
                )
        return diagnostics


def _check_frozen_field(
    model_name: str,
    stmt: ast.AnnAssign,
) -> base.Diagnostic | None:
    """Return a PDT002 diagnostic if stmt uses a mutable type, else None."""
    if not isinstance(stmt.target, ast.Name) or stmt.target.id == "model_config":
        return None
    if stmt.annotation is None or _is_class_var(stmt.annotation):
        return None
    mutable = _mutable_types_in(stmt.annotation)
    if not mutable:
        return None
    ann = stmt.annotation
    return base.Diagnostic(
        rule_id="PDT002",
        message=(
            f"Frozen model `{model_name}` field"
            f" `{stmt.target.id}` uses mutable type"
            f" `{mutable[0]}`; use an immutable alternative"
            f" (e.g. `tuple` instead of `list`,"
            f" `frozenset` instead of `set`)"
        ),
        line=ann.lineno,
        col=ann.col_offset,
        end_line=ann.end_lineno or ann.lineno,
        end_col=ann.end_col_offset or ann.col_offset,
        severity=base.Severity.WARNING,
    )


def _check_frozen_model(node: ast.ClassDef) -> list[base.Diagnostic]:
    """Return PDT002 diagnostics for all mutable fields on a single frozen model."""
    config_value = _find_model_config(node)
    if not (
        config_value is not None
        and _is_config_dict_call(config_value)
        and isinstance(config_value, ast.Call)
        and _is_frozen_true(config_value)
    ):
        return []
    diagnostics: list[base.Diagnostic] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        diag = _check_frozen_field(node.name, stmt)
        if diag is not None:
            diagnostics.append(diag)
    return diagnostics


class PDT002(base.Rule):
    """Flag mutable field types on frozen Pydantic models.

    When ``frozen=True``, every field annotation must use only immutable
    types. Mutable containers like ``list``, ``dict``, and ``set`` violate
    the immutability contract and should be replaced with their immutable
    counterparts (``tuple``, ``frozenset``, a read-only mapping, etc.).

    The check recurses into generic parameters and union syntax, so
    ``Optional[list[str]]`` and ``str | list[int]`` are both caught.
    ``ClassVar`` annotations are skipped because they are not model fields.

    Allowed:
        class Point(BaseModel):
            model_config = ConfigDict(frozen=True)
            coords: tuple[float, float]
            tags: frozenset[str]

    Flagged:
        class Point(BaseModel):
            model_config = ConfigDict(frozen=True)
            coords: list[float]      # mutable
            meta: dict[str, int]     # mutable
    """

    def check(self, tree: ast.Module, source: str) -> list[base.Diagnostic]:
        """Return a diagnostic for every mutable field on a frozen model."""
        diagnostics: list[base.Diagnostic] = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and _is_pydantic_model(node):
                    diagnostics.extend(_check_frozen_model(node))
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics
