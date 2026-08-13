""" Calculator (mean/sum) aggregation across a range of grid layers, shared by pvplot and plot """
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from numpy.typing import NDArray

# "mean": average of the active cells across the layer range. "sum": their sum. "surface": the
# value of the first active cell in the range, scanning from its start (the given -i/-j/-k
# index) towards its end - i.e. the shallowest active layer touched from that starting index,
# skipping over any inactive/pinched-out ones in between. Unlike mean/sum, "surface" is not a
# reduction compute_calc/apply_slice_calc can perform on an already-displayed slice's values:
# see compute_calc's notes for why, and opm_vis.utils.grid.slice_range_first_active_indices for
# where it is actually implemented instead. Adding a new *aggregating* kind only needs a new
# entry here and a new branch in compute_calc - click.Choice(CALC_KINDS) in the CLI picks it up
# automatically.
CALC_KINDS = ("mean", "sum", "surface")


def compute_calc(stacked: NDArray[Any], kind: str) -> NDArray[Any]:
    """
    Reduce a stack of per-layer values into one aggregated value per position

    Parameters
    ----------
    stacked : NDArray[Any]
        Values with shape (n_layers, n_positions). NaN marks a layer with no active cell at
        that position.
    kind : str
        "mean" or "sum" (the CALC_KINDS entries this function actually implements; see Notes
        for why "surface" is not one of them, despite being a valid CALC_KINDS/--calculator
        value)

    Returns
    -------
    NDArray[Any]
        Aggregated values, shape (n_positions,)

    Raises
    ------
    ValueError
        If kind is not "mean" or "sum" - including "surface", see Notes

    Notes
    -----
    np.nanmean/np.nansum skip NaNs, so a position is aggregated only over the layers where it
    actually has an active cell - never padded with zeros or otherwise counting inactive cells.

    "surface" is deliberately not implemented here: it does not aggregate a column of values at
    all, it picks *which active cell* is displayed at each lateral position (the first active
    one from the range's start), which changes the slice's own geometry, not just the value
    shown on it. apply_slice_calc only ever overwrites cells already active on the displayed
    slice (see its own notes) - and for those, the range's own first layer is by definition
    already active, so a "first active layer" reduction here would always just return the
    slice's own plain value, silently doing nothing. slice_poly.py's generate() and
    pvplot's set_scalars()/global_clim() all skip calling this (and apply_slice_calc) for
    "surface" accordingly, building the surface's geometry via
    opm_vis.utils.grid.slice_range_first_active_indices instead - see _GridSlice's calc_end/
    surface constructor arguments.

    A position with no active cell in any layer - inactive on the displayed slice itself, and
    so discarded by apply_slice_calc regardless of what is computed for it here - is an
    all-NaN column. NumPy's own "Mean of empty slice"/invalid-value warnings for that column are
    an expected consequence of that, not a bug to report, and are suppressed accordingly; the
    NaN result is correct.
    """
    if kind not in CALC_KINDS:
        raise ValueError(f"kind must be one of {CALC_KINDS}, got {kind!r}")

    if kind == "surface":
        raise ValueError(
            '"surface" is not aggregated by compute_calc: it selects which active cell is '
            "displayed at each lateral position rather than reducing a column of values - see "
            "this function's own Notes."
        )

    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.filterwarnings("ignore", message="Mean of empty slice")
        if kind == "mean":
            return np.nanmean(stacked, axis=0)
        return np.nansum(stacked, axis=0)


def calc_label(keyword: str, kind: str) -> str:
    """
    Keyword name annotated to show a plot/colour bar is showing a calculator result

    Parameters
    ----------
    keyword : str
        OPM keyword
    kind : str
        One of CALC_KINDS; see compute_calc

    Returns
    -------
    str
        "kind(KEYWORD)", e.g. "mean(PRESSURE)"

    Raises
    ------
    ValueError
        If kind is not one of CALC_KINDS
    """
    if kind not in CALC_KINDS:
        raise ValueError(f"kind must be one of {CALC_KINDS}, got {kind!r}")

    return f"{kind}({keyword})"


def resolve_calc_range(slice_ind: int, n_slice: int, count: int | None) -> tuple[int, int]:
    """
    Inclusive 0-based layer range the calculator aggregates over

    Parameters
    ----------
    slice_ind : int
        0-based index of the slice being displayed - the range always starts here, and
        slice_ind's own layer is always included regardless of count
    n_slice : int
        Number of layers along the slice's own dimension (egrid.dimension[axis])
    count : int | None
        Value of --calc-count: how many further layers to include *after* slice_ind, in
        addition to slice_ind itself, or None to continue all the way to the grid's last layer.
        count=1 adds just slice_ind+1 (2 layers in total), count=2 adds slice_ind+1 and
        slice_ind+2 (3 layers in total), and so on.

    Returns
    -------
    tuple[int, int]
        (start, end), both inclusive and 0-based: start is always slice_ind; end is
        n_slice - 1 if count is None, otherwise min(slice_ind + count, n_slice - 1)
    """
    end = n_slice - 1 if count is None else min(slice_ind + count, n_slice - 1)
    return slice_ind, end


def apply_slice_calc(full_data: NDArray[Any], layer_grid: NDArray[Any], kind: str) -> NDArray[Any]:
    """
    Replace one slice's values with the calculator's aggregate across a range of layers

    Parameters
    ----------
    full_data : NDArray[Any]
        One value per active cell, in active index order - as returned by CaseData.read,
        RestartReader.read or InitReader.read with no act given
    layer_grid : NDArray[Any]
        (n_layers, nx1, nx2) active index (or -1) per layer and lateral position, as returned
        by opm_vis.utils.grid.slice_range_layer_grid. Layer 0 is the slice being displayed -
        i.e. its own start_ind == the slice's own slice_ind.
    kind : str
        One of CALC_KINDS; see compute_calc

    Returns
    -------
    NDArray[Any]
        A copy of full_data, with every active index belonging to the displayed slice
        (layer_grid[0]) replaced by its aggregate across the whole layer range. Every other
        entry (cells outside the displayed slice) is left unchanged.

    Notes
    -----
    Only the displayed slice's own cells are ever overwritten - the other layers in the range
    exist only to be read from and folded into that one slice's values, never shown themselves.
    """
    flat = layer_grid.reshape(layer_grid.shape[0], -1)
    gathered = np.where(flat >= 0, full_data[np.clip(flat, 0, None)], np.nan)
    aggregated = compute_calc(gathered, kind)

    result = full_data.copy()
    positions = flat[0]
    on_slice = positions >= 0
    result[positions[on_slice]] = aggregated[on_slice]
    return result
