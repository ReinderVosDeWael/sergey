"""Load sergey configuration from pyproject.toml."""

from __future__ import annotations

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
        rule_options: Per-rule option overrides keyed by rule ID.
    """

    select: frozenset[str] | None
    ignore: frozenset[str]
    rule_options: dict[str, dict[str, int | str | bool]] = dataclasses.field(
        default_factory=dict, hash=False
    )


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
    rules_raw: dict[str, object] = section.get("rules", {})

    select = (
        frozenset(rule_id.upper() for rule_id in select_raw)
        if select_raw is not None
        else None
    )
    ignore = frozenset(rule_id.upper() for rule_id in ignore_raw)
    rule_options: dict[str, dict[str, int | str | bool]] = {
        rule_id.upper(): {
            opt_key: opt_val
            for opt_key, opt_val in opts.items()
            if isinstance(opt_val, int | str | bool)
        }
        for rule_id, opts in rules_raw.items()
        if isinstance(opts, dict)
    }
    return Config(select=select, ignore=ignore, rule_options=rule_options)


def configure_rules(
    active_rules: list[base.Rule],
    config: Config,
) -> list[base.Rule]:
    """Return rules with per-rule options from config applied.

    For each rule whose ID appears in ``config.rule_options``, calls
    ``rule.configure(opts)`` and uses the returned instance.  Rules with no
    matching options are returned unchanged.

    Args:
        active_rules: The filtered list of rules to configure.
        config: The active configuration.

    Returns:
        List of rules with options applied, preserving order.
    """
    result: list[base.Rule] = []
    for rule in active_rules:
        opts = config.rule_options.get(type(rule).__name__, {})
        result.append(rule.configure(opts) if opts else rule)
    return result


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
