"""Load sergey configuration from pyproject.toml."""

import dataclasses
import pathlib
import tomllib
import typing

if typing.TYPE_CHECKING:
    from sergey.rules import base


@dataclasses.dataclass(frozen=True)
class Config:
    """Resolved sergey configuration.

    Attributes:
        select: Rule IDs to run. ``None`` means all registered rules are active.
        ignore: Rule IDs to exclude from the active set.
    """

    select: frozenset[str] | None
    ignore: frozenset[str]


def _find_pyproject(start: pathlib.Path) -> pathlib.Path | None:
    """Walk up from *start* to find the nearest pyproject.toml."""
    for directory in [start, *start.parents]:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_config(start: pathlib.Path | None = None) -> Config:
    """Return the Config from the nearest pyproject.toml, or defaults.

    Reads ``[tool.sergey]`` from the first ``pyproject.toml`` found by
    walking up from *start* (defaults to ``Path.cwd()``).  Returns a
    default Config (all rules active, none ignored) if no file is found
    or the section is absent.

    Args:
        start: Directory to begin the upward search.  Defaults to cwd.

    Returns:
        A Config reflecting the ``select`` and ``ignore`` lists, if present.
    """
    search_root = start if start is not None else pathlib.Path.cwd()
    pyproject = _find_pyproject(search_root)
    if pyproject is None:
        return Config(select=None, ignore=frozenset())

    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return Config(select=None, ignore=frozenset())

    section = data.get("tool", {}).get("sergey", {})
    select_raw: list[str] | None = section.get("select")
    ignore_raw: list[str] = section.get("ignore", [])

    select = (
        frozenset(rule_id.upper() for rule_id in select_raw)
        if select_raw is not None
        else None
    )
    ignore = frozenset(rule_id.upper() for rule_id in ignore_raw)
    return Config(select=select, ignore=ignore)


def filter_rules(
    all_rules: list[base.Rule],
    config: Config,
) -> list[base.Rule]:
    """Return the subset of *all_rules* allowed by *config*.

    ``select`` is applied first (restricting to that set), then ``ignore``
    removes any listed IDs.  Rule identity is determined by the class name,
    which matches the rule ID (e.g. ``PDT001``).

    Args:
        all_rules: Full list of available rule instances.
        config: The active configuration.

    Returns:
        Filtered list preserving the original order.
    """
    active = all_rules
    if config.select is not None:
        active = [rule for rule in active if type(rule).__name__ in config.select]
    if config.ignore:
        active = [rule for rule in active if type(rule).__name__ not in config.ignore]
    return active
