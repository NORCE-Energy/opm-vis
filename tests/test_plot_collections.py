""" Unit tests for opm_vis.plot.collections: km axis relabeling and plot_faults, backed by
SPE1CASE1/TPSA_LAGGED """
from typing import cast

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Line3DCollection  # noqa: E402

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


# ---------------------------------------------------------------------------
# plot_faults
# ---------------------------------------------------------------------------


@pytest.fixture
def fault_file(tmp_path):
    """Two named faults inside SPE1CASE1's 10x10x3 grid: FAULT1 at i=4 (0-based), spanning
    every j and k, and FAULT2 at j=5 (0-based), spanning every i and k."""
    path = tmp_path / "FAULTS.DATA"
    path.write_text(
        """
FAULTS
  'FAULT1'  5 5 1 10 1 3 'I' /
  'FAULT2'  1 10 6 6 1 3 'J' /
/
"""
    )
    return str(path)


def test_2d_plot_faults_adds_a_line_collection(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file))

    line_collections = [c for c in coll.ax_.collections if isinstance(c, LineCollection)]
    assert len(line_collections) == 1
    # FAULT1 (i=4) crosses every j (10 cells); FAULT2 (j=5) crosses every i (10 cells)
    assert line_collections[0].get_segments()[0].shape == (2, 2)
    assert sum(len(lc.get_segments()) for lc in line_collections) == 20


def test_2d_plot_faults_labels_each_fault_by_name(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file))

    assert sorted(t.get_text() for t in coll.ax_.texts) == ["FAULT1", "FAULT2"]


def test_2d_plot_faults_labels_can_be_turned_off(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file), labels=False)

    assert len(coll.ax_.texts) == 0


def test_plot_faults_names_restricts_to_the_given_faults(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file), names=["FAULT1"])

    assert [t.get_text() for t in coll.ax_.texts] == ["FAULT1"]


def test_plot_faults_unknown_name_raises(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.raises(KeyError, match="UNKNOWN"):
        coll.plot_faults(str(fault_file), names=["UNKNOWN"])


def test_plot_faults_nothing_crossing_the_slice_adds_nothing(case1, fault_file):
    # FAULT1 is an I-direction fault: coincident with the plane of any i-slice, never a line
    # on one - so filtering to it alone crosses no i-slice at all.
    coll = SlicePoly2DCollection([case1], "i", 5)

    coll.plot_faults(str(fault_file), names=["FAULT1"])

    assert len(coll.ax_.collections) == 0
    assert len(coll.ax_.texts) == 0


def test_plot_faults_default_colour_is_black(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file))

    line_collections = [c for c in coll.ax_.collections if isinstance(c, LineCollection)]
    np.testing.assert_allclose(np.asarray(line_collections[0].get_color()), [[0.0, 0.0, 0.0, 1.0]])


def test_plot_faults_forwards_kwargs(case1, fault_file):
    coll = SlicePoly2DCollection([case1], "k", 0)

    coll.plot_faults(str(fault_file), color="red")

    line_collections = [c for c in coll.ax_.collections if isinstance(c, LineCollection)]
    np.testing.assert_allclose(np.asarray(line_collections[0].get_color()), [[1.0, 0.0, 0.0, 1.0]])


def test_3d_plot_faults_adds_a_line3d_collection(case1, fault_file):
    coll = SlicePoly3DCollection([case1], [("k", 0)])
    ax_3d = cast(Axes3D, coll.ax_)

    coll.plot_faults(str(fault_file))

    assert any(isinstance(c, Line3DCollection) for c in ax_3d.collections)
    assert sorted(t.get_text() for t in ax_3d.texts) == ["FAULT1", "FAULT2"]
