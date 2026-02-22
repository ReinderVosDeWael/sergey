"""Tests for NAM001, NAM002, and NAM003 naming rules."""

import ast
import textwrap

from sergey.rules import naming


def _check_nam001(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in naming.NAM001().check(tree, source)]


def _check_nam002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in naming.NAM002().check(tree, source)]


def _check_nam003(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in naming.NAM003().check(tree, source)]


# ---------------------------------------------------------------------------
# NAM001 — bool-returning functions must use a predicate prefix
# ---------------------------------------------------------------------------


class TestNAM001:
    def test_is_prefix_ok(self) -> None:
        assert _check_nam001("def is_valid(self) -> bool: ...") == []

    def test_has_prefix_ok(self) -> None:
        assert _check_nam001("def has_permission(user) -> bool: ...") == []

    def test_can_prefix_ok(self) -> None:
        assert _check_nam001("def can_read(self) -> bool: ...") == []

    def test_should_prefix_ok(self) -> None:
        assert _check_nam001("def should_retry() -> bool: ...") == []

    def test_will_prefix_ok(self) -> None:
        assert _check_nam001("def will_succeed() -> bool: ...") == []

    def test_did_prefix_ok(self) -> None:
        assert _check_nam001("def did_complete() -> bool: ...") == []

    def test_was_prefix_ok(self) -> None:
        assert _check_nam001("def was_processed() -> bool: ...") == []

    def test_no_annotation_ok(self) -> None:
        assert _check_nam001("def check(): ...") == []

    def test_non_bool_return_ok(self) -> None:
        assert _check_nam001("def check() -> int: ...") == []

    def test_none_return_ok(self) -> None:
        assert _check_nam001("def check() -> None: ...") == []

    def test_dunder_exempt(self) -> None:
        assert _check_nam001("def __eq__(self, other) -> bool: ...") == []

    def test_dunder_lt_exempt(self) -> None:
        assert _check_nam001("def __lt__(self, other) -> bool: ...") == []

    def test_union_return_not_flagged(self) -> None:
        # Only exactly `-> bool` is checked; `bool | None` is not.
        assert _check_nam001("def check() -> bool | None: ...") == []

    def test_missing_prefix_flagged(self) -> None:
        assert _check_nam001("def check() -> bool: ...") == ["NAM001"]

    def test_validate_flagged(self) -> None:
        assert _check_nam001("def validate(item) -> bool: ...") == ["NAM001"]

    def test_async_function_flagged(self) -> None:
        assert _check_nam001("async def check() -> bool: ...") == ["NAM001"]

    def test_async_with_prefix_ok(self) -> None:
        assert _check_nam001("async def is_ready() -> bool: ...") == []

    def test_private_function_with_prefix_ok(self) -> None:
        # _is_submodule has is_ prefix after stripping the leading underscore.
        assert _check_nam001("def _is_valid(x) -> bool: ...") == []

    def test_private_function_without_prefix_flagged(self) -> None:
        assert _check_nam001("def _check() -> bool: ...") == ["NAM001"]

    def test_method_flagged(self) -> None:
        source = textwrap.dedent("""\
            class Foo:
                def check(self) -> bool: ...
        """)
        assert _check_nam001(source) == ["NAM001"]

    def test_method_with_prefix_ok(self) -> None:
        source = textwrap.dedent("""\
            class Foo:
                def is_valid(self) -> bool: ...
        """)
        assert _check_nam001(source) == []

    def test_multiple_violations(self) -> None:
        source = textwrap.dedent("""\
            def check() -> bool: ...
            def verify() -> bool: ...
        """)
        assert _check_nam001(source) == ["NAM001", "NAM001"]

    def test_diagnostic_message_contains_function_name(self) -> None:
        source = "def check() -> bool: ..."
        tree = ast.parse(source)
        diags = naming.NAM001().check(tree, source)
        assert len(diags) == 1
        assert "`check`" in diags[0].message

    def test_diagnostic_message_mentions_bool(self) -> None:
        source = "def check() -> bool: ..."
        tree = ast.parse(source)
        diags = naming.NAM001().check(tree, source)
        assert "bool" in diags[0].message

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            def is_fine() -> bool: ...
            def check() -> bool: ...
        """)
        tree = ast.parse(source)
        diags = naming.NAM001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_rule_id(self) -> None:
        source = "def check() -> bool: ..."
        tree = ast.parse(source)
        diags = naming.NAM001().check(tree, source)
        assert diags[0].rule_id == "NAM001"


# ---------------------------------------------------------------------------
# NAM002 — single-character variable names
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# NAM003 — single-character function parameter names
# ---------------------------------------------------------------------------


class TestNAM003:
    def test_descriptive_param_ok(self) -> None:
        assert _check_nam003("def process(value): ...") == []

    def test_two_char_param_ok(self) -> None:
        assert _check_nam003("def process(fn): ...") == []

    def test_throwaway_underscore_ok(self) -> None:
        assert _check_nam003("def apply(_, transform): ...") == []

    def test_single_char_param_flagged(self) -> None:
        assert _check_nam003("def process(x): ...") == ["NAM003"]

    def test_uppercase_single_char_flagged(self) -> None:
        assert _check_nam003("def process(N): ...") == ["NAM003"]

    def test_multiple_single_char_params_flagged(self) -> None:
        assert _check_nam003("def process(x, y): ...") == ["NAM003", "NAM003"]

    def test_mixed_params_only_bad_flagged(self) -> None:
        result = _check_nam003("def process(value, x, count, y): ...")
        assert result == ["NAM003", "NAM003"]

    def test_vararg_not_flagged(self) -> None:
        # *args is exempt even if named with one char
        assert _check_nam003("def process(*a): ...") == []

    def test_kwarg_not_flagged(self) -> None:
        assert _check_nam003("def process(**k): ...") == []

    def test_posonly_single_char_flagged(self) -> None:
        assert _check_nam003("def process(x, /): ...") == ["NAM003"]

    def test_posonly_descriptive_ok(self) -> None:
        assert _check_nam003("def process(value, /): ...") == []

    def test_kwonly_single_char_flagged(self) -> None:
        assert _check_nam003("def process(*, x): ...") == ["NAM003"]

    def test_kwonly_descriptive_ok(self) -> None:
        assert _check_nam003("def process(*, key): ...") == []

    def test_async_function_flagged(self) -> None:
        assert _check_nam003("async def process(x): ...") == ["NAM003"]

    def test_async_descriptive_ok(self) -> None:
        assert _check_nam003("async def process(value): ...") == []

    def test_method_self_ok(self) -> None:
        # 'self' is 4 chars, not flagged
        source = textwrap.dedent("""\
            class Foo:
                def method(self): ...
        """)
        assert _check_nam003(source) == []

    def test_method_single_char_arg_flagged(self) -> None:
        source = textwrap.dedent("""\
            class Foo:
                def method(self, x): ...
        """)
        assert _check_nam003(source) == ["NAM003"]

    def test_lambda_not_checked(self) -> None:
        # Lambda parameters are ast.arg nodes inside ast.Lambda, not FunctionDef.
        assert _check_nam003("f = lambda x: x") == []

    def test_nested_function_flagged(self) -> None:
        source = textwrap.dedent("""\
            def outer():
                def inner(x): ...
        """)
        assert _check_nam003(source) == ["NAM003"]

    def test_diagnostic_message_contains_param_name(self) -> None:
        source = "def process(x): ..."
        tree = ast.parse(source)
        diags = naming.NAM003().check(tree, source)
        assert len(diags) == 1
        assert "`x`" in diags[0].message
        assert "descriptive" in diags[0].message

    def test_diagnostic_col_offset(self) -> None:
        source = "def process(value, x): ..."
        tree = ast.parse(source)
        diags = naming.NAM003().check(tree, source)
        assert len(diags) == 1
        assert diags[0].col == 19  # column of 'x'

    def test_rule_id(self) -> None:
        source = "def process(x): ..."
        tree = ast.parse(source)
        diags = naming.NAM003().check(tree, source)
        assert diags[0].rule_id == "NAM003"
