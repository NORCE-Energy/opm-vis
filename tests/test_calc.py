""" Unit tests for opm_vis.utils.calc, shared by the pvplot and plot backends """
import warnings

import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.utils.calc import (
    CALC_KINDS,
    apply_slice_calc,
    calc_label,
    compute_calc,
    resolve_calc_range,
)
from opm_vis.utils.grid import slice_range_layer_grid
from opm_vis.utils.restart import RestartReader

# The case1/data_dir fixtures come from conftest.py. SPE1CASE1 is a fully active,
# standard-oriented 10x10x3 Cartesian box grid (no inactive cells, no NaNs).


@pytest.fixture(scope="module")
def real_egrid(data_dir):
    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


# ---------------------------------------------------------------------------
# compute_calc
# ---------------------------------------------------------------------------


def test_mean_averages_along_axis_0():
    stacked = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    np.testing.assert_allclose(compute_calc(stacked, "mean"), [3.0, 4.0])


def test_sum_adds_along_axis_0():
    stacked = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    np.testing.assert_allclose(compute_calc(stacked, "sum"), [9.0, 12.0])


def test_nan_layers_are_skipped_not_zero_padded():
    # Position 0 has a real value in only 2 of 3 layers; both mean and sum must be computed
    # over just those 2, never treating the NaN layer as a 0.
    stacked = np.array([[10.0], [np.nan], [20.0]])

    assert compute_calc(stacked, "mean")[0] == pytest.approx(15.0)
    assert compute_calc(stacked, "sum")[0] == pytest.approx(30.0)


def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="mean"):
        compute_calc(np.array([[1.0]]), "bogus")


def test_mean_of_an_all_nan_column_does_not_warn():
    # A position inactive on the displayed slice itself is an all-NaN column here (it is
    # discarded by apply_slice_calc regardless) - NumPy's own "Mean of empty slice" warning for
    # that is expected, not a bug, and must not surface.
    stacked = np.array([[np.nan, 1.0], [np.nan, 2.0]])

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = compute_calc(stacked, "mean")

    assert np.isnan(result[0])
    assert result[1] == pytest.approx(1.5)


def test_sum_of_an_all_nan_column_does_not_warn():
    stacked = np.array([[np.nan, 1.0], [np.nan, 2.0]])

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = compute_calc(stacked, "sum")

    assert result[0] == 0.0  # np.nansum's own convention for an all-NaN slice
    assert result[1] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# calc_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", CALC_KINDS)
def test_calc_label_wraps_keyword_with_kind(kind):
    assert calc_label("PRESSURE", kind) == f"{kind}(PRESSURE)"


def test_calc_label_rejects_an_unknown_kind():
    with pytest.raises(ValueError, match="mean"):
        calc_label("PRESSURE", "bogus")


# ---------------------------------------------------------------------------
# resolve_calc_range
# ---------------------------------------------------------------------------


def test_resolve_calc_range_defaults_to_the_grid_s_last_layer():
    assert resolve_calc_range(slice_ind=3, n_slice=10, count=None) == (3, 9)


def test_resolve_calc_range_limits_to_count_layers():
    assert resolve_calc_range(slice_ind=3, n_slice=10, count=4) == (3, 6)


def test_resolve_calc_range_clamps_count_past_the_grid_s_last_layer():
    assert resolve_calc_range(slice_ind=8, n_slice=10, count=100) == (8, 9)


def test_resolve_calc_range_count_of_one_is_just_the_slice_itself():
    assert resolve_calc_range(slice_ind=5, n_slice=10, count=1) == (5, 5)


# ---------------------------------------------------------------------------
# apply_slice_calc
# ---------------------------------------------------------------------------


def test_apply_slice_calc_replaces_only_the_displayed_slice_s_cells():
    # 4 active cells total; layer_grid has 2 layers of 2 lateral positions each. Layer 0 (the
    # displayed slice) touches active indices 0 and 1; layer 1 touches 2 and 3.
    full_data = np.array([10.0, 20.0, 100.0, 200.0])
    layer_grid = np.array([[0, 1], [2, 3]])

    result = apply_slice_calc(full_data, layer_grid, "mean")

    # Position 0: mean(10, 100) = 55; position 1: mean(20, 200) = 110
    np.testing.assert_allclose(result, [55.0, 110.0, 100.0, 200.0])
    # full_data itself must not be mutated
    np.testing.assert_allclose(full_data, [10.0, 20.0, 100.0, 200.0])


def test_apply_slice_calc_skips_positions_inactive_in_other_layers():
    # Lateral position 1 is active on the displayed slice (layer 0) but inactive on layer 1
    # (-1); its aggregate must come from layer 0 alone, not be dragged down by a phantom 0.
    full_data = np.array([10.0, 20.0, 100.0])
    layer_grid = np.array([[0, 1], [2, -1]])

    result = apply_slice_calc(full_data, layer_grid, "mean")

    np.testing.assert_allclose(result, [55.0, 20.0, 100.0])


def test_apply_slice_calc_leaves_positions_inactive_on_the_displayed_slice_untouched():
    # Lateral position 1 is inactive on the displayed slice itself (layer 0 == -1), so it has
    # no active index to write an aggregate into at all - full_data must come back unchanged.
    full_data = np.array([10.0, 100.0])
    layer_grid = np.array([[0, -1], [1, -1]])

    result = apply_slice_calc(full_data, layer_grid, "sum")

    np.testing.assert_allclose(result, [110.0, 100.0])


# ---------------------------------------------------------------------------
# Integration against the real SPE1CASE1 dataset
# ---------------------------------------------------------------------------


def test_calc_matches_manual_column_aggregate_for_spe1(case1, real_egrid):
    restart = RestartReader([case1])
    rstep = 60
    full_data = restart.read("PRESSURE", rstep)

    layer_grid = slice_range_layer_grid(real_egrid, "k", 0, 2)  # every layer, k=0..2
    result = apply_slice_calc(full_data, layer_grid, "mean")

    nx, ny, _ = real_egrid.dimension
    for i in range(nx):
        for j in range(ny):
            act0 = real_egrid.active_index(i, j, 0)
            column = [
                full_data[real_egrid.active_index(i, j, k)] for k in range(3)
            ]
            assert result[act0] == pytest.approx(np.mean(column))


def test_calc_count_of_one_matches_the_slice_s_own_plain_values(case1, real_egrid):
    restart = RestartReader([case1])
    rstep = 60
    full_data = restart.read("PRESSURE", rstep)

    start, end = resolve_calc_range(slice_ind=1, n_slice=3, count=1)
    layer_grid = slice_range_layer_grid(real_egrid, "k", start, end)
    result = apply_slice_calc(full_data, layer_grid, "sum")

    nx, ny, _ = real_egrid.dimension
    for i in range(nx):
        for j in range(ny):
            act1 = real_egrid.active_index(i, j, 1)
            assert result[act1] == pytest.approx(full_data[act1])
