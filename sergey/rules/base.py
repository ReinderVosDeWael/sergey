"""Base abstractions for sergey rules."""

from __future__ import annotations

import abc
import dataclasses
import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ast


class Severity(enum.Enum):
    """LSP diagnostic severity levels."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclasses.dataclass
class TextEdit:
    """A single text replacement at an explicit source location.

    Uses 1-indexed lines and 0-indexed columns, matching Diagnostic.
    """

    line: int
    col: int
    end_line: int
    end_col: int
    replacement: str


@dataclasses.dataclass
class Fix:
    """A text replacement that resolves a diagnostic.

    The replacement covers the range of the parent Diagnostic
    (line, col) → (end_line, end_col), using 1-indexed lines and
    0-indexed columns.

    ``additional_edits`` lists extra replacements elsewhere in the file
    that are part of the same logical fix (e.g. rewriting call-site
    references after changing an import).
    """

    replacement: str
    additional_edits: list[TextEdit] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Diagnostic:
    """A single diagnostic emitted by a rule."""

    rule_id: str
    message: str
    line: int  # 1-indexed
    col: int  # 0-indexed
    end_line: int
    end_col: int
    severity: Severity
    fix: Fix | None = None


class Rule(abc.ABC):
    """Abstract base class for all sergey rules."""

    @abc.abstractmethod
    def check(self, tree: ast.Module, source: str) -> list[Diagnostic]:
        """Analyze the AST and return any diagnostics.

        Args:
            tree: The parsed AST of the source file.
            source: The raw source string (needed for line-count and comment rules).

        Returns:
            A list of Diagnostic instances. Returns an empty list if no issues
            are found or if an internal error occurs.
        """

    def configure(self, options: dict[str, int | str | bool]) -> Rule:
        """Return a new Rule with the given options applied.

        The default implementation ignores *options* and returns *self*.
        Rules that support per-rule configuration should override this method.

        Args:
            options: Mapping of option names to values.

        Returns:
            A Rule instance (possibly new) with options applied.
        """
        return self
