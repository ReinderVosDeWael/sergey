"""All mercury-bot rules."""

from mercury_bot.rules.base import Diagnostic, Rule, Severity
from mercury_bot.rules.imports import IMP001, IMP002

ALL_RULES: list[Rule] = [
    IMP001(),
    IMP002(),
]

__all__ = ["ALL_RULES", "IMP001", "IMP002", "Diagnostic", "Rule", "Severity"]
