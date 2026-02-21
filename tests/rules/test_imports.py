"""Tests for IMP001 and IMP002 import-style rules."""

import ast
import textwrap

from mercury_bot.rules.imports import IMP001, IMP002


def _check_imp001(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [d.rule_id for d in IMP001().check(tree, source)]


def _check_imp002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [d.rule_id for d in IMP002().check(tree, source)]


# ---------------------------------------------------------------------------
# IMP001 — non-typing from-imports
# ---------------------------------------------------------------------------


class TestIMP001:
    def test_plain_import_ok(self) -> None:
        assert _check_imp001("import os") == []

    def test_dotted_import_ok(self) -> None:
        assert _check_imp001("import os.path") == []

    def test_aliased_import_ok(self) -> None:
        assert _check_imp001("import collections.abc as abc") == []

    def test_multiple_plain_imports_ok(self) -> None:
        assert _check_imp001("import os, sys, re") == []

    def test_from_import_function_flagged(self) -> None:
        assert _check_imp001("from os.path import join") == ["IMP001"]

    def test_from_import_class_flagged(self) -> None:
        assert _check_imp001("from collections import OrderedDict") == ["IMP001"]

    def test_from_import_multiple_names_one_diagnostic(self) -> None:
        # One ImportFrom node → one diagnostic, regardless of how many names
        result = _check_imp001("from os.path import join, exists, dirname")
        assert result == ["IMP001"]

    def test_multiple_from_import_statements_each_flagged(self) -> None:
        source = """\
            from os.path import join
            from collections import OrderedDict
        """
        assert _check_imp001(source) == ["IMP001", "IMP001"]

    def test_future_import_excluded(self) -> None:
        assert _check_imp001("from __future__ import annotations") == []

    def test_typing_import_excluded(self) -> None:
        # typing is covered by IMP002, not IMP001
        assert _check_imp001("from typing import Optional") == []

    def test_relative_import_with_module_flagged(self) -> None:
        assert _check_imp001("from .utils import Helper") == ["IMP001"]

    def test_aliased_from_import_flagged(self) -> None:
        assert _check_imp001("from os.path import join as path_join") == ["IMP001"]

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            from os.path import join
        """)
        tree = ast.parse(source)
        diags = IMP001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_message_contains_name_and_module(self) -> None:
        source = "from os.path import join"
        tree = ast.parse(source)
        diags = IMP001().check(tree, source)
        assert "join" in diags[0].message
        assert "os.path" in diags[0].message


# ---------------------------------------------------------------------------
# IMP002 — typing from-imports
# ---------------------------------------------------------------------------


class TestIMP002:
    def test_import_typing_ok(self) -> None:
        assert _check_imp002("import typing") == []

    def test_import_typing_extensions_ok(self) -> None:
        assert _check_imp002("import typing_extensions") == []

    def test_from_typing_flagged(self) -> None:
        assert _check_imp002("from typing import Optional") == ["IMP002"]

    def test_from_typing_extensions_flagged(self) -> None:
        assert _check_imp002("from typing_extensions import Protocol") == ["IMP002"]

    def test_from_typing_multiple_names_one_diagnostic(self) -> None:
        result = _check_imp002("from typing import Optional, List, Dict")
        assert result == ["IMP002"]

    def test_from_typing_type_checking_flagged(self) -> None:
        # TYPE_CHECKING is a special form but still lives in typing
        assert _check_imp002("from typing import TYPE_CHECKING") == ["IMP002"]

    def test_non_typing_import_not_flagged(self) -> None:
        assert _check_imp002("from os.path import join") == []

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            from typing import Optional
        """)
        tree = ast.parse(source)
        diags = IMP002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_message_contains_name_and_module(self) -> None:
        source = "from typing import Optional"
        tree = ast.parse(source)
        diags = IMP002().check(tree, source)
        assert "Optional" in diags[0].message
        assert "typing" in diags[0].message

    def test_rule_id(self) -> None:
        source = "from typing import Any"
        tree = ast.parse(source)
        diags = IMP002().check(tree, source)
        assert diags[0].rule_id == "IMP002"
