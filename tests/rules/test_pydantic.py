"""Tests for PDT001 Pydantic rules."""

import ast
import textwrap

from sergey.rules import pydantic


def _check_pdt001(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    return [diag.rule_id for diag in pydantic.PDT001().check(tree, source)]


class TestPDT001:
    # ------------------------------------------------------------------
    # Non-Pydantic classes — never flagged
    # ------------------------------------------------------------------

    def test_plain_class_ok(self) -> None:
        assert _check_pdt001("class Foo: pass") == []

    def test_non_basemodel_subclass_ok(self) -> None:
        assert _check_pdt001("class Foo(Bar): pass") == []

    def test_multiple_non_pydantic_bases_ok(self) -> None:
        assert _check_pdt001("class Foo(Bar, Baz): pass") == []

    # ------------------------------------------------------------------
    # Correct Pydantic models
    # ------------------------------------------------------------------

    def test_frozen_true_ok(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = ConfigDict(frozen=True)
                name: str
        """
        assert _check_pdt001(source) == []

    def test_frozen_false_ok(self) -> None:
        source = """\
            class Draft(BaseModel):
                model_config = ConfigDict(frozen=False)
                body: str
        """
        assert _check_pdt001(source) == []

    def test_frozen_with_other_kwargs_ok(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = ConfigDict(frozen=True, validate_assignment=True)
                name: str
        """
        assert _check_pdt001(source) == []

    def test_qualified_basemodel_ok(self) -> None:
        # pydantic.BaseModel via attribute access
        source = """\
            class User(pydantic.BaseModel):
                model_config = ConfigDict(frozen=True)
                name: str
        """
        assert _check_pdt001(source) == []

    def test_qualified_config_dict_ok(self) -> None:
        # pydantic.ConfigDict via attribute access
        source = """\
            class User(BaseModel):
                model_config = pydantic.ConfigDict(frozen=True)
                name: str
        """
        assert _check_pdt001(source) == []

    def test_annotated_assignment_ok(self) -> None:
        source = """\
            class User(BaseModel):
                model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
                name: str
        """
        assert _check_pdt001(source) == []

    # ------------------------------------------------------------------
    # Missing model_config entirely
    # ------------------------------------------------------------------

    def test_no_model_config_flagged(self) -> None:
        source = """\
            class User(BaseModel):
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    def test_no_model_config_empty_body_flagged(self) -> None:
        assert _check_pdt001("class User(BaseModel): pass") == ["PDT001"]

    def test_annotated_no_value_flagged(self) -> None:
        # Declared but never assigned — treated as absent.
        source = """\
            class User(BaseModel):
                model_config: ClassVar[ConfigDict]
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    # ------------------------------------------------------------------
    # model_config present but not a ConfigDict call
    # ------------------------------------------------------------------

    def test_model_config_not_a_call_flagged(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = {"frozen": True}
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    def test_model_config_bare_variable_flagged(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = MY_CONFIG
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    # ------------------------------------------------------------------
    # ConfigDict call present but frozen not set
    # ------------------------------------------------------------------

    def test_empty_config_dict_flagged(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = ConfigDict()
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    def test_config_dict_without_frozen_flagged(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = ConfigDict(validate_assignment=True)
                name: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    # ------------------------------------------------------------------
    # Multiple classes
    # ------------------------------------------------------------------

    def test_two_bad_models_two_diagnostics(self) -> None:
        source = """\
            class User(BaseModel):
                name: str

            class Item(BaseModel):
                title: str
        """
        assert _check_pdt001(source) == ["PDT001", "PDT001"]

    def test_one_good_one_bad(self) -> None:
        source = """\
            class User(BaseModel):
                model_config = ConfigDict(frozen=True)
                name: str

            class Item(BaseModel):
                title: str
        """
        assert _check_pdt001(source) == ["PDT001"]

    def test_non_pydantic_class_among_models_not_flagged(self) -> None:
        source = """\
            class Helper:
                pass

            class User(BaseModel):
                model_config = ConfigDict(frozen=True)
                name: str
        """
        assert _check_pdt001(source) == []

    # ------------------------------------------------------------------
    # Diagnostic metadata
    # ------------------------------------------------------------------

    def test_rule_id(self) -> None:
        source = "class User(BaseModel): pass"
        tree = ast.parse(source)
        diags = pydantic.PDT001().check(tree, source)
        assert diags[0].rule_id == "PDT001"

    def test_no_config_diagnostic_points_to_class(self) -> None:
        source = textwrap.dedent("""\
            x = 1
            class User(BaseModel):
                name: str
        """)
        tree = ast.parse(source)
        diags = pydantic.PDT001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2

    def test_missing_frozen_diagnostic_points_to_config_dict(self) -> None:
        source = textwrap.dedent("""\
            class User(BaseModel):
                model_config = ConfigDict()
                name: str
        """)
        tree = ast.parse(source)
        diags = pydantic.PDT001().check(tree, source)
        assert len(diags) == 1
        assert diags[0].line == 2  # the ConfigDict() line

    def test_no_config_message_mentions_model_name(self) -> None:
        source = "class User(BaseModel): pass"
        tree = ast.parse(source)
        diags = pydantic.PDT001().check(tree, source)
        assert "`User`" in diags[0].message

    def test_missing_frozen_message_mentions_frozen(self) -> None:
        source = textwrap.dedent("""\
            class User(BaseModel):
                model_config = ConfigDict()
                name: str
        """)
        tree = ast.parse(source)
        diags = pydantic.PDT001().check(tree, source)
        assert "frozen" in diags[0].message
