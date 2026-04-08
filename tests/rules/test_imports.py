"""Tests for IMP002, IMP003, IMP004, and IMP005 import-style rules."""

import ast
import textwrap

from sergey.rules import base, imports


def _check_imp002(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP002().check(tree, source)]


def _check_imp003(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP003().check(tree, source)]


def _check_imp004(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP004().check(tree, source)]


def _check_imp005(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in imports.IMP005().check(tree, source)]


def _diags_imp005(source: str) -> list[base.Diagnostic]:
    tree = ast.parse(textwrap.dedent(source))
    return imports.IMP005().check(tree, source)


def _fix_imp005(source: str) -> list[base.Fix | None]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.fix for diag in imports.IMP005().check(tree, source)]


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
# IMP002 — auto-fix
# ---------------------------------------------------------------------------


def _fix_imp002(source: str) -> list[base.Fix | None]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.fix for diag in imports.IMP002().check(tree, source)]


def _diags_imp002(source: str) -> list[base.Diagnostic]:
    tree = ast.parse(textwrap.dedent(source))
    return imports.IMP002().check(tree, source)


class TestIMP002Fix:
    def test_simple_typing_import_fix(self) -> None:
        source = textwrap.dedent("""\
            import typing
            x: typing.Optional[str]
        """)
        fixes = _fix_imp002(source)
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from typing import Optional"

    def test_multiple_attrs_sorted(self) -> None:
        source = textwrap.dedent("""\
            import typing
            x: typing.Optional[str]
            y: typing.Dict[str, int]
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from typing import Dict, Optional"

    def test_reference_rewrite(self) -> None:
        source = textwrap.dedent("""\
            import typing
            x: typing.Optional[str]
        """)
        diags = _diags_imp002(source)
        assert len(diags) == 1
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "Optional"
        assert edits[0].line == 2

    def test_reference_rewrite_multiple_refs(self) -> None:
        source = textwrap.dedent("""\
            import typing
            x: typing.Optional[str]
            y: typing.Optional[int]
        """)
        diags = _diags_imp002(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 2
        assert all(e.replacement == "Optional" for e in edits)

    def test_with_alias(self) -> None:
        source = textwrap.dedent("""\
            import typing as t
            x: t.Optional[str]
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from typing import Optional"
        edits = fixes[0].additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "Optional"

    def test_typing_extensions(self) -> None:
        source = textwrap.dedent("""\
            import typing_extensions
            x: typing_extensions.Protocol
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from typing_extensions import Protocol"

    def test_no_fix_when_unsafe_usage(self) -> None:
        # bare `typing` used as a value — cannot safely fix
        source = textwrap.dedent("""\
            import typing
            x = typing
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is None

    def test_no_fix_when_no_attr_refs(self) -> None:
        # typing imported but never accessed as attribute
        source = "import typing\n"
        fixes = _fix_imp002(source)
        assert fixes[0] is None

    def test_no_fix_on_name_conflict(self) -> None:
        source = textwrap.dedent("""\
            import typing
            Optional = str
            x: typing.Optional[str]
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is None

    def test_multi_alias_node_fixes_both(self) -> None:
        # import typing, typing_extensions — fix covers both
        source = textwrap.dedent("""\
            import typing, typing_extensions
            x: typing.Optional[str]
            y: typing_extensions.Protocol
        """)
        diags = _diags_imp002(source)
        # Two diagnostics (one per alias), both share the same fix
        assert len(diags) == 2
        fix = diags[0].fix
        assert fix is not None
        assert fix is diags[1].fix
        assert "from typing import Optional" in fix.replacement
        assert "from typing_extensions import Protocol" in fix.replacement

    def test_mixed_typing_and_plain_import(self) -> None:
        source = textwrap.dedent("""\
            import typing, os
            x: typing.Optional[str]
        """)
        fixes = _fix_imp002(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from typing import Optional\nimport os"

    def test_indented_import_preserves_indent(self) -> None:
        source = textwrap.dedent("""\
            def f():
                import typing
                x: typing.Optional[str]
        """)
        diags = _diags_imp002(source)
        assert diags[0].fix is not None
        assert diags[0].fix.replacement == "from typing import Optional"


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


# ---------------------------------------------------------------------------
# IMP004 — auto-fix
# ---------------------------------------------------------------------------


def _fix_imp004(source: str) -> list[base.Fix | None]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.fix for diag in imports.IMP004().check(tree, source)]


def _diags_imp004(source: str) -> list[base.Diagnostic]:
    tree = ast.parse(textwrap.dedent(source))
    return imports.IMP004().check(tree, source)


class TestIMP004Fix:
    def test_no_alias_fix(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc
            x: collections.abc.Mapping
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from collections.abc import Mapping"

    def test_no_alias_reference_rewrite(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc
            x: collections.abc.Mapping
        """)
        diags = _diags_imp004(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "Mapping"
        assert edits[0].line == 2

    def test_no_alias_multiple_names(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc
            x: collections.abc.Mapping
            y: collections.abc.Callable
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from collections.abc import Callable, Mapping"

    def test_with_alias_fix(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc as abc
            x: abc.Mapping
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from collections.abc import Mapping"

    def test_with_alias_reference_rewrite(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc as abc
            x: abc.Mapping
        """)
        diags = _diags_imp004(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "Mapping"

    def test_no_fix_when_unsafe_usage_no_alias(self) -> None:
        # bare collections used as a value
        source = textwrap.dedent("""\
            import collections.abc
            x = collections
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is None

    def test_no_fix_when_intermediate_unsafe_no_alias(self) -> None:
        # collections.abc used without further attribute access
        source = textwrap.dedent("""\
            import collections.abc
            x = collections.abc
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is None

    def test_no_fix_when_unsafe_usage_with_alias(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc as abc
            x = abc
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is None

    def test_no_fix_when_no_attr_refs(self) -> None:
        source = "import collections.abc\n"
        fixes = _fix_imp004(source)
        assert fixes[0] is None

    def test_no_fix_on_name_conflict(self) -> None:
        source = textwrap.dedent("""\
            import collections.abc
            Mapping = dict
            x: collections.abc.Mapping
        """)
        fixes = _fix_imp004(source)
        assert fixes[0] is None

    def test_indented_import_preserves_indent(self) -> None:
        source = textwrap.dedent("""\
            def f():
                import collections.abc
                x: collections.abc.Mapping
        """)
        diags = _diags_imp004(source)
        assert diags[0].fix is not None
        assert diags[0].fix.replacement == "from collections.abc import Mapping"


# ---------------------------------------------------------------------------
# IMP005 — plain imports used via submodule attribute access
# ---------------------------------------------------------------------------


class TestIMP005:
    def test_plain_import_no_submodule_access_ok(self) -> None:
        # import os; os.getcwd() — getcwd is not a submodule
        assert _check_imp005("import os\nos.getcwd()") == []

    def test_plain_import_not_used_ok(self) -> None:
        assert _check_imp005("import os") == []

    def test_from_import_ok(self) -> None:
        assert _check_imp005("from os import path") == []

    def test_dotted_import_not_flagged_by_imp005(self) -> None:
        # import os.path is an IMP003 violation, not IMP005
        assert _check_imp005("import os.path\nos.path.join('a', 'b')") == []

    def test_submodule_access_flagged(self) -> None:
        # os.path is a real submodule of os
        source = "import os\nos.path.join('a', 'b')"
        assert _check_imp005(source) == ["IMP005"]

    def test_message_contains_module_and_submodule(self) -> None:
        source = "import os\nos.path.join('a', 'b')"
        tree = ast.parse(source)
        diags = imports.IMP005().check(tree, source)
        assert len(diags) == 1
        assert "from os import path" in diags[0].message
        assert "os" in diags[0].message

    def test_rule_id(self) -> None:
        source = "import os\nos.path.join('a', 'b')"
        tree = ast.parse(source)
        diags = imports.IMP005().check(tree, source)
        assert diags[0].rule_id == "IMP005"

    def test_diagnostic_line_number(self) -> None:
        source = textwrap.dedent("""\
            import sys
            import os
            os.path.join('a', 'b')
        """)
        tree = ast.parse(source)
        diags = imports.IMP005().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_multiple_submodules_one_diagnostic(self) -> None:
        # Both os.path and os.stat are submodules — one diagnostic per import
        source = textwrap.dedent("""\
            import importlib
            importlib.util.find_spec('os')
            importlib.abc.Loader
        """)
        diags = _diags_imp005(source)
        assert len(diags) == 1
        assert "util" in diags[0].message
        assert "abc" in diags[0].message

    def test_aliased_import_flagged(self) -> None:
        source = "import os as operating_system\noperating_system.path.join('a', 'b')"
        assert _check_imp005(source) == ["IMP005"]

    def test_aliased_import_message_uses_module_name(self) -> None:
        source = "import os as operating_system\noperating_system.path.join('a', 'b')"
        tree = ast.parse(source)
        diags = imports.IMP005().check(tree, source)
        assert "from os import path" in diags[0].message

    def test_two_imports_both_violating(self) -> None:
        source = textwrap.dedent("""\
            import os
            import importlib
            os.path.join('a', 'b')
            importlib.util.find_spec('os')
        """)
        assert _check_imp005(source) == ["IMP005", "IMP005"]

    def test_multi_alias_import_only_violating_flagged(self) -> None:
        # import os, sys — only os has a submodule access
        source = textwrap.dedent("""\
            import os, sys
            os.path.join('a', 'b')
            sys.argv
        """)
        diags = _diags_imp005(source)
        assert len(diags) == 1
        assert "os" in diags[0].message


# ---------------------------------------------------------------------------
# IMP005 — auto-fix
# ---------------------------------------------------------------------------


class TestIMP005Fix:
    def test_simple_submodule_fix(self) -> None:
        source = textwrap.dedent("""\
            import os
            os.path.join('a', 'b')
        """)
        fixes = _fix_imp005(source)
        assert len(fixes) == 1
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path"

    def test_reference_rewrite(self) -> None:
        source = textwrap.dedent("""\
            import os
            os.path.join('a', 'b')
        """)
        diags = _diags_imp005(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "path"
        assert edits[0].line == 2

    def test_multiple_refs_rewritten(self) -> None:
        source = textwrap.dedent("""\
            import os
            os.path.join('a', 'b')
            os.path.exists('/tmp')
        """)
        diags = _diags_imp005(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 2
        assert all(e.replacement == "path" for e in edits)

    def test_multiple_submodules_fix(self) -> None:
        source = textwrap.dedent("""\
            import importlib
            importlib.util.find_spec('os')
            importlib.abc.Loader
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from importlib import abc, util"

    def test_multiple_submodule_refs_rewritten(self) -> None:
        source = textwrap.dedent("""\
            import importlib
            importlib.util.find_spec('os')
            importlib.abc.Loader
        """)
        diags = _diags_imp005(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 2
        replacements = {e.replacement for e in edits}
        assert replacements == {"util", "abc"}

    def test_keeps_import_when_non_submodule_access(self) -> None:
        # os.getcwd() is not a submodule — keep import os, add from os import path
        source = textwrap.dedent("""\
            import os
            os.getcwd()
            os.path.join('a', 'b')
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os\nfrom os import path"

    def test_keeps_import_when_bare_name_used(self) -> None:
        source = textwrap.dedent("""\
            import os
            x = os
            os.path.join('a', 'b')
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "import os\nfrom os import path"

    def test_aliased_import_fix(self) -> None:
        source = textwrap.dedent("""\
            import os as operating_system
            operating_system.path.join('a', 'b')
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path"

    def test_aliased_import_reference_rewrite(self) -> None:
        source = textwrap.dedent("""\
            import os as operating_system
            operating_system.path.join('a', 'b')
        """)
        diags = _diags_imp005(source)
        assert diags[0].fix is not None
        edits = diags[0].fix.additional_edits
        assert len(edits) == 1
        assert edits[0].replacement == "path"

    def test_no_fix_on_name_conflict(self) -> None:
        source = textwrap.dedent("""\
            import os
            path = '/tmp'
            os.path.join('a', 'b')
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is None

    def test_multi_alias_import_fix(self) -> None:
        # import os, sys — only os violates; sys kept as-is in replacement
        # aliases are emitted in their original order: os (violating) then sys (kept)
        source = textwrap.dedent("""\
            import os, sys
            os.path.join('a', 'b')
            sys.argv
        """)
        fixes = _fix_imp005(source)
        assert fixes[0] is not None
        assert fixes[0].replacement == "from os import path\nimport sys"

    def test_indented_fix_preserves_indent(self) -> None:
        source = textwrap.dedent("""\
            def f():
                import os
                os.path.join('a', 'b')
        """)
        diags = _diags_imp005(source)
        assert len(diags) == 1
        assert diags[0].fix is not None
        assert diags[0].fix.replacement == "from os import path"

    def test_indented_fix_with_non_submodule_preserves_indent(self) -> None:
        source = textwrap.dedent("""\
            def f():
                import os
                os.getcwd()
                os.path.join('a', 'b')
        """)
        diags = _diags_imp005(source)
        assert len(diags) == 1
        assert diags[0].fix is not None
        assert diags[0].fix.replacement == "import os\n    from os import path"
