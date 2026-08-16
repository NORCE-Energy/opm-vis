""" Unit tests for opm_vis.plot.collections' km axis relabeling, backed by SPE1CASE1/TPSA_LAGGED """
from typing import cast

import matplotlib
import pytest

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from matplotlib.ticker import FuncFormatter  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402

from opm_vis.plot.collections import (  # noqa: E402
    SlicePoly2DCollection,
    SlicePoly3DCollection,
    _km_axis_label,
    _km_tick_formatter,
)

# The case1 and tpsa_lagged fixtures come from conftest.py.


# ---------------------------------------------------------------------------
# _km_axis_label / _km_tick_formatter
# ---------------------------------------------------------------------------


def test_km_axis_label_stays_in_metres_under_the_threshold():
    assert _km_axis_label("E(x)", 999.0) == "E(x) [m]"


def test_km_axis_label_switches_to_km_over_the_threshold():
    assert _km_axis_label("E(x)", 1200.0) == "E(x) [km]"


def test_km_axis_label_uses_the_span_magnitude_not_its_sign():
    # get_xlim() etc. can return a negative (max - min) after an axis has been inverted
    assert _km_axis_label("Depth", -1200.0) == "Depth [km]"


def test_km_tick_formatter_divides_by_1000_to_three_decimals():
    assert _km_tick_formatter(501_200.0, 0) == "501.200"


# ---------------------------------------------------------------------------
# SlicePoly2DCollection
# ---------------------------------------------------------------------------


def test_2d_k_slice_switches_wide_axes_to_km(case1):
    # SPE1CASE1 is a 10x10x3 grid, 1000 ft a side: a k-slice's E(x)/N(y) both span 10000 ft
    coll = SlicePoly2DCollection([case1], "k", 0)

    assert coll.ax_.get_xlabel() == "E(x) [km]"
    assert coll.ax_.get_ylabel() == "N(y) [km]"
    assert isinstance(coll.ax_.xaxis.get_major_formatter(), FuncFormatter)
    assert isinstance(coll.ax_.yaxis.get_major_formatter(), FuncFormatter)


def test_2d_j_slice_keeps_the_shallow_depth_axis_in_metres(case1):
    # E(x) is wide (10000 ft) but this layer's own depth span is only ~100 ft
    coll = SlicePoly2DCollection([case1], "j", 5)

    assert coll.ax_.get_xlabel() == "E(x) [km]"
    assert coll.ax_.get_ylabel() == "Depth [m]"
    assert isinstance(coll.ax_.xaxis.get_major_formatter(), FuncFormatter)
    assert not isinstance(coll.ax_.yaxis.get_major_formatter(), FuncFormatter)


def test_2d_i_slice_labels_northing_on_x(case1):
    coll = SlicePoly2DCollection([case1], "i", 5)

    assert coll.ax_.get_xlabel() == "N(y) [km]"
    assert coll.ax_.get_ylabel() == "Depth [m]"


def test_2d_slice_stays_in_metres_under_a_narrow_span(tpsa_lagged):
    # TPSA_LAGGED is only 100 m a side
    coll = SlicePoly2DCollection([tpsa_lagged], "k", 0)

    assert coll.ax_.get_xlabel() == "E(x) [m]"
    assert coll.ax_.get_ylabel() == "N(y) [m]"
    assert not isinstance(coll.ax_.xaxis.get_major_formatter(), FuncFormatter)
    assert not isinstance(coll.ax_.yaxis.get_major_formatter(), FuncFormatter)


# ---------------------------------------------------------------------------
# SlicePoly3DCollection
# ---------------------------------------------------------------------------


def test_3d_collection_switches_wide_axes_to_km_independently(case1):
    coll = SlicePoly3DCollection([case1], [("j", 5)])
    ax_3d = cast(Axes3D, coll.ax_)

    assert ax_3d.get_xlabel() == "E(x) [km]"
    assert ax_3d.get_ylabel() == "N(y) [m]"
    assert ax_3d.get_zlabel() == "Depth(z) [m]"
    assert isinstance(ax_3d.xaxis.get_major_formatter(), FuncFormatter)
    assert not isinstance(ax_3d.yaxis.get_major_formatter(), FuncFormatter)
    assert not isinstance(ax_3d.zaxis.get_major_formatter(), FuncFormatter)
