"""Tests for STR002 structure rules."""

import ast
import textwrap

from sergey.rules import structure


def _check_str002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in structure.STR002().check(tree, source)]


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
