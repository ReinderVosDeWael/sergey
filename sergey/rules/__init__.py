"""All sergey rules."""

from sergey.rules import base, imports, naming

ALL_RULES: list[base.Rule] = [
    imports.IMP001(),
    imports.IMP002(),
    imports.IMP003(),
    naming.NAM002(),
]

__all__ = ["ALL_RULES"]
