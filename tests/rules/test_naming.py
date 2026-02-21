"""Tests for NAM002 naming rules."""

import ast
import textwrap

from sergey.rules import naming


def _check_nam002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in naming.NAM002().check(tree, source)]


class TestNAM002:
    def test_descriptive_name_ok(self) -> None:
        assert _check_nam002("result = 1") == []

    def test_two_char_name_ok(self) -> None:
        assert _check_nam002("ok = 1") == []

    def test_throwaway_underscore_ok(self) -> None:
        assert _check_nam002("_ = some_function()") == []

    def test_single_char_assignment_flagged(self) -> None:
        assert _check_nam002("x = 1") == ["NAM002"]

    def test_uppercase_single_char_flagged(self) -> None:
        assert _check_nam002("X = 1") == ["NAM002"]

    def test_annotated_assignment_flagged(self) -> None:
        assert _check_nam002("x: int = 1") == ["NAM002"]

    def test_augmented_assignment_flagged(self) -> None:
        # x must already exist; the Store context on += is still flagged
        source = textwrap.dedent("""\
            x = 0
            x += 1
        """)
        assert _check_nam002(source) == ["NAM002", "NAM002"]

    def test_for_loop_variable_flagged(self) -> None:
        assert _check_nam002("for i in range(10): pass") == ["NAM002"]

    def test_descriptive_loop_variable_ok(self) -> None:
        assert _check_nam002("for idx in range(10): pass") == []

    def test_list_comprehension_variable_flagged(self) -> None:
        # [x ...] is a Load; only the Store in `for x` is flagged
        source = "[val for val in range(10)]"
        assert _check_nam002(source) == []

    def test_list_comprehension_single_char_flagged(self) -> None:
        source = "[x for x in range(10)]"
        assert _check_nam002(source) == ["NAM002"]

    def test_dict_comprehension_both_flagged(self) -> None:
        source = "{k: v for k, v in items.items()}"
        result = _check_nam002(source)
        assert result == ["NAM002", "NAM002"]

    def test_set_comprehension_flagged(self) -> None:
        assert _check_nam002("{x for x in items}") == ["NAM002"]

    def test_generator_expression_flagged(self) -> None:
        assert _check_nam002("list(x for x in items)") == ["NAM002"]

    def test_walrus_operator_flagged(self) -> None:
        assert _check_nam002("(n := compute())") == ["NAM002"]

    def test_walrus_descriptive_ok(self) -> None:
        assert _check_nam002("(result := compute())") == []

    def test_with_statement_single_char_flagged(self) -> None:
        assert _check_nam002("with open('f') as f: pass") == ["NAM002"]

    def test_multiple_single_char_assignments(self) -> None:
        source = textwrap.dedent("""\
            x = 1
            y = 2
            total = x + y
        """)
        assert _check_nam002(source) == ["NAM002", "NAM002"]

    def test_nested_comprehension_all_flagged(self) -> None:
        # Both `r` and `c` are single-char comprehension variables
        source = "[[c for c in r] for r in matrix]"
        result = _check_nam002(source)
        assert len(result) == 2
        assert all(rule_id == "NAM002" for rule_id in result)

    def test_diagnostic_message_contains_name(self) -> None:
        source = "x = 1"
        tree = ast.parse(source)
        diags = naming.NAM002().check(tree, source)
        assert len(diags) == 1
        assert "`x`" in diags[0].message
        assert "descriptive" in diags[0].message

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            result = 0
            x = 1
        """)
        tree = ast.parse(source)
        diags = naming.NAM002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_col_offset(self) -> None:
        source = textwrap.dedent("""\
            def fn():
                x = 1
        """)
        tree = ast.parse(source)
        diags = naming.NAM002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].col == 4

    def test_rule_id(self) -> None:
        source = "n = 1"
        tree = ast.parse(source)
        diags = naming.NAM002().check(tree, source)
        assert diags[0].rule_id == "NAM002"
