"""All sergey rules."""

from sergey.rules import base, docs, imports, naming, pydantic, structure

ALL_RULES: list[base.Rule] = [
    docs.DOC001(),
    imports.IMP001(),
    imports.IMP002(),
    imports.IMP003(),
    imports.IMP004(),
    naming.NAM001(),
    naming.NAM002(),
    naming.NAM003(),
    pydantic.PDT001(),
    pydantic.PDT002(),
    structure.STR002(),
    structure.STR003(),
    structure.STR004(),
]

__all__ = ["ALL_RULES"]
