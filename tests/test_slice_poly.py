""" Unit tests for opm_vis.plot.slice_poly's calculator support, backed by SPE1CASE1 """
import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.plot.slice_poly import SlicePoly2D

# The case1/data_dir fixtures come from conftest.py. SPE1CASE1 is a fully active,
# standard-oriented 10x10x3 Cartesian box grid (no inactive cells, no NaNs).


@pytest.fixture(scope="module")
def real_egrid(data_dir):
    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


@pytest.fixture
def slc(case1):
    return SlicePoly2D([case1], "k", 0)


def test_read_calc_mean_matches_manual_column_average(slc, case1, real_egrid):
    from opm_vis.utils.restart import RestartReader

    full_data = RestartReader([case1]).read("PRESSURE", 60)
    aggregated = slc._read_calc("PRESSURE", 60, "mean", None)

    nx, ny, _ = real_egrid.dimension
    expected = []
    for act in slc.active_indices():
        i, j, _ = real_egrid.ijk_from_active_index(act)
        column = [full_data[real_egrid.active_index(i, j, k)] for k in range(3)]
        expected.append(np.mean(column))

    # rtol left loose: restart data is float32, and the two code paths sum in a different
    # order, so bit-for-bit equality isn't expected.
    np.testing.assert_allclose(aggregated, expected, rtol=1e-6)


def test_read_calc_count_of_one_matches_the_slice_s_own_values(slc, case1):
    plain = slc._read_keyword("PRESSURE", 60, slc.active_indices())
    aggregated = slc._read_calc("PRESSURE", 60, "sum", 1)

    np.testing.assert_allclose(aggregated, plain)


def test_generate_with_calc_kind_sets_the_aggregated_array(slc):
    polyc = slc.generate("PRESSURE", 60, calc_kind="mean")

    expected = slc._read_calc("PRESSURE", 60, "mean", None)
    np.testing.assert_allclose(polyc.get_array(), expected)


def test_generate_calc_kind_combines_with_diff(slc):
    polyc = slc.generate("PRESSURE", 60, calc_kind="mean", diff_rstep=0)

    current = slc._read_calc("PRESSURE", 60, "mean", None)
    reference = slc._read_calc("PRESSURE", 0, "mean", None)
    np.testing.assert_allclose(polyc.get_array(), current - reference)
