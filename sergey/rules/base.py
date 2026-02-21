"""Base abstractions for sergey rules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ast


class Severity(Enum):
    """LSP diagnostic severity levels."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass
class Diagnostic:
    """A single diagnostic emitted by a rule."""

    rule_id: str
    message: str
    line: int      # 1-indexed
    col: int       # 0-indexed
    end_line: int
    end_col: int
    severity: Severity


class Rule(ABC):
    """Abstract base class for all sergey rules."""

    @abstractmethod
    def check(self, tree: ast.Module, source: str) -> list[Diagnostic]:
        """Analyze the AST and return any diagnostics.

        Args:
            tree: The parsed AST of the source file.
            source: The raw source string (needed for line-count and comment rules).

        Returns:
            A list of Diagnostic instances. Returns an empty list if no issues
            are found or if an internal error occurs.
        """
