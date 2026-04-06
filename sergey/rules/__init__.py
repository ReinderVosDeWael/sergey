"""All sergey rules."""

from typing import Final

from sergey.rules import base, docs, imports, naming, pydantic, structure

ALL_RULES: Final[tuple[base.Rule, ...]] = (
    docs.DOC001(),
    imports.IMP001(),
    imports.IMP002(),
    imports.IMP003(),
    imports.IMP004(),
    imports.IMP005(),
    naming.NAM001(),
    naming.NAM002(),
    naming.NAM003(),
    pydantic.PDT001(),
    pydantic.PDT002(),
    pydantic.PDT003(),
    structure.STR002(),
    structure.STR003(),
    structure.STR004(),
    structure.STR005(),
    structure.STR006(),
    structure.STR007(),
)

__all__ = ["ALL_RULES"]
