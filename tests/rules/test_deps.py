"""Tests for IMP005 — optional-dependency import guard rule."""

from __future__ import annotations

import ast
import textwrap
import typing

from sergey.rules import base, deps

if typing.TYPE_CHECKING:
    import pathlib

_OPT_DEPS: frozenset[str] = frozenset({"numpy", "pandas", "my_pkg"})


def _check(source: str, optional_deps: frozenset[str] = _OPT_DEPS) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in deps.IMP005(optional_deps).check(tree, source)]


def _diags(
    source: str,
    optional_deps: frozenset[str] = _OPT_DEPS,
) -> list[base.Diagnostic]:
    tree = ast.parse(textwrap.dedent(source))
    return deps.IMP005(optional_deps).check(tree, source)


# ---------------------------------------------------------------------------
# No optional deps configured → never flag
# ---------------------------------------------------------------------------


class TestNoOptionalDeps:
    def test_empty_deps_no_diagnostics(self) -> None:
        assert _check("import numpy", frozenset()) == []

    def test_empty_deps_from_import_no_diagnostics(self) -> None:
        assert _check("from numpy import array", frozenset()) == []


# ---------------------------------------------------------------------------
# Unguarded imports → flagged
# ---------------------------------------------------------------------------


class TestUnguardedImports:
    def test_plain_import_flagged(self) -> None:
        assert _check("import numpy") == ["IMP005"]

    def test_from_import_flagged(self) -> None:
        assert _check("from numpy import array") == ["IMP005"]

    def test_dotted_import_flagged(self) -> None:
        assert _check("import numpy.linalg") == ["IMP005"]

    def test_from_dotted_import_flagged(self) -> None:
        assert _check("from numpy.linalg import norm") == ["IMP005"]

    def test_aliased_import_flagged(self) -> None:
        assert _check("import numpy as np") == ["IMP005"]

    def test_aliased_from_import_flagged(self) -> None:
        assert _check("from numpy import array as arr") == ["IMP005"]

    def test_two_optional_imports_two_diagnostics(self) -> None:
        source = """\
            import numpy
            import pandas
        """
        assert _check(source) == ["IMP005", "IMP005"]

    def test_non_optional_import_not_flagged(self) -> None:
        assert _check("import os") == []

    def test_non_optional_from_import_not_flagged(self) -> None:
        assert _check("from os import path") == []

    def test_optional_and_non_optional_same_statement(self) -> None:
        # "import numpy, os" — only numpy is optional
        assert _check("import numpy, os") == ["IMP005"]


# ---------------------------------------------------------------------------
# try/except guarded → not flagged
# ---------------------------------------------------------------------------


class TestGuardedImports:
    def test_import_in_try_body_ok(self) -> None:
        source = """\
            try:
                import numpy
            except ImportError:
                numpy = None
        """
        assert _check(source) == []

    def test_from_import_in_try_body_ok(self) -> None:
        source = """\
            try:
                from numpy import array
            except ImportError:
                array = None
        """
        assert _check(source) == []

    def test_import_in_try_body_nested_if_ok(self) -> None:
        source = """\
            try:
                if True:
                    import numpy
            except ImportError:
                numpy = None
        """
        assert _check(source) == []

    def test_import_in_except_handler_flagged(self) -> None:
        # An import inside the except body is NOT protected
        source = """\
            try:
                pass
            except ImportError:
                import numpy
        """
        assert _check(source) == ["IMP005"]

    def test_import_in_finally_flagged(self) -> None:
        source = """\
            try:
                pass
            except ImportError:
                pass
            finally:
                import numpy
        """
        assert _check(source) == ["IMP005"]

    def test_import_in_try_else_flagged(self) -> None:
        source = """\
            try:
                pass
            except ImportError:
                pass
            else:
                import numpy
        """
        assert _check(source) == ["IMP005"]

    def test_multiple_imports_in_try_body_ok(self) -> None:
        source = """\
            try:
                import numpy
                import pandas
            except ImportError:
                pass
        """
        assert _check(source) == []


# ---------------------------------------------------------------------------
# Scope boundaries — functions and classes reset the try context
# ---------------------------------------------------------------------------


class TestScopeBoundaries:
    def test_import_in_function_inside_try_flagged(self) -> None:
        # The function body is a new scope; the enclosing try does not protect it
        source = """\
            try:
                def helper():
                    import numpy
            except ImportError:
                pass
        """
        assert _check(source) == ["IMP005"]

    def test_import_in_function_with_own_try_ok(self) -> None:
        source = """\
            def helper():
                try:
                    import numpy
                except ImportError:
                    numpy = None
        """
        assert _check(source) == []

    def test_import_in_function_without_try_flagged(self) -> None:
        source = """\
            def helper():
                import numpy
        """
        assert _check(source) == ["IMP005"]

    def test_import_in_class_body_flagged(self) -> None:
        source = """\
            class Foo:
                import numpy
        """
        assert _check(source) == ["IMP005"]

    def test_import_in_class_method_with_try_ok(self) -> None:
        source = """\
            class Foo:
                def bar(self):
                    try:
                        import numpy
                    except ImportError:
                        pass
        """
        assert _check(source) == []

    def test_import_outside_try_and_inside_try_both_present(self) -> None:
        # One unguarded, one guarded — only the unguarded one is flagged
        source = """\
            import pandas
            try:
                import numpy
            except ImportError:
                numpy = None
        """
        assert _check(source) == ["IMP005"]


# ---------------------------------------------------------------------------
# Package name normalisation
# ---------------------------------------------------------------------------


