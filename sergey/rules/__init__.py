"""All sergey rules."""

from sergey.rules.base import Diagnostic, Rule, Severity
from sergey.rules.imports import IMP001, IMP002

ALL_RULES: list[Rule] = [
    IMP001(),
    IMP002(),
]

__all__ = ["ALL_RULES", "IMP001", "IMP002", "Diagnostic", "Rule", "Severity"]
