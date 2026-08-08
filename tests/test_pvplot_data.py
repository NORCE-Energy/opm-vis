""" Unit tests for opm_vis.pvplot.data, backed by the SPE1CASE1 test dataset """
import numpy as np
import pytest

from opm_vis.pvplot.data import CaseData

# The case1 fixture comes from conftest.py. SPE1CASE1 is a fully active 10x10x3 grid in field
# units with 121 report steps. PRESSURE, RS, SGAS and SWAT appear in both its restart files
# and its .INIT file, with different values, which is what makes the restart-over-INIT
# priority rule observable here.


@pytest.fixture(scope="module")
def case(case1):
    return CaseData([case1])


# ---------------------------------------------------------------------------
# read / is_static
# ---------------------------------------------------------------------------


def test_read_returns_one_value_per_active_cell(case):
    sgas = case.read("SGAS", 60)

    assert sgas.shape == (300,)  # 10x10x3, fully active


def test_read_falls_back_to_the_init_file(case):
    poro = case.read("PORO", 60)

    assert poro.shape == (300,)
    np.testing.assert_allclose(poro[0], 0.3)


def test_read_prefers_the_restart_file_over_the_init_file(case):
    from_case = case.read("PRESSURE", 60)

    # The .INIT copy of PRESSURE is only the initial state, so it must not win
    np.testing.assert_allclose(from_case, case.restart.read("PRESSURE", 60))
    assert not np.allclose(from_case, case.static.read("PRESSURE"))


def test_read_raises_for_an_unknown_keyword(case):
    with pytest.raises(KeyError, match="not in restart files or .INIT file"):
        case.read("NOSUCHKW", 60)


def test_is_static_distinguishes_dynamic_from_init_keywords(case):
    assert case.is_static("PORO", 60) is True
    assert case.is_static("SGAS", 60) is False


# ---------------------------------------------------------------------------
# unit_convention / wells
# ---------------------------------------------------------------------------


def test_unit_convention_is_read_from_the_restart_header(case):
    assert case.unit_convention() == "field"


def test_wells_are_built_lazily(case1):
    case = CaseData([case1])

    assert case._wells is None  # walking every report step is not free
    assert set(case.wells[60]) == {"PROD", "INJ"}
    assert case.wells is case.wells


def test_report_dates_span_the_run(case):
    assert case.report.report_steps() == list(range(121))
