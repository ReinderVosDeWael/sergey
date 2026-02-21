"""Orchestrates rule execution against a parsed AST."""

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mercury_bot.rules.base import Diagnostic, Rule


class Analyzer:
    """Runs all registered rules against a source file."""

    def __init__(self, rules: list[Rule]) -> None:
        """Initialize with a list of rule instances.

        Args:
            rules: Rule instances to run on every analysis request.
        """
        self.rules = rules

    def analyze(self, source: str) -> list[Diagnostic]:
        """Parse source and run all rules, returning sorted diagnostics.

        Args:
            source: Raw Python source code to analyze.

        Returns:
            All diagnostics from all rules, sorted by (line, col).
            Returns an empty list if the source cannot be parsed.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        return sorted(
            [d for rule in self.rules for d in rule.check(tree, source)],
            key=lambda d: (d.line, d.col),
        )