class TestNameNormalisation:
    def test_hyphenated_dep_name_normalised(self) -> None:
        # pyproject.toml: "my-pkg", import: "my_pkg"
        assert _check("import my_pkg") == ["IMP005"]

    def test_dotted_submodule_uses_top_level(self) -> None:
        # "numpy.linalg" → top-level "numpy", which is optional
        assert _check("import numpy.linalg") == ["IMP005"]

    def test_from_submodule_uses_top_level(self) -> None:
        assert _check("from numpy.linalg import norm") == ["IMP005"]


# ---------------------------------------------------------------------------
# Multi-name import: "import numpy, pandas" → one diagnostic
# ---------------------------------------------------------------------------


class TestMultiNameImport:
    def test_two_optional_in_one_import_one_diagnostic(self) -> None:
        result = _diags("import numpy, pandas")
        assert len(result) == 1
        assert result[0].rule_id == "IMP005"
        assert "`numpy`" in result[0].message
        assert "`pandas`" in result[0].message

    def test_one_optional_one_stdlib_one_diagnostic(self) -> None:
        result = _diags("import numpy, os")
        assert len(result) == 1
        assert "`numpy`" in result[0].message
        assert "os" not in result[0].message

    def test_repeated_top_level_no_duplicate(self) -> None:
        # import numpy.linalg, numpy.random → top-level "numpy" appears twice
        result = _diags("import numpy.linalg, numpy.random")
        assert len(result) == 1
        assert result[0].message.count("`numpy`") == 1


# ---------------------------------------------------------------------------
# Relative imports — ignored (cannot determine package name statically)
# ---------------------------------------------------------------------------


class TestRelativeImports:
    def test_relative_import_not_flagged(self) -> None:
        assert _check("from . import utils") == []

    def test_relative_dotted_import_not_flagged(self) -> None:
        assert _check("from .sub import helper") == []


# ---------------------------------------------------------------------------
# Diagnostic metadata
# ---------------------------------------------------------------------------


class TestDiagnosticMetadata:
    def test_rule_id(self) -> None:
        result = _diags("import numpy")
        assert result[0].rule_id == "IMP005"

    def test_severity_is_warning(self) -> None:
        result = _diags("import numpy")
        assert result[0].severity == base.Severity.WARNING

    def test_line_number(self) -> None:
        source = textwrap.dedent("""\
            import os
            import numpy
        """)
        result = _diags(source)
        assert len(result) == 1
        assert result[0].line == 2

    def test_message_contains_package_name(self) -> None:
        result = _diags("import numpy")
        assert "`numpy`" in result[0].message

    def test_message_mentions_try_except(self) -> None:
        result = _diags("import numpy")
        assert "try/except" in result[0].message

    def test_no_fix_attached(self) -> None:
        result = _diags("import numpy")
        assert result[0].fix is None


# ---------------------------------------------------------------------------
# _parse_dep_name helper
# ---------------------------------------------------------------------------


class TestParseDepName:
    def test_plain_name(self) -> None:
        assert deps._parse_dep_name("numpy") == "numpy"

    def test_version_specifier(self) -> None:
        assert deps._parse_dep_name("numpy>=1.0") == "numpy"

    def test_complex_specifier(self) -> None:
        assert deps._parse_dep_name("numpy>=1.0,<2.0") == "numpy"

    def test_extras(self) -> None:
        assert deps._parse_dep_name("my-pkg[extra]") == "my_pkg"

    def test_environment_marker(self) -> None:
        assert deps._parse_dep_name("numpy; python_version>'3.8'") == "numpy"

    def test_hyphen_to_underscore(self) -> None:
        assert deps._parse_dep_name("my-package") == "my_package"

    def test_uppercase_lowercased(self) -> None:
        assert deps._parse_dep_name("NumPy") == "numpy"


# ---------------------------------------------------------------------------
# _load_optional_deps — integration with a real pyproject.toml
# ---------------------------------------------------------------------------


class TestLoadOptionalDeps:
    def test_reads_optional_dependencies(self, tmp_path: pathlib.Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project.optional-dependencies]\nviz = ["matplotlib>=3.0", "seaborn"]\n'
        )
        result = deps._load_optional_deps(pyproject)
        assert "matplotlib" in result
        assert "seaborn" in result

    def test_excludes_dev_dependency_group(self, tmp_path: pathlib.Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[dependency-groups]\ndev = ["pytest", "ruff"]\n'
            '[project.optional-dependencies]\nviz = ["matplotlib"]\n'
        )
        result = deps._load_optional_deps(pyproject)
        assert "matplotlib" in result
        assert "pytest" not in result
        assert "ruff" not in result

    def test_includes_non_dev_dependency_groups(self, tmp_path: pathlib.Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[dependency-groups]\ndev = ["pytest"]\nviz = ["matplotlib"]\n'
        )
        result = deps._load_optional_deps(pyproject)
        assert "matplotlib" in result
        assert "pytest" not in result

    def test_reads_both_sources(self, tmp_path: pathlib.Path) -> None:
        # Both [project.optional-dependencies] and [dependency-groups] non-dev
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project.optional-dependencies]\nspeed = ["orjson"]\n'
            '[dependency-groups]\ndev = ["pytest"]\nextra = ["httpx"]\n'
        )
        result = deps._load_optional_deps(pyproject)
        assert "orjson" in result
        assert "httpx" in result
        assert "pytest" not in result

    def test_empty_section_returns_empty(self, tmp_path: pathlib.Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'my-pkg'\n")
        result = deps._load_optional_deps(pyproject)
        assert result == frozenset()

    def test_missing_file_returns_empty(self, tmp_path: pathlib.Path) -> None:
        missing = tmp_path / "nonexistent.toml"
        result = deps._load_optional_deps(missing)
        assert result == frozenset()
