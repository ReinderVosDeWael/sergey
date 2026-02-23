"""Tests for STR002, STR003, and STR004 structure rules."""

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
        assert "5" in diags[0].message  # actual count
        assert "4" in diags[0].message  # maximum allowed

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


# ---------------------------------------------------------------------------
# STR004 — prefer tuples for unmodified lists
# ---------------------------------------------------------------------------


def _check_str004(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in structure.STR004().check(tree, source)]


class TestSTR004:
    # ------------------------------------------------------------------
    # Cases that SHOULD be flagged
    # ------------------------------------------------------------------

    def test_unmodified_list_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                for item in items:
                    print(item)
        """
        assert _check_str004(source) == ["STR004"]

    def test_unused_list_flagged(self) -> None:
        source = """\
            def foo():
                items = []
        """
        assert _check_str004(source) == ["STR004"]

    def test_list_used_for_membership_flagged(self) -> None:
        source = """\
            def foo(val):
                allowed = [1, 2, 3]
                if val in allowed:
                    pass
        """
        assert _check_str004(source) == ["STR004"]

    def test_annotated_assignment_flagged(self) -> None:
        source = """\
            def foo():
                items: list[int] = [1, 2, 3]
                print(items)
        """
        assert _check_str004(source) == ["STR004"]

    def test_async_function_flagged(self) -> None:
        source = """\
            async def foo():
                items = [1, 2, 3]
                for item in items:
                    pass
        """
        assert _check_str004(source) == ["STR004"]

    def test_multiple_unmodified_lists_both_flagged(self) -> None:
        source = """\
            def foo():
                xs = [1, 2]
                ys = [3, 4]
                print(xs, ys)
        """
        assert _check_str004(source) == ["STR004", "STR004"]

    def test_list_in_if_branch_flagged(self) -> None:
        source = """\
            def foo(cond):
                if cond:
                    items = [1, 2, 3]
                    print(items)
        """
        assert _check_str004(source) == ["STR004"]

    def test_list_passed_to_function_still_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                print(len(items))
        """
        assert _check_str004(source) == ["STR004"]

    # ------------------------------------------------------------------
    # Cases that should NOT be flagged — in-place mutations
    # ------------------------------------------------------------------

    def test_append_not_flagged(self) -> None:
        source = """\
            def foo():
                items = []
                items.append(1)
        """
        assert _check_str004(source) == []

    def test_extend_not_flagged(self) -> None:
        source = """\
            def foo():
                items = []
                items.extend([1, 2])
        """
        assert _check_str004(source) == []

    def test_insert_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2]
                items.insert(0, 0)
        """
        assert _check_str004(source) == []

    def test_pop_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2]
                items.pop()
        """
        assert _check_str004(source) == []

    def test_remove_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                items.remove(2)
        """
        assert _check_str004(source) == []

    def test_clear_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2]
                items.clear()
        """
        assert _check_str004(source) == []

    def test_sort_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [3, 1, 2]
                items.sort()
        """
        assert _check_str004(source) == []

    def test_reverse_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                items.reverse()
        """
        assert _check_str004(source) == []

    def test_augmented_assignment_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1]
                items += [2, 3]
        """
        assert _check_str004(source) == []

    def test_subscript_assignment_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                items[0] = 99
        """
        assert _check_str004(source) == []

    def test_subscript_deletion_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                del items[0]
        """
        assert _check_str004(source) == []

    # ------------------------------------------------------------------
    # Cases that should NOT be flagged — function output
    # ------------------------------------------------------------------

    def test_returned_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                return items
        """
        assert _check_str004(source) == []

    def test_returned_in_tuple_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                return items, 42
        """
        assert _check_str004(source) == []

    def test_yielded_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                yield items
        """
        assert _check_str004(source) == []

    def test_yield_from_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                yield from items
        """
        assert _check_str004(source) == []

    # ------------------------------------------------------------------
    # Cases that should NOT be flagged — scope / rebinding / escape
    # ------------------------------------------------------------------

    def test_module_level_list_not_flagged(self) -> None:
        source = """\
            items = [1, 2, 3]
            for item in items:
                print(item)
        """
        assert _check_str004(source) == []

    def test_class_body_list_not_flagged(self) -> None:
        source = """\
            class Foo:
                items = [1, 2, 3]
        """
        assert _check_str004(source) == []

    def test_reassigned_variable_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                items = other()
        """
        assert _check_str004(source) == []

    def test_global_variable_not_flagged(self) -> None:
        source = """\
            def foo():
                global items
                items = [1, 2, 3]
        """
        assert _check_str004(source) == []

    def test_nonlocal_variable_not_flagged(self) -> None:
        source = """\
            def outer():
                items = []
                def foo():
                    nonlocal items
                    items = [1, 2, 3]
        """
        assert _check_str004(source) == []

    def test_used_in_nested_function_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                def inner():
                    print(items)
                inner()
        """
        assert _check_str004(source) == []

    def test_used_in_lambda_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                fn = lambda: items
        """
        assert _check_str004(source) == []

    def test_stored_as_attribute_not_flagged(self) -> None:
        source = """\
            def foo(self):
                items = [1, 2, 3]
                self.items = items
        """
        assert _check_str004(source) == []

    def test_stored_in_dict_not_flagged(self) -> None:
        source = """\
            def foo(data):
                items = [1, 2, 3]
                data["key"] = items
        """
        assert _check_str004(source) == []

    def test_multi_target_assignment_not_flagged(self) -> None:
        source = """\
            def foo():
                x = y = [1, 2, 3]
        """
        assert _check_str004(source) == []

    def test_for_loop_rebind_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                for items in something:
                    pass
        """
        assert _check_str004(source) == []

    def test_walrus_rebind_not_flagged(self) -> None:
        source = """\
            def foo():
                items = [1, 2, 3]
                if (items := other()):
                    pass
        """
        assert _check_str004(source) == []

    # ------------------------------------------------------------------
    # Diagnostic metadata
    # ------------------------------------------------------------------

    def test_rule_id(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                items = [1, 2, 3]
                print(items)
        """)
        tree = ast.parse(source)
        diags = structure.STR004().check(tree, source)
        assert len(diags) == 1
        assert diags[0].rule_id == "STR004"

    def test_diagnostic_line_points_to_assignment(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                x = 0
                items = [1, 2, 3]
                print(items)
        """)
        tree = ast.parse(source)
        diags = structure.STR004().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 3

    def test_diagnostic_message_contains_variable_name(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                colors = ["red", "green"]
                print(colors)
        """)
        tree = ast.parse(source)
        diags = structure.STR004().check(tree, source)
        assert len(diags) == 1
        assert "colors" in diags[0].message
        assert "tuple" in diags[0].message

    # ------------------------------------------------------------------
    # Set literals — cases that SHOULD be flagged
    # ------------------------------------------------------------------

    def test_unmodified_set_flagged(self) -> None:
        source = """\
            def foo(val):
                allowed = {1, 2, 3}
                if val in allowed:
                    print("ok")
        """
        assert _check_str004(source) == ["STR004"]

    def test_unused_set_flagged(self) -> None:
        source = """\
            def foo():
                tags = {"a", "b"}
        """
        assert _check_str004(source) == ["STR004"]

    def test_set_iterated_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                for item in items:
                    print(item)
        """
        assert _check_str004(source) == ["STR004"]

    def test_set_annotated_assignment_flagged(self) -> None:
        source = """\
            def foo():
                items: set[int] = {1, 2, 3}
                print(items)
        """
        assert _check_str004(source) == ["STR004"]

    def test_set_in_async_function_flagged(self) -> None:
        source = """\
            async def foo():
                vals = {1, 2}
                print(vals)
        """
        assert _check_str004(source) == ["STR004"]

    def test_mixed_list_and_set_both_flagged(self) -> None:
        source = """\
            def foo():
                xs = [1, 2]
                ys = {3, 4}
                print(xs, ys)
        """
        assert _check_str004(source) == ["STR004", "STR004"]

    # ------------------------------------------------------------------
    # Set literals — cases that should NOT be flagged (mutations)
    # ------------------------------------------------------------------

    def test_set_add_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2}
                items.add(3)
        """
        assert _check_str004(source) == []

    def test_set_update_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1}
                items.update({2, 3})
        """
        assert _check_str004(source) == []

    def test_set_discard_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items.discard(2)
        """
        assert _check_str004(source) == []

    def test_set_remove_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items.remove(2)
        """
        assert _check_str004(source) == []

    def test_set_pop_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2}
                items.pop()
        """
        assert _check_str004(source) == []

    def test_set_clear_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2}
                items.clear()
        """
        assert _check_str004(source) == []

    def test_set_difference_update_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items.difference_update({1})
        """
        assert _check_str004(source) == []

    def test_set_intersection_update_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items.intersection_update({2, 3})
        """
        assert _check_str004(source) == []

    def test_set_symmetric_difference_update_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items.symmetric_difference_update({3, 4})
        """
        assert _check_str004(source) == []

    def test_set_augmented_or_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1}
                items |= {2, 3}
        """
        assert _check_str004(source) == []

    def test_set_augmented_and_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items &= {2, 3}
        """
        assert _check_str004(source) == []

    def test_set_augmented_sub_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items -= {1}
        """
        assert _check_str004(source) == []

    def test_set_augmented_xor_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items ^= {3, 4}
        """
        assert _check_str004(source) == []

    # ------------------------------------------------------------------
    # Set literals — cases that should NOT be flagged (output / escape)
    # ------------------------------------------------------------------

    def test_set_returned_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                return items
        """
        assert _check_str004(source) == []

    def test_set_yielded_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                yield items
        """
        assert _check_str004(source) == []

    def test_set_used_in_nested_function_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                def inner():
                    print(items)
                inner()
        """
        assert _check_str004(source) == []

    def test_set_stored_as_attribute_not_flagged(self) -> None:
        source = """\
            def foo(self):
                items = {1, 2, 3}
                self.items = items
        """
        assert _check_str004(source) == []

    def test_set_reassigned_not_flagged(self) -> None:
        source = """\
            def foo():
                items = {1, 2, 3}
                items = other()
        """
        assert _check_str004(source) == []

    def test_set_global_not_flagged(self) -> None:
        source = """\
            def foo():
                global items
                items = {1, 2, 3}
        """
        assert _check_str004(source) == []

    def test_module_level_set_not_flagged(self) -> None:
        source = """\
            items = {1, 2, 3}
            print(items)
        """
        assert _check_str004(source) == []

    # ------------------------------------------------------------------
    # Set diagnostic metadata
    # ------------------------------------------------------------------

    def test_set_diagnostic_message(self) -> None:
        source = textwrap.dedent("""\
            def foo():
                tags = {"a", "b"}
                print(tags)
        """)
        tree = ast.parse(source)
        diags = structure.STR004().check(tree, source)
        assert len(diags) == 1
        assert "tags" in diags[0].message
        assert "Set" in diags[0].message
        assert "frozenset" in diags[0].message
