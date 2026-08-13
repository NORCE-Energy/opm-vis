""" Difference calculations shared by the pvplot and plot backends """
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

# "plain": current - reference. "absolute": |current - reference|. "relative": percent change
# from reference.
DIFF_KINDS = ("plain", "absolute", "relative")


def compute_diff(current: NDArray[Any], reference: NDArray[Any], kind: str) -> NDArray[Any]:
    """
    Difference between a keyword's values at two report steps

    Parameters
    ----------
    current : NDArray[Any]
        Values at the report step being plotted
    reference : NDArray[Any]
        Values at the reference report step being differenced against
    kind : str
        One of DIFF_KINDS: "plain" (current - reference), "absolute" (the plain difference's
        magnitude), or "relative" (percent change from reference)

    Returns
    -------
    NDArray[Any]
        The requested difference, same shape as the inputs

    Raises
    ------
    ValueError
        If kind is not one of DIFF_KINDS

    Notes
    -----
    "relative" divides by reference, which is exactly 0 in a cell wherever the reference
    value itself is 0. NumPy's divide-by-zero/invalid warnings are suppressed there since the
    resulting inf/NaN is an expected consequence of dividing by zero, not a bug to report.
    """
    if kind not in DIFF_KINDS:
        raise ValueError(f"kind must be one of {DIFF_KINDS}, got {kind!r}")

    delta = current - reference
    if kind == "plain":
        return delta
    if kind == "absolute":
        return np.abs(delta)

    with np.errstate(divide="ignore", invalid="ignore"):
        return delta / reference * 100.0


def diff_label(keyword: str, kind: str) -> str:
    """
    Keyword name annotated to show a plot/colour bar is showing a difference

    Parameters
    ----------
    keyword : str
        OPM keyword
    kind : str
        One of DIFF_KINDS; see compute_diff

    Returns
    -------
    str
        "ΔKEYWORD" for "plain"/"relative", "|ΔKEYWORD|" for "absolute"

    Raises
    ------
    ValueError
        If kind is not one of DIFF_KINDS
    """
    if kind not in DIFF_KINDS:
        raise ValueError(f"kind must be one of {DIFF_KINDS}, got {kind!r}")

    return f"|Δ{keyword}|" if kind == "absolute" else f"Δ{keyword}"
