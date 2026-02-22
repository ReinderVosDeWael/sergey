"""Pydantic rules: PDT001."""

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
        try:
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
                elif (
                    isinstance(config_value, ast.Call)
                    and not _has_frozen_kwarg(config_value)
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
        except Exception:  # noqa: BLE001, S110
            pass
        return diagnostics
