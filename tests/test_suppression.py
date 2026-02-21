"""Tests for inline suppression: # sergey: noqa and # sergey: disable-file."""

import textwrap

from sergey import analyzer
from sergey.rules import imports, naming

# Focused rule sets so tests are predictable regardless of ALL_RULES changes.
_imp_analyzer = analyzer.Analyzer(rules=[imports.IMP001(), imports.IMP002()])
_nam_analyzer = analyzer.Analyzer(rules=[naming.NAM002()])


def _imp_ids(source: str) -> list[str]:
    return [diag.rule_id for diag in _imp_analyzer.analyze(source)]


def _nam_ids(source: str) -> list[str]:
    return [diag.rule_id for diag in _nam_analyzer.analyze(source)]


# ---------------------------------------------------------------------------
# Line-level suppression  —  # sergey: noqa[: RULE1,RULE2]
# ---------------------------------------------------------------------------


class TestLineSuppression:
    def test_noqa_bare_suppresses_all_rules_on_line(self) -> None:
        assert _imp_ids("from os.path import join  # sergey: noqa") == []

    def test_noqa_specific_matching_rule_suppressed(self) -> None:
        assert _imp_ids("from os.path import join  # sergey: noqa: IMP001") == []

    def test_noqa_specific_nonmatching_rule_not_suppressed(self) -> None:
        # IMP002 listed but IMP001 is the one that fires — should NOT be suppressed
        result = _imp_ids("from os.path import join  # sergey: noqa: IMP002")
        assert result == ["IMP001"]

    def test_noqa_only_affects_its_own_line(self) -> None:
        source = textwrap.dedent("""\
            from os.path import join
            import os  # sergey: noqa
        """)
        # the suppression on line 2 has no effect on IMP001 on line 1
        assert _imp_ids(source) == ["IMP001"]

    def test_noqa_multiple_comma_separated_rules(self) -> None:
        source = "from os.path import join  # sergey: noqa: IMP001, IMP002"
        assert _imp_ids(source) == []

    def test_noqa_case_insensitive_rule_id(self) -> None:
        assert _imp_ids("from os.path import join  # sergey: noqa: imp001") == []

    def test_noqa_extra_whitespace_around_keyword(self) -> None:
        assert _imp_ids("from os.path import join  #  sergey:  noqa") == []

    def test_noqa_works_for_nam002(self) -> None:
        assert _nam_ids("x = 1  # sergey: noqa") == []

    def test_noqa_specific_rule_works_for_nam002(self) -> None:
        assert _nam_ids("x = 1  # sergey: noqa: NAM002") == []

    def test_noqa_wrong_rule_does_not_suppress_nam002(self) -> None:
        result = _nam_ids("x = 1  # sergey: noqa: IMP001")
        assert result == ["NAM002"]

    def test_noqa_on_comment_only_line_does_not_affect_other_lines(self) -> None:
        source = textwrap.dedent("""\
            from os.path import join
            # sergey: noqa
        """)
        # The noqa comment is on line 2; the diagnostic is on line 1.
        assert _imp_ids(source) == ["IMP001"]


# ---------------------------------------------------------------------------
# File-level suppression  —  # sergey: disable-file[: RULE1,RULE2]
# ---------------------------------------------------------------------------


class TestFileSuppression:
    def test_disable_file_bare_suppresses_all(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file
            from os.path import join
            from typing import Optional
        """)
        assert _imp_ids(source) == []

    def test_disable_file_specific_rule_suppresses_only_that_rule(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: IMP001
            from os.path import join
            from typing import Optional
        """)
        result = _imp_ids(source)
        assert result == ["IMP002"]

    def test_disable_file_does_not_suppress_other_rules(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: IMP002
            from os.path import join
        """)
        result = _imp_ids(source)
        assert result == ["IMP001"]

    def test_disable_file_applies_regardless_of_position(self) -> None:
        # disable-file at the bottom still covers lines above it
        source = textwrap.dedent("""\
            from os.path import join
            from typing import Optional
            # sergey: disable-file
        """)
        assert _imp_ids(source) == []

    def test_disable_file_multiple_rules_comma_separated(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: IMP001, IMP002
            from os.path import join
            from typing import Optional
        """)
        assert _imp_ids(source) == []

    def test_disable_file_case_insensitive_rule_id(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: imp001
            from os.path import join
        """)
        assert _imp_ids(source) == []

    def test_disable_file_works_for_nam002(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: NAM002
            x = 1
            y = 2
        """)
        assert _nam_ids(source) == []


# ---------------------------------------------------------------------------
# Combined file-level + line-level suppression
# ---------------------------------------------------------------------------


class TestCombinedSuppression:
    def test_file_and_line_together_suppress_different_rules(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: IMP001
            from os.path import join
            from typing import Optional  # sergey: noqa: IMP002
        """)
        # IMP001 suppressed by file directive, IMP002 suppressed on its line
        assert _imp_ids(source) == []

    def test_line_suppression_fills_gap_left_by_file_suppression(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file: IMP001
            from os.path import join
            from typing import Optional
        """)
        # IMP001 file-disabled; IMP002 on line 3 is NOT suppressed
        result = _imp_ids(source)
        assert result == ["IMP002"]

    def test_file_suppression_and_redundant_line_noqa(self) -> None:
        source = textwrap.dedent("""\
            # sergey: disable-file
            from os.path import join  # sergey: noqa: IMP001
        """)
        assert _imp_ids(source) == []
