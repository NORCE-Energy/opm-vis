""" Unit tests for opm_vis.pvplot.labels """
import pytest

pytest.importorskip("pyvista")  # importing opm_vis.pvplot at all needs it

from opm_vis.pvplot.labels import (  # noqa: E402
    axis_titles,
    plain_text,
    scalar_bar_title,
    unit,
)
from opm_vis.utils.units import _FIELD, _LAB, _METRIC, _PVT_M, Label  # noqa: E402

# Pure string handling, so no dataset and no rendering is needed here. The private unit tables
# are imported to assert that no mathtext survives for any tabulated mnemonic, which keeps
# this honest if new entries are added to opm_vis.utils.units later.
_ALL_TABLES = {"metric": _METRIC, "field": _FIELD, "lab": _LAB, "pvt-m": _PVT_M}


# ---------------------------------------------------------------------------
# plain_text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (r"kg/m$^3$", "kg/m³"),
        (r"Sm$^3$/Sm$^3$", "Sm³/Sm³"),
        (r"$^\circ$C", "°C"),
        (r"cP-Rm$^3$/day/bar", "cP-Rm³/day/bar"),
        ("mD", "mD"),  # nothing to do
        ("-", "-"),
    ],
)
def test_plain_text_replaces_known_mathtext(raw, expected):
    assert plain_text(raw) == expected


def test_plain_text_degrades_gracefully_for_untabulated_mathtext():
    # Not a pattern we have a Unicode equivalent for; dropping the delimiters beats
    # rendering the raw markup
    assert plain_text(r"m$^7$") == "m^7"


@pytest.mark.parametrize("unit_type, table", _ALL_TABLES.items())
def test_no_mathtext_survives_for_any_tabulated_keyword(unit_type, table):
    label = Label(unit_type)

    for keyword in table:
        assert "$" not in unit(label, keyword)


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_unit_looks_up_the_convention():
    assert unit(Label("metric"), "PRESSURE") == "barsa"
    assert unit(Label("field"), "PRESSURE") == "psia"


def test_unit_is_empty_for_an_untabulated_keyword():
    # Label raises KeyError here; a plot should not die over a missing unit string
    assert unit(Label("metric"), "NOSUCHKW") == ""


def test_unit_is_empty_for_an_unrecognised_convention():
    with pytest.warns(UserWarning):
        assert unit(Label("bogus"), "PRESSURE") == ""


# ---------------------------------------------------------------------------
# scalar_bar_title
# ---------------------------------------------------------------------------


def test_scalar_bar_title_brackets_the_unit():
    assert scalar_bar_title(Label("metric"), "PRESSURE") == "PRESSURE [barsa]"
    assert scalar_bar_title(Label("field"), "OIL_DEN") == "OIL_DEN [lb/ft³]"


def test_scalar_bar_title_omits_empty_brackets():
    assert scalar_bar_title(Label("metric"), "NOSUCHKW") == "NOSUCHKW"


# ---------------------------------------------------------------------------
# axis_titles
# ---------------------------------------------------------------------------


def test_axis_titles_follow_the_unit_convention():
    # opm_vis.plot hard-codes metres for both of these
    assert axis_titles(Label("field")) == ("E(x) [ft]", "N(y) [ft]", "Depth [ft]")
    assert axis_titles(Label("metric")) == ("E(x) [m]", "N(y) [m]", "Depth [m]")


def test_axis_titles_drop_the_unit_when_it_is_unknown():
    with pytest.warns(UserWarning):
        assert axis_titles(Label("bogus")) == ("E(x)", "N(y)", "Depth")
