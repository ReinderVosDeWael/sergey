"""Tests for STR002 and STR003 structure rules."""

import ast
import textwrap

from sergey.rules import structure


def _check_str002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in structure.STR002().check(tree, source)]


def _check_str003(source: str, **kwargs: int) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in structure.STR003(**kwargs).check(tree, source)]


# ---------------------------------------------------------------------------
# STR002 — maximum nesting depth
# ---------------------------------------------------------------------------


class TestSTR002:
    # ------------------------------------------------------------------
    # Within-limit cases (no diagnostic expected)
    # ------------------------------------------------------------------

    def test_depth_zero_ok(self) -> None:
        assert _check_str002("x = 1") == []

    def test_depth_one_ok(self) -> None:
        assert _check_str002("for item in items: pass") == []

    def test_depth_four_ok(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        if c:
                            with ctx:
                                pass
        """
        assert _check_str002(source) == []

    def test_elif_does_not_add_depth(self) -> None:
        # if/elif/else is one level; the elif should NOT push depth to 5.
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            if case1:
                                pass
                            elif case2:
                                pass
                            else:
                                pass
        """
        assert _check_str002(source) == []

    def test_nested_function_resets_depth(self) -> None:
        # Outer code is at depth 4; inner function resets to 0.
        source = """\
            def outer():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                def inner():
                                    if flag:
                                        pass
        """
        assert _check_str002(source) == []

    def test_class_resets_depth(self) -> None:
        source = """\
            for a in x:
                for b in y:
                    for c in z:
                        for d in w:
                            class Inner:
                                if True:
                                    pass
        """
        assert _check_str002(source) == []

    def test_lambda_resets_depth(self) -> None:
        # The lambda body is a fresh scope.
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                fn = lambda: 1
        """
        assert _check_str002(source) == []

    def test_while_loop_at_depth_four_ok(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        if c:
                            while running:
                                pass
        """
        assert _check_str002(source) == []

    def test_try_at_depth_four_ok(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        if c:
                            try:
                                pass
                            except Exception:
                                pass
        """
        assert _check_str002(source) == []

    # ------------------------------------------------------------------
    # Over-limit cases (diagnostic expected)
    # ------------------------------------------------------------------

    def test_depth_five_flagged(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if flag:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_depth_five_module_level_flagged(self) -> None:
        # Nesting at module level is also counted.
        source = """\
            for a in x:
                for b in y:
                    for c in z:
                        for d in w:
                            if flag:
                                pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_two_sibling_violations_two_diagnostics(self) -> None:
        # Two separate depth-5 blocks in the same function → two diagnostics.
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if flag1:
                                    pass
                                if flag2:
                                    pass
        """
        assert _check_str002(source) == ["STR002", "STR002"]

    def test_elif_at_depth_five_not_double_counted(self) -> None:
        # The if/elif at depth 5 emits only ONE diagnostic (for the `if`).
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if case1:
                                    pass
                                elif case2:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_while_at_depth_five_flagged(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                while running:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_with_at_depth_five_flagged(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                with ctx:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_try_at_depth_five_flagged(self) -> None:
        source = """\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                try:
                                    pass
                                except Exception:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_async_for_flagged(self) -> None:
        source = """\
            async def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                async for e in stream:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    def test_async_with_flagged(self) -> None:
        source = """\
            async def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                async with lock:
                                    pass
        """
        assert _check_str002(source) == ["STR002"]

    # ------------------------------------------------------------------
    # Diagnostic metadata
    # ------------------------------------------------------------------

    def test_diagnostic_rule_id(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if flag:
                                    pass
        """)
        tree = ast.parse(source)
        diags = structure.STR002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].rule_id == "STR002"

    def test_diagnostic_line_points_to_offending_block(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if flag:
                                    pass
        """)
        tree = ast.parse(source)
        diags = structure.STR002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 6  # the `if flag:` line

    def test_diagnostic_message_contains_depth(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                for a in x:
                    for b in y:
                        for c in z:
                            for d in w:
                                if flag:
                                    pass
        """)
        tree = ast.parse(source)
        diags = structure.STR002().check(tree, source)
        assert "5" in diags[0].message
        assert "4" in diags[0].message  # mentions the maximum too


# ---------------------------------------------------------------------------
# STR003 — long try bodies
# ---------------------------------------------------------------------------


class TestSTR003:
    # ------------------------------------------------------------------
    # Within-limit cases (no diagnostic expected)
    # ------------------------------------------------------------------

    def test_empty_try_ok(self) -> None:
        assert _check_str003("try:\n    pass\nexcept Exception:\n    pass") == []

    def test_four_stmts_ok(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
            except Exception:
                pass
        """
        assert _check_str003(source) == []

    def test_long_except_not_flagged(self) -> None:
        # except block length is irrelevant — only the try body counts
        source = """\
            try:
                result = fetch()
            except Exception:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
                f = 6
        """
        assert _check_str003(source) == []

    def test_long_finally_not_flagged(self) -> None:
        source = """\
            try:
                result = fetch()
            except Exception:
                pass
            finally:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
        """
        assert _check_str003(source) == []

    def test_custom_threshold_below_ok(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
            except Exception:
                pass
        """
        assert _check_str003(source, max_body_stmts=2) == []

    # ------------------------------------------------------------------
    # Over-limit cases (diagnostic expected)
    # ------------------------------------------------------------------

    def test_five_stmts_flagged(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """
        assert _check_str003(source) == ["STR003"]

    def test_six_stmts_flagged(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
                f = 6
            except Exception:
                pass
        """
        assert _check_str003(source) == ["STR003"]

    def test_two_try_blocks_both_long(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """
        assert _check_str003(source) == ["STR003", "STR003"]

    def test_custom_threshold_exceeded(self) -> None:
        source = """\
            try:
                a = 1
                b = 2
                c = 3
            except Exception:
                pass
        """
        assert _check_str003(source, max_body_stmts=2) == ["STR003"]

    # ------------------------------------------------------------------
    # Diagnostic metadata
    # ------------------------------------------------------------------

    def test_rule_id(self) -> None:
        source = textwrap.dedent("""\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """)
        tree = ast.parse(source)
        diags = structure.STR003().check(tree, source)
        assert diags[0].rule_id == "STR003"

    def test_diagnostic_line_points_to_try(self) -> None:
        source = textwrap.dedent("""\
            x = 0
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """)
        tree = ast.parse(source)
        diags = structure.STR003().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2  # the `try:` line

    def test_diagnostic_message_contains_counts(self) -> None:
        source = textwrap.dedent("""\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """)
        tree = ast.parse(source)
        diags = structure.STR003().check(tree, source)
        assert "5" in diags[0].message   # actual count
        assert "4" in diags[0].message   # maximum allowed

    def test_configure_changes_threshold(self) -> None:
        rule = structure.STR003()
        configured = rule.configure({"max_body_stmts": 2})
        source = textwrap.dedent("""\
            try:
                a = 1
                b = 2
                c = 3
            except Exception:
                pass
        """)
        tree = ast.parse(source)
        assert len(configured.check(tree, source)) == 1

    def test_configure_unknown_option_returns_same_behaviour(self) -> None:
        rule = structure.STR003()
        configured = rule.configure({"unknown_option": 99})
        source = textwrap.dedent("""\
            try:
                a = 1
                b = 2
                c = 3
                d = 4
                e = 5
            except Exception:
                pass
        """)
        tree = ast.parse(source)
        assert configured.check(tree, source) == rule.check(tree, source)
