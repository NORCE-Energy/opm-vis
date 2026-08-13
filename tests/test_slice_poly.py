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


def test_read_calc_count_of_one_adds_the_next_layer_to_the_slice_itself(slc, case1, real_egrid):
    # SPE1CASE1 has 3 k-layers; slc is at k=0 (0-based). count=1 must aggregate k=0 and k=1 -
    # both the slice itself and the next layer - differing from both the slice's own plain
    # values and from the full (no-count) aggregate across all 3 layers.
    from opm_vis.utils.restart import RestartReader

    full_data = RestartReader([case1]).read("PRESSURE", 60)
    plain = slc._read_keyword("PRESSURE", 60, slc.active_indices())
    full_range = slc._read_calc("PRESSURE", 60, "sum", None)
    aggregated = slc._read_calc("PRESSURE", 60, "sum", 1)

    assert not np.allclose(aggregated, plain)
    assert not np.allclose(aggregated, full_range)

    expected = []
    for act in slc.active_indices():
        i, j, _ = real_egrid.ijk_from_active_index(act)
        act1 = real_egrid.active_index(i, j, 1)
        expected.append(full_data[act] + full_data[act1])

    np.testing.assert_allclose(aggregated, expected)


def test_generate_with_calc_kind_sets_the_aggregated_array(slc):
    polyc = slc.generate("PRESSURE", 60, calc_kind="mean")

    expected = slc._read_calc("PRESSURE", 60, "mean", None)
    np.testing.assert_allclose(polyc.get_array(), expected)


def test_generate_calc_kind_combines_with_diff_plain(slc):
    # "plain" diff (current - reference) commutes with mean/sum, so this holds under either
    # ordering - it is not on its own proof of which one generate() actually does; see
    # test_read_calc_diff_first_then_aggregate_matches_manual_computation for that.
    polyc = slc.generate("PRESSURE", 60, calc_kind="mean", diff_rstep=0)

    current = slc._read_calc("PRESSURE", 60, "mean", None)
    reference = slc._read_calc("PRESSURE", 0, "mean", None)
    np.testing.assert_allclose(polyc.get_array(), current - reference)


def test_read_calc_diff_first_then_aggregate_matches_manual_computation(slc, case1, real_egrid):
    from opm_vis.utils.restart import RestartReader

    restart = RestartReader([case1])
    current = restart.read("PRESSURE", 60)
    reference = restart.read("PRESSURE", 0)
    per_cell_relative = (current - reference) / reference * 100.0

    aggregated = slc._read_calc(
        "PRESSURE", 60, "mean", None, diff_rstep=0, diff_kind="relative"
    )

    nx, ny, _ = real_egrid.dimension
    expected = []
    for act in slc.active_indices():
        i, j, _ = real_egrid.ijk_from_active_index(act)
        column = [per_cell_relative[real_egrid.active_index(i, j, k)] for k in range(3)]
        expected.append(np.mean(column))

    np.testing.assert_allclose(aggregated, expected, rtol=1e-5)

    # "relative" is nonlinear, so diffing first then averaging must differ from averaging
    # first then relative-differencing the two averages - the ordering this feature does NOT
    # use.
    at_60 = slc._read_calc("PRESSURE", 60, "mean", None)
    at_0 = slc._read_calc("PRESSURE", 0, "mean", None)
    aggregated_then_diffed = (at_60 - at_0) / at_0 * 100.0
    assert not np.allclose(aggregated, aggregated_then_diffed)


# ---------------------------------------------------------------------------
# calc_kind="surface" - see opm_vis.utils.grid.slice_range_first_active_indices and
# test_grid.py for the gap-filling behaviour itself (SPE1CASE1 has no inactive cells to
# exercise that with); these confirm generate() takes the plain, non-aggregating branch for
# "surface" rather than _read_calc/apply_slice_calc (which reject "surface"; see compute_calc).
# ---------------------------------------------------------------------------


def test_generate_with_calc_kind_surface_matches_plain_values(slc):
    plain = slc.generate("PRESSURE", 60)
    surface = slc.generate("PRESSURE", 60, calc_kind="surface")

    np.testing.assert_allclose(surface.get_array(), plain.get_array())


def test_generate_calc_kind_surface_combines_with_diff(slc):
    plain_diff = slc.generate("PRESSURE", 60, diff_rstep=0, diff_kind="relative")
    surface_diff = slc.generate(
        "PRESSURE", 60, calc_kind="surface", diff_rstep=0, diff_kind="relative"
    )

    np.testing.assert_allclose(surface_diff.get_array(), plain_diff.get_array())


def test_slicepoly2d_surface_true_matches_plain_when_fully_active(case1):
    # SPE1CASE1 has no inactive cells, so surface's own geometry equals the plain slice's -
    # a smoke test that the surface/calc_count constructor wiring works end to end, not a test
    # of the gap-filling behaviour itself (see test_grid.py for that, with synthetic data).
    plain = SlicePoly2D([case1], "k", 0)
    surface = SlicePoly2D([case1], "k", 0, calc_count=None, surface=True)

    assert surface.active_indices() == plain.active_indices()
    np.testing.assert_allclose(surface.cell_corners(), plain.cell_corners())
