"""Tests for sergey.config: load_config and filter_rules."""

import pathlib

from sergey import analyzer as sergey_analyzer
from sergey import config as sergey_config
from sergey.rules import imports, naming, pydantic, structure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_RULES = [imports.IMP001(), imports.IMP002(), pydantic.PDT001()]


def _ids(rule_list: list) -> list[str]:
    return [type(rule).__name__ for rule in rule_list]


# ---------------------------------------------------------------------------
# load_config — no pyproject.toml
# ---------------------------------------------------------------------------


class TestLoadConfigMissing:
    def test_no_pyproject_returns_defaults(self, tmp_path: pathlib.Path) -> None:
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select is None
        assert cfg.ignore == frozenset()

    def test_default_config_is_frozen(self, tmp_path: pathlib.Path) -> None:
        cfg = sergey_config.load_config(tmp_path)
        assert isinstance(cfg, sergey_config.Config)

    def test_finds_pyproject_in_parent(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.sergey]\nignore = [\"IMP001\"]\n"
        )
        child = tmp_path / "sub" / "pkg"
        child.mkdir(parents=True)
        cfg = sergey_config.load_config(child)
        assert "IMP001" in cfg.ignore

    def test_invalid_toml_returns_defaults(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text("this is not : valid toml ][")
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select is None
        assert cfg.ignore == frozenset()


# ---------------------------------------------------------------------------
# load_config — pyproject.toml without [tool.sergey]
# ---------------------------------------------------------------------------


class TestLoadConfigNoSection:
    def test_no_tool_sergey_returns_defaults(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select is None
        assert cfg.ignore == frozenset()


# ---------------------------------------------------------------------------
# load_config — select
# ---------------------------------------------------------------------------


class TestLoadConfigSelect:
    def test_select_single_rule(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nselect = ["IMP001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select == frozenset({"IMP001"})
        assert cfg.ignore == frozenset()

    def test_select_multiple_rules(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nselect = ["IMP001", "PDT001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select == frozenset({"IMP001", "PDT001"})

    def test_select_normalised_to_uppercase(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nselect = ["imp001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select == frozenset({"IMP001"})


# ---------------------------------------------------------------------------
# load_config — ignore
# ---------------------------------------------------------------------------


class TestLoadConfigIgnore:
    def test_ignore_single_rule(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nignore = ["PDT001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select is None
        assert cfg.ignore == frozenset({"PDT001"})

    def test_ignore_normalised_to_uppercase(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nignore = ["pdt001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert "PDT001" in cfg.ignore

    def test_select_and_ignore_together(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sergey]\nselect = ["IMP001", "IMP002"]\nignore = ["IMP001"]\n'
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.select == frozenset({"IMP001", "IMP002"})
        assert cfg.ignore == frozenset({"IMP001"})


# ---------------------------------------------------------------------------
# filter_rules
# ---------------------------------------------------------------------------


class TestFilterRules:
    def test_no_select_no_ignore_returns_all(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset())
        assert _ids(sergey_config.filter_rules(_SAMPLE_RULES, cfg)) == _ids(
            _SAMPLE_RULES
        )

    def test_select_restricts_to_listed_rules(self) -> None:
        cfg = sergey_config.Config(select=frozenset({"IMP001"}), ignore=frozenset())
        result = sergey_config.filter_rules(_SAMPLE_RULES, cfg)
        assert _ids(result) == ["IMP001"]

    def test_select_multiple(self) -> None:
        cfg = sergey_config.Config(
            select=frozenset({"IMP001", "PDT001"}), ignore=frozenset()
        )
        result = sergey_config.filter_rules(_SAMPLE_RULES, cfg)
        assert set(_ids(result)) == {"IMP001", "PDT001"}

    def test_select_unknown_id_returns_empty(self) -> None:
        cfg = sergey_config.Config(select=frozenset({"UNKNOWN"}), ignore=frozenset())
        assert sergey_config.filter_rules(_SAMPLE_RULES, cfg) == []

    def test_ignore_removes_listed_rules(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset({"IMP001"}))
        result = _ids(sergey_config.filter_rules(_SAMPLE_RULES, cfg))
        assert "IMP001" not in result
        assert "IMP002" in result
        assert "PDT001" in result

    def test_ignore_all_returns_empty(self) -> None:
        cfg = sergey_config.Config(
            select=None, ignore=frozenset({"IMP001", "IMP002", "PDT001"})
        )
        assert sergey_config.filter_rules(_SAMPLE_RULES, cfg) == []

    def test_select_then_ignore(self) -> None:
        # select IMP001+IMP002, then ignore IMP001 → only IMP002 remains
        cfg = sergey_config.Config(
            select=frozenset({"IMP001", "IMP002"}), ignore=frozenset({"IMP001"})
        )
        result = sergey_config.filter_rules(_SAMPLE_RULES, cfg)
        assert _ids(result) == ["IMP002"]

    def test_original_order_preserved(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset({"IMP002"}))
        result = _ids(sergey_config.filter_rules(_SAMPLE_RULES, cfg))
        assert result == ["IMP001", "PDT001"]

    def test_empty_rules_list(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset())
        assert sergey_config.filter_rules([], cfg) == []


# ---------------------------------------------------------------------------
# Integration: filtered rules actually affect analysis
# ---------------------------------------------------------------------------


class TestFilterIntegration:
    def test_ignored_rule_produces_no_diagnostic(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset({"NAM002"}))
        active = sergey_config.filter_rules([naming.NAM002()], cfg)
        az = sergey_analyzer.Analyzer(rules=active)
        # NAM002 would normally flag `x` as non-descriptive
        assert az.analyze("x = 1") == []

    def test_selected_rule_still_fires(self) -> None:
        cfg = sergey_config.Config(select=frozenset({"NAM002"}), ignore=frozenset())
        active = sergey_config.filter_rules([naming.NAM002(), imports.IMP001()], cfg)
        az = sergey_analyzer.Analyzer(rules=active)
        diag_ids = [diag.rule_id for diag in az.analyze("x = 1")]
        assert diag_ids == ["NAM002"]


# ---------------------------------------------------------------------------
# load_config — rule_options
# ---------------------------------------------------------------------------


class TestLoadConfigRuleOptions:
    def test_no_rules_section_returns_empty_options(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.sergey]\n")
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.rule_options == {}

    def test_rule_options_loaded(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.sergey.rules.STR003]\nmax_body_stmts = 2\n"
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.rule_options == {"STR003": {"max_body_stmts": 2}}

    def test_rule_id_normalised_to_uppercase(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.sergey.rules.str003]\nmax_body_stmts = 3\n"
        )
        cfg = sergey_config.load_config(tmp_path)
        assert "STR003" in cfg.rule_options

    def test_non_scalar_option_values_ignored(self, tmp_path: pathlib.Path) -> None:
        # Lists and dicts are not valid option values and should be dropped.
        (tmp_path / "pyproject.toml").write_text(
            "[tool.sergey.rules.STR003]\nmax_body_stmts = 2\nbad = [1, 2, 3]\n"
        )
        cfg = sergey_config.load_config(tmp_path)
        assert cfg.rule_options["STR003"] == {"max_body_stmts": 2}


# ---------------------------------------------------------------------------
# configure_rules
# ---------------------------------------------------------------------------


class TestConfigureRules:
    def test_no_options_returns_same_rules(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset())
        rules = [structure.STR003()]
        result = sergey_config.configure_rules(rules, cfg)
        assert result == rules

    def test_options_applied_to_matching_rule(self) -> None:
        cfg = sergey_config.Config(
            select=None,
            ignore=frozenset(),
            rule_options={"STR003": {"max_body_stmts": 2}},
        )
        original = structure.STR003()
        result = sergey_config.configure_rules([original], cfg)
        assert len(result) == 1
        # The configured rule uses the new threshold
        source = "try:\n    a=1\n    b=2\n    c=3\nexcept Exception:\n    pass\n"
        import ast  # noqa: PLC0415
        tree = ast.parse(source)
        assert len(result[0].check(tree, source)) == 1
        assert len(original.check(tree, source)) == 0

    def test_options_not_applied_to_other_rules(self) -> None:
        cfg = sergey_config.Config(
            select=None,
            ignore=frozenset(),
            rule_options={"STR003": {"max_body_stmts": 2}},
        )
        imp_rule = imports.IMP001()
        result = sergey_config.configure_rules([imp_rule], cfg)
        assert result == [imp_rule]

    def test_empty_rules_list(self) -> None:
        cfg = sergey_config.Config(select=None, ignore=frozenset())
        assert sergey_config.configure_rules([], cfg) == []
