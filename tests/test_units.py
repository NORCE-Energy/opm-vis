""" Unit tests for opm_vis.utils.units """
import pytest

from opm_vis.utils.units import _FIELD, _METRIC, Label, summary_unit_label

# ---------------------------------------------------------------------------
# Label (grid keywords, unit convention driven)
# ---------------------------------------------------------------------------


def test_label_looks_up_a_metric_keyword():
    assert Label("metric")("PRESSURE") == "barsa"


def test_label_looks_up_a_field_keyword():
    assert Label("field")("PRESSURE") == "psia"


def test_label_is_case_insensitive_in_the_convention():
    assert Label("METRIC")("PRESSURE") == "barsa"


def test_label_warns_for_an_unknown_convention():
    with pytest.warns(UserWarning, match="No label made"):
        assert Label("nonsense")("PRESSURE") == "UNKNOWN"


def test_unit_convention_returns_the_convention():
    assert Label("Field").unit_convention() == "field"


# ---------------------------------------------------------------------------
# summary_unit_label (summary vectors, unit string driven)
# ---------------------------------------------------------------------------


def test_summary_unit_label_renders_a_rate():
    assert summary_unit_label("STB/DAY") == "stb/day"


def test_summary_unit_label_renders_an_empty_unit_as_dimensionless():
    assert summary_unit_label("") == "-"


def test_summary_unit_label_ignores_surrounding_whitespace():
    assert summary_unit_label("  ") == "-"


def test_summary_unit_label_keeps_a_multiplication_separator():
    assert summary_unit_label("CP*RM3/DAY/BAR") == r"cP*Rm$^3$/day/bar"


def test_summary_unit_label_matches_the_metric_table():
    # The token spellings have to agree with the hand-written grid tables, or the same physical
    # unit would be written two different ways in one figure
    assert summary_unit_label("SM3/SM3") == _METRIC["RS"]


def test_summary_unit_label_matches_the_field_table():
    assert summary_unit_label("MSCF/STB") == _FIELD["RS"]


def test_summary_unit_label_passes_an_unknown_token_through():
    # UDQ vectors carry whatever unit string the deck gave them, so this must not warn or fail
    assert summary_unit_label("WIDGETS/DAY") == "WIDGETS/day"
