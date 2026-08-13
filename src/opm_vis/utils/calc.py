""" Calculator (mean/sum) aggregation across a range of grid layers, shared by pvplot and plot """
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

# "mean": average of the active cells across the layer range. "sum": their sum. Adding a new
# kind only needs a new entry here and a new branch in compute_calc - click.Choice(CALC_KINDS)
# in the CLI picks it up automatically.
CALC_KINDS = ("mean", "sum")


def compute_calc(stacked: NDArray[Any], kind: str) -> NDArray[Any]:
    """
    Reduce a stack of per-layer values into one aggregated value per position

    Parameters
    ----------
    stacked : NDArray[Any]
        Values with shape (n_layers, n_positions). NaN marks a layer with no active cell at
        that position.
    kind : str
        One of CALC_KINDS: "mean" or "sum"

    Returns
    -------
    NDArray[Any]
        Aggregated values, shape (n_positions,)

    Raises
    ------
    ValueError
        If kind is not one of CALC_KINDS

    Notes
    -----
    np.nanmean/np.nansum skip NaNs, so a position is aggregated only over the layers where it
    actually has an active cell - never padded with zeros or otherwise counting inactive cells.
    """
    if kind not in CALC_KINDS:
        raise ValueError(f"kind must be one of {CALC_KINDS}, got {kind!r}")

    with np.errstate(invalid="ignore"):
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
        0-based index of the slice being displayed - the range always starts here
    n_slice : int
        Number of layers along the slice's own dimension (egrid.dimension[axis])
    count : int | None
        Value of --calc-count: limit the range to this many layers, or None to continue to the
        grid's last layer

    Returns
    -------
    tuple[int, int]
        (start, end), both inclusive and 0-based: start is always slice_ind; end is
        n_slice - 1 if count is None, otherwise min(slice_ind + count - 1, n_slice - 1)
    """
    end = n_slice - 1 if count is None else min(slice_ind + count - 1, n_slice - 1)
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
