"""Orchestrates rule execution against a parsed AST."""

import ast
import re
import typing

if typing.TYPE_CHECKING:
    from sergey.rules import base

# Matches:  # sergey: noqa          (suppress all rules on this line)
#           # sergey: noqa: IMP001  (suppress specific rules on this line)
_LINE_NOQA_PAT = re.compile(
    r"#\s*sergey:\s*noqa(?::\s*([A-Z0-9][A-Z0-9,\s]*))?",
    re.IGNORECASE,
)

# Matches:  # sergey: disable-file           (suppress all rules in this file)
#           # sergey: disable-file: IMP001   (suppress specific rules in this file)
_FILE_DISABLE_PAT = re.compile(
    r"#\s*sergey:\s*disable-file(?::\s*([A-Z0-9][A-Z0-9,\s]*))?",
    re.IGNORECASE,
)


def _rule_ids(raw: str | None) -> frozenset[str] | None:
    """Parse rule IDs from a suppression comment capture group.

    Returns None to indicate all rules are suppressed, or a frozenset of
    specific uppercased rule IDs.
    """
    if not raw or not raw.strip():
        return None
    ids = frozenset(part.strip().upper() for part in raw.split(",") if part.strip())
    return ids or None


def _covers(suppressed: frozenset[str] | None, rule_id: str) -> bool:
    """Return True if rule_id falls within the suppression set.

    None means all rules are suppressed.
    """
    return suppressed is None or rule_id in suppressed


def _apply_suppressions(
    diagnostics: list[base.Diagnostic],
    source: str,
) -> list[base.Diagnostic]:
    """Remove diagnostics covered by inline sergey suppression comments."""
    lines = source.splitlines()

    file_sup_active = False
    file_sup_rules: frozenset[str] | None = None
    line_sups: dict[int, frozenset[str] | None] = {}

    for lineno, line_text in enumerate(lines, start=1):
        file_match = _FILE_DISABLE_PAT.search(line_text)
        if file_match:
            file_sup_active = True
            file_sup_rules = _rule_ids(file_match.group(1))

        line_match = _LINE_NOQA_PAT.search(line_text)
        if line_match:
            line_sups[lineno] = _rule_ids(line_match.group(1))

    return [
        diag
        for diag in diagnostics
        if not (
            (file_sup_active and _covers(file_sup_rules, diag.rule_id))
            or (diag.line in line_sups and _covers(line_sups[diag.line], diag.rule_id))
        )
    ]


class Analyzer:
    """Runs all registered rules against a source file."""

    def __init__(self, rules: list[base.Rule]) -> None:
        """Initialize with a list of rule instances.

        Args:
            rules: Rule instances to run on every analysis request.
        """
        self.rules = rules

    def analyze(self, source: str) -> list[base.Diagnostic]:
        """Parse source, run all rules, and apply inline suppressions.

        Args:
            source: Raw Python source code to analyze.

        Returns:
            Diagnostics sorted by (line, col) with suppressed entries removed.
            Returns an empty list if the source cannot be parsed.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        diagnostics = sorted(
            [diag for rule in self.rules for diag in rule.check(tree, source)],
            key=lambda diag: (diag.line, diag.col),
        )
        return _apply_suppressions(diagnostics, source)
