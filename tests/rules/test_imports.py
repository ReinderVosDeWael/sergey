"""Tests for IMP001, IMP002, IMP003, and IMP004 import-style rules."""

import ast
import textwrap

from sergey.rules import base, imports


def _check_imp001(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP001().check(tree, source)]


def _check_imp002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP002().check(tree, source)]


def _check_imp003(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP003().check(tree, source)]


def _check_imp004(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP004().check(tree, source)]


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

    def test_submodule_import_ok(self) -> None:
        # os.path is a real submodule of os — should not be flagged
        assert _check_imp001("from os import path") == []

    def test_submodule_and_class_mixed(self) -> None:
        # path is a submodule (ok), getcwd is a function (bad) — one diagnostic
        # mentioning only getcwd
        source = "from os import path, getcwd"
        tree = ast.parse(source)
        diags = imports.IMP001().check(tree, source)
        assert len(diags) == 1
        assert "getcwd" in diags[0].message
        assert "path" not in diags[0].message

    def test_future_import_excluded(self) -> None:
        assert _check_imp001("from __future__ import annotations") == []

    def test_typing_import_excluded(self) -> None:
        # typing is covered by IMP002, not IMP001
        assert _check_imp001("from typing import Optional") == []

    def test_typing_extensions_import_excluded(self) -> None:
        # typing_extensions is covered by IMP002, not IMP001
        assert _check_imp001("from typing_extensions import Protocol") == []

    def test_collections_abc_import_excluded(self) -> None:
        # collections.abc is covered by IMP004, not IMP001
        assert _check_imp001("from collections.abc import Mapping") == []

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
        diags = imports.IMP001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_message_contains_name_and_module(self) -> None:
        source = "from os.path import join"
        tree = ast.parse(source)
        diags = imports.IMP001().check(tree, source)
        assert "join" in diags[0].message
        assert "os.path" in diags[0].message


# ---------------------------------------------------------------------------
# IMP001 — auto-fix
# ---------------------------------------------------------------------------


def _fix_imp001(source: str) -> list[base.Fix | None]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.fix for diag in imports.IMP001().check(tree, source)]


class TestIMP001Fix:
    def test_simple_absolute_import_fix(self) -> None:
        fixes = _fix_imp001("from os.path import join")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os.path"

    def test_top_level_module_fix(self) -> None:
        fixes = _fix_imp001("from collections import OrderedDict")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "import collections"

    def test_multiple_bad_names_one_import(self) -> None:
        fixes = _fix_imp001("from os.path import join, exists, dirname")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os.path"

    def test_aliased_bad_name_fix(self) -> None:
        fixes = _fix_imp001("from os.path import join as path_join")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os.path"

    def test_mixed_good_and_bad_aliases_fix(self) -> None:
        # path is a submodule (kept), getcwd is a function (flagged)
        fixes = _fix_imp001("from os import path, getcwd")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path\nimport os"

    def test_relative_import_with_module_fix(self) -> None:
        fixes = _fix_imp001("from .utils import Helper")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from . import utils"

    def test_relative_import_double_dot_fix(self) -> None:
        fixes = _fix_imp001("from ..models import User")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from .. import models"

    def test_relative_import_nested_module_fix(self) -> None:
        fixes = _fix_imp001("from .pkg.sub import MyClass")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from .pkg import sub"

    def test_indented_import_fix_preserves_indent(self) -> None:
        source = textwrap.dedent("""\
            def f():
                from os.path import join
        """)
        tree = ast.parse(source)
        diags = imports.IMP001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].fix is not None
        assert diags[0].fix.replacement == "import os.path"

    def test_no_fix_for_bare_relative_import(self) -> None:
        # from . import X has no module component — cannot determine fix
        fixes = _fix_imp001("from . import SomeClass")
        assert len(fixes) == 1
        assert fixes[0] is None

    def test_two_flagged_statements_two_fixes(self) -> None:
        source = textwrap.dedent("""\
            from os.path import join
            from collections import OrderedDict
        """)
        fixes = _fix_imp001(source)
        assert len(fixes) == 2
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os.path"
        assert fixes[1] is not None
        assert fixes[1].replacement == "import collections"


# ---------------------------------------------------------------------------
# IMP002 — typing from-imports
# ---------------------------------------------------------------------------


