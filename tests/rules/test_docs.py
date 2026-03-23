"""Tests for DOC001 documentation rules."""

import ast
import textwrap

from sergey.rules import docs


def _check_doc001(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in docs.DOC001().check(tree, source)]


class TestDOC001:
    # ------------------------------------------------------------------
    # No diagnostic expected
    # ------------------------------------------------------------------

    def test_no_raise_no_docstring_ok(self) -> None:
        assert _check_doc001("def foo(): pass") == []

    def test_no_raise_with_docstring_ok(self) -> None:
        source = '''\
            def foo():
                """Do something."""
                return 1
        '''
        assert _check_doc001(source) == []

    def test_raise_without_docstring_ok(self) -> None:
        # No docstring: this rule does not check for docstring presence.
        source = """\
            def foo():
                raise ValueError("bad")
        """
        assert _check_doc001(source) == []

    def test_google_raises_section_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: Always.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == []

    def test_numpy_raises_section_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises
                ------
                ValueError
                    Always.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == []

    def test_bare_reraise_exempt(self) -> None:
        # Bare `raise` inside an except block is not an explicit raise.
        source = '''\
            def foo():
                """Do something."""
                try:
                    pass
                except Exception:
                    raise
        '''
        assert _check_doc001(source) == []

    def test_raise_in_nested_function_not_counted(self) -> None:
        # The raise is in `inner`, not `outer`; outer should not be flagged.
        source = '''\
            def outer():
                """Outer summary."""
                def inner():
                    raise ValueError("inner")
                inner()
        '''
        assert _check_doc001(source) == []

    def test_nested_function_with_raises_section_ok(self) -> None:
        source = '''\
            def outer():
                """Outer summary."""
                def inner():
                    """Inner summary.

                    Raises:
                        ValueError: Always.
                    """
                    raise ValueError("always")
                inner()
        '''
        assert _check_doc001(source) == []

    def test_raise_in_nested_class_method_not_counted(self) -> None:
        source = '''\
            def outer():
                """Outer summary."""
                class Inner:
                    def method(self):
                        raise ValueError("inner")
        '''
        assert _check_doc001(source) == []

    def test_async_function_with_raises_section_ok(self) -> None:
        source = '''\
            async def foo():
                """Summary.

                Raises:
                    RuntimeError: On failure.
                """
                raise RuntimeError("fail")
        '''
        assert _check_doc001(source) == []

    def test_raise_inside_if_with_raises_section_ok(self) -> None:
        source = '''\
            def foo(x):
                """Summary.

                Raises:
                    ValueError: If x is negative.
                """
                if x < 0:
                    raise ValueError("negative")
        '''
        assert _check_doc001(source) == []

    def test_raise_inside_try_with_raises_section_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    RuntimeError: On failure.
                """
                try:
                    pass
                except Exception as exc:
                    raise RuntimeError("fail") from exc
        '''
        assert _check_doc001(source) == []

    def test_method_with_raises_section_ok(self) -> None:
        source = '''\
            class Foo:
                def method(self):
                    """Summary.

                    Raises:
                        ValueError: Always.
                    """
                    raise ValueError("always")
        '''
        assert _check_doc001(source) == []

    # ------------------------------------------------------------------
    # Diagnostic expected
    # ------------------------------------------------------------------

    def test_raise_with_docstring_no_raises_section_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary."""
                raise ValueError("always")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_async_function_flagged(self) -> None:
        source = '''\
            async def foo():
                """Summary."""
                raise RuntimeError("fail")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_raise_inside_if_flagged(self) -> None:
        source = '''\
            def foo(x):
                """Summary."""
                if x < 0:
                    raise ValueError("negative")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_raise_inside_for_loop_flagged(self) -> None:
        source = '''\
            def foo(items):
                """Summary."""
                for item in items:
                    if not item:
                        raise ValueError("empty item")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_raise_inside_try_except_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary."""
                try:
                    pass
                except Exception as exc:
                    raise RuntimeError("fail") from exc
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_method_without_raises_section_flagged(self) -> None:
        source = '''\
            class Foo:
                def method(self):
                    """Summary."""
                    raise ValueError("always")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_nested_function_flagged_independently(self) -> None:
        # `inner` has a docstring and raises but no Raises section.
        source = '''\
            def outer():
                """Outer summary."""
                def inner():
                    """Inner summary."""
                    raise ValueError("inner")
                inner()
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_multiple_functions_each_flagged(self) -> None:
        source = '''\
            def foo():
                """Foo summary."""
                raise ValueError("foo")

            def bar():
                """Bar summary."""
                raise RuntimeError("bar")
        '''
        assert _check_doc001(source) == ["DOC001", "DOC001"]

    def test_one_good_one_bad(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: Always.
                """
                raise ValueError("always")

            def bar():
                """Summary."""
                raise RuntimeError("always")
        '''
        assert _check_doc001(source) == ["DOC001"]

    # ------------------------------------------------------------------
    # Diagnostic metadata
    # ------------------------------------------------------------------

    def test_rule_id(self) -> None:
        source = textwrap.dedent('''\
            def foo():
                """Summary."""
                raise ValueError("x")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert diags[0].rule_id == "DOC001"

    def test_diagnostic_points_to_def_line(self) -> None:
        source = textwrap.dedent('''\
            x = 1
            def foo():
                """Summary."""
                raise ValueError("x")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_message_contains_function_name(self) -> None:
        source = textwrap.dedent('''\
            def parse(text):
                """Parse."""
                raise ValueError("bad")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert "`parse`" in diags[0].message
        assert "Raises" in diags[0].message

    # ------------------------------------------------------------------
    # Raises section present but missing specific exception class
    # ------------------------------------------------------------------

    def test_raises_section_documents_correct_exception_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: Always.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == []

    def test_raises_section_wrong_exception_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    RuntimeError: Something.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_raises_section_partial_documentation_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: One case.
                """
                raise ValueError("v")
                raise RuntimeError("r")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_raises_section_all_exceptions_documented_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: First case.
                    RuntimeError: Second case.
                """
                raise ValueError("v")
                raise RuntimeError("r")
        '''
        assert _check_doc001(source) == []

    def test_raises_section_duplicate_raises_one_diagnostic(self) -> None:
        # Same exception raised twice — only one diagnostic expected.
        source = '''\
            def foo(x):
                """Summary.

                Raises:
                    RuntimeError: Something.
                """
                if x < 0:
                    raise ValueError("neg")
                raise ValueError("other")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_numpy_raises_section_documents_exception_ok(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises
                ------
                ValueError
                    Always.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == []

    def test_numpy_raises_section_wrong_exception_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises
                ------
                RuntimeError
                    Something.
                """
                raise ValueError("always")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_qualified_exception_class_checked(self) -> None:
        # raise module.SomeError() — the attr "SomeError" is extracted.
        source = '''\
            def foo():
                """Summary.

                Raises:
                    SomeError: Always.
                """
                raise module.SomeError("x")
        '''
        assert _check_doc001(source) == []

    def test_qualified_exception_missing_flagged(self) -> None:
        source = '''\
            def foo():
                """Summary.

                Raises:
                    OtherError: Something.
                """
                raise module.SomeError("x")
        '''
        assert _check_doc001(source) == ["DOC001"]

    def test_variable_reraise_not_flagged(self) -> None:
        # `raise exc` — lowercase name treated as variable, not a class.
        source = '''\
            def foo():
                """Summary.

                Raises:
                    RuntimeError: On failure.
                """
                try:
                    pass
                except RuntimeError as exc:
                    raise exc
        '''
        assert _check_doc001(source) == []

    def test_exception_not_substring_matched(self) -> None:
        # "Error" must not match "ValueError" — word-boundary check.
        source = '''\
            def foo():
                """Summary.

                Raises:
                    ValueError: Always.
                """
                raise Error("x")
        '''
        assert _check_doc001(source) == ["DOC001"]

    # ------------------------------------------------------------------
    # Diagnostic metadata for per-exception diagnostics
    # ------------------------------------------------------------------

    def test_missing_exception_diagnostic_points_to_raise(self) -> None:
        source = textwrap.dedent('''\
            def foo():
                """Summary.

                Raises:
                    RuntimeError: Something.
                """
                raise ValueError("x")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 7  # the raise statement

    def test_missing_exception_message_mentions_exception_name(self) -> None:
        source = textwrap.dedent('''\
            def foo():
                """Summary.

                Raises:
                    RuntimeError: Something.
                """
                raise ValueError("x")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert "`ValueError`" in diags[0].message

    def test_missing_exception_message_mentions_function_name(self) -> None:
        source = textwrap.dedent('''\
            def parse(text):
                """Parse.

                Raises:
                    RuntimeError: Something.
                """
                raise ValueError("x")
        ''')
        tree = ast.parse(source)
        diags = docs.DOC001().check(tree, source)
        assert "`parse`" in diags[0].message