class TestIMP002:
    def test_from_typing_ok(self) -> None:
        assert _check_imp002("from typing import Optional") == []

    def test_from_typing_extensions_ok(self) -> None:
        assert _check_imp002("from typing_extensions import Protocol") == []

    def test_from_typing_multiple_names_ok(self) -> None:
        assert _check_imp002("from typing import Optional, List, Dict") == []

    def test_from_typing_type_checking_ok(self) -> None:
        assert _check_imp002("from typing import TYPE_CHECKING") == []

    def test_import_typing_flagged(self) -> None:
        assert _check_imp002("import typing") == ["IMP002"]

    def test_import_typing_extensions_flagged(self) -> None:
        assert _check_imp002("import typing_extensions") == ["IMP002"]

    def test_non_typing_import_not_flagged(self) -> None:
        assert _check_imp002("import os") == []

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            import typing
        """)
        tree = ast.parse(source)
        diags = imports.IMP002().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_diagnostic_message_contains_module(self) -> None:
        source = "import typing"
        tree = ast.parse(source)
        diags = imports.IMP002().check(tree, source)
        assert "typing" in diags[0].message

    def test_rule_id(self) -> None:
        source = "import typing"
        tree = ast.parse(source)
        diags = imports.IMP002().check(tree, source)
        assert diags[0].rule_id == "IMP002"


# ---------------------------------------------------------------------------
# IMP003 — dotted plain imports
# ---------------------------------------------------------------------------


class TestIMP003:
    def test_plain_import_ok(self) -> None:
        assert _check_imp003("import os") == []

    def test_plain_import_multiple_ok(self) -> None:
        assert _check_imp003("import os, sys, re") == []

    def test_dotted_import_flagged(self) -> None:
        assert _check_imp003("import os.path") == ["IMP003"]

    def test_deep_dotted_import_flagged(self) -> None:
        assert _check_imp003("import importlib.util") == ["IMP003"]

    def test_aliased_dotted_import_flagged(self) -> None:
        assert _check_imp003("import os.path as ospath") == ["IMP003"]

    def test_mixed_one_dotted_one_plain(self) -> None:
        # os.path is dotted (flagged), sys is plain (ok) — one diagnostic
        assert _check_imp003("import os.path, sys") == ["IMP003"]

    def test_two_dotted_imports_two_diagnostics(self) -> None:
        assert _check_imp003("import os.path, importlib.util") == ["IMP003", "IMP003"]

    def test_from_import_not_flagged(self) -> None:
        # IMP003 only checks ast.Import nodes, not ast.ImportFrom
        assert _check_imp003("from os import path") == []

    def test_diagnostic_suggests_from_import(self) -> None:
        source = "import os.path"
        tree = ast.parse(source)
        diags = imports.IMP003().check(tree, source)
        assert len(diags) == 1
        assert "from os import path" in diags[0].message

    def test_diagnostic_suggests_correct_parent_for_deep_import(self) -> None:
        source = "import importlib.util"
        tree = ast.parse(source)
        diags = imports.IMP003().check(tree, source)
        assert "from importlib import util" in diags[0].message

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            import os.path
        """)
        tree = ast.parse(source)
        diags = imports.IMP003().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_rule_id(self) -> None:
        source = "import os.path"
        tree = ast.parse(source)
        diags = imports.IMP003().check(tree, source)
        assert diags[0].rule_id == "IMP003"

    def test_collections_abc_excluded(self) -> None:
        # collections.abc is covered by IMP004, not IMP003
        assert _check_imp003("import collections.abc") == []


# ---------------------------------------------------------------------------
# IMP003 — auto-fix
# ---------------------------------------------------------------------------


def _fix_imp003(source: str) -> list[base.Fix | None]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.fix for diag in imports.IMP003().check(tree, source)]


class TestIMP003Fix:
    def test_simple_dotted_import_fix(self) -> None:
        fixes = _fix_imp003("import os.path")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path"

    def test_deep_dotted_import_fix(self) -> None:
        fixes = _fix_imp003("import importlib.util")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from importlib import util"

    def test_aliased_dotted_import_fix(self) -> None:
        fixes = _fix_imp003("import os.path as ospath")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path as ospath"

    def test_multiple_dotted_imports_same_fix(self) -> None:
        # Both diagnostics carry the same fix (the full node replacement).
        fixes = _fix_imp003("import os.path, importlib.util")
        assert len(fixes) == 2
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path\nfrom importlib import util"
        assert fixes[1] is not None
        assert fixes[1].replacement == fixes[0].replacement

    def test_mixed_dotted_and_plain_fix(self) -> None:
        # os.path is dotted (flagged), sys is plain (kept as-is in replacement).
        fixes = _fix_imp003("import os.path, sys")
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path\nimport sys"

    def test_indented_import_fix_preserves_indent(self) -> None:
        # Indented import inside a function — subsequent lines must keep the indent.
        source = textwrap.dedent("""\
            def f():
                import os.path, importlib.util
        """)
        tree = ast.parse(source)
        diags = imports.IMP003().check(tree, source)
        assert len(diags) == 2
        assert diags[0].fix is not None
        expected = "from os import path\n    from importlib import util"
        assert diags[0].fix.replacement == expected

    def test_no_fix_for_plain_import(self) -> None:
        # Plain (non-dotted) import produces no IMP003 diagnostics at all.
        fixes = _fix_imp003("import os")
        assert fixes == []


# ---------------------------------------------------------------------------
# IMP004 — collections.abc plain imports
# ---------------------------------------------------------------------------


class TestIMP004:
    def test_from_collections_abc_ok(self) -> None:
        assert _check_imp004("from collections.abc import Mapping") == []

    def test_from_collections_abc_multiple_names_ok(self) -> None:
        assert _check_imp004("from collections.abc import Callable, Sequence") == []

    def test_import_collections_not_flagged(self) -> None:
        assert _check_imp004("import collections") == []

    def test_import_collections_abc_flagged(self) -> None:
        assert _check_imp004("import collections.abc") == ["IMP004"]

    def test_diagnostic_message(self) -> None:
        source = "import collections.abc"
        tree = ast.parse(source)
        diags = imports.IMP004().check(tree, source)
        assert len(diags) == 1
        assert "from collections.abc import ..." in diags[0].message
        assert "import collections.abc" in diags[0].message

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            import collections.abc
        """)
        tree = ast.parse(source)
        diags = imports.IMP004().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_rule_id(self) -> None:
        source = "import collections.abc"
        tree = ast.parse(source)
        diags = imports.IMP004().check(tree, source)
        assert diags[0].rule_id == "IMP004"
