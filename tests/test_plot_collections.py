""" Unit tests for opm_vis.plot.collections: km axis relabeling and plot_faults, backed by
SPE1CASE1/TPSA_LAGGED """
from typing import cast

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Line3DCollection  # noqa: E402

from opm_vis.plot.collections import (  # noqa: E402
    SlicePoly2DCollection,
    SlicePoly3DCollection,
    _km_axis_label,
    _km_tick_formatter,
    default_slice_figsize,
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


def test_default_slice_figsize_follows_a_square_slice():
    width, height = default_slice_figsize(100.0, 100.0)

    # Square axes; the extra width is the margin for the colorbar and y label
    assert width - 1.8 == pytest.approx(height - 1.2, abs=0.01)


def test_default_slice_figsize_clamps_a_thin_cross_section():
    # SPE1CASE1's cross-sections are 10000 ft wide but only 100 ft deep
    assert default_slice_figsize(10000.0, 100.0) == default_slice_figsize(2.5, 1.0)
    assert default_slice_figsize(1.0, 10000.0) == default_slice_figsize(1.0, 2.0)


def test_default_slice_figsize_survives_a_degenerate_slice():
    assert default_slice_figsize(0.0, 100.0) == default_slice_figsize(1.0, 1.0)


def test_2d_cross_section_gets_a_wide_figure(case1):
    coll = SlicePoly2DCollection([case1], "i", 5)

    width, height = coll.fig.get_size_inches()
    assert width > 2 * height


def test_2d_figsize_overrides_the_default(case1):
    coll = SlicePoly2DCollection([case1], "k", 0, figsize=(5.0, 3.0))

    assert tuple(coll.fig.get_size_inches()) == (5.0, 3.0)


def test_3d_figsize_overrides_the_default(case1):
    coll = SlicePoly3DCollection([case1], [("k", 0)], figsize=(5.0, 3.0))

    assert tuple(coll.fig.get_size_inches()) == (5.0, 3.0)


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


# ---------------------------------------------------------------------------
# plot_polygons
# ---------------------------------------------------------------------------


def _line_collections(ax):
    return [c for c in ax.collections if isinstance(c, LineCollection)]


def test_plot_polygons_on_a_k_slice_draws_every_polygon_by_its_x_y(case1, polygon_files):
    coll = SlicePoly2DCollection([case1], "k", 0)
    coll.plot_polygons([polygon_files["outline"], polygon_files["line"]])

    (lines,) = _line_collections(coll.ax_)
    assert len(lines.get_segments()) == 2
    assert {t.get_text() for t in coll.ax_.texts} == {"outline", "deep"}


def test_plot_polygons_on_an_i_slice_projects_x_y_z_and_skips_outlines(case1, polygon_files):
    coll = SlicePoly2DCollection([case1], "i", 5)
    with pytest.warns(UserWarning, match="1 x,y-only polygon"):
        coll.plot_polygons([polygon_files["outline"], polygon_files["line"]])

    (lines,) = _line_collections(coll.ax_)
    (segment,) = lines.get_segments()
    # An i-slice plots (y, depth)
    assert np.allclose(segment, [[500, 8350], [9500, 8350]])


def test_plot_polygons_in_3d_puts_outlines_at_the_top_of_the_slices(case1, polygon_files):
    coll = SlicePoly3DCollection([case1], [("k", 1)])
    coll.plot_polygons(polygon_files["outline"])

    (lines,) = [c for c in coll.ax_.collections if isinstance(c, Line3DCollection)]
    top = coll.slice_coll[0].cell_corners_min()[2]
    assert np.allclose(lines._segments3d[0][:, 2], top)  # pylint: disable=protected-access


def test_plot_polygons_labels_can_be_replaced_or_turned_off(case1, polygon_files):
    paths = [polygon_files["outline"], polygon_files["line"]]

    relabelled = SlicePoly2DCollection([case1], "k", 0)
    relabelled.plot_polygons(paths, labels=["Licence", ""])
    unlabelled = SlicePoly2DCollection([case1], "k", 0)
    unlabelled.plot_polygons(paths, labels=False)

    assert [t.get_text() for t in relabelled.ax_.texts] == ["Licence"]
    assert not unlabelled.ax_.texts


def test_plot_polygons_warns_about_a_polygon_outside_the_slice(case1, tmp_path):
    path = tmp_path / "km.npy"
    # Far outside SPE1CASE1, which spans 0-10000 ft
    np.save(path, np.array([[1.0, 1.0], [9.0, 1.0], [9.0, 9.0]]) + 100000)
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.warns(UserWarning, match=r"outside the plotted grid.*km \(km\.npy\)"):
        coll.plot_polygons(str(path))


def test_plot_colorbar_label_replaces_the_generated_one(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)
    coll.plot(None, "PERMX", colorbar_label="$k_x$ [mD]")

    colorbar_axes = coll.fig.axes[-1]
    assert colorbar_axes.get_ylabel() == "$k_x$ [mD]"


def test_plot_polygons_linewidth_defaults_to_2_and_can_be_changed(case1, polygon_files):
    default = SlicePoly2DCollection([case1], "k", 0)
    default.plot_polygons(polygon_files["line"])
    thick = SlicePoly2DCollection([case1], "k", 0)
    thick.plot_polygons(polygon_files["line"], linewidth=6.0)

    assert _line_collections(default.ax_)[0].get_linewidth()[0] == 2.0
    assert _line_collections(thick.ax_)[0].get_linewidth()[0] == 6.0


def test_plot_title_can_be_turned_off(case1):
    with_title = SlicePoly2DCollection([case1], "k", 0)
    with_title.plot(60, "SGAS")
    without_title = SlicePoly2DCollection([case1], "k", 0)
    without_title.plot(60, "SGAS", title=False)

    assert with_title.fig._suptitle.get_text() == "31.12.2019"  # pylint: disable=protected-access
    assert without_title.fig._suptitle is None  # pylint: disable=protected-access


def test_animate_title_can_be_turned_off(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)
    coll.animate("SGAS", rstep_list=[0, 60], title=False)
    coll.anim._init_draw()  # pylint: disable=protected-access
    coll.anim._draw_frame(60)  # pylint: disable=protected-access

    assert coll.fig._suptitle is None  # pylint: disable=protected-access


def _well_texts(ax):
    return sorted(t.get_text() for t in ax.texts)


def test_plot_well_names_restricts_the_wells_drawn(case1):
    # INJ is completed at k=0 only, PROD at k=2 only; an i- or j-slice through both would be
    # needed to see both, so each is checked on its own layer
    inj = SlicePoly2DCollection([case1], "k", 0)
    inj.plot(60, "SGAS")
    prod = SlicePoly2DCollection([case1], "k", 2)
    prod.plot(60, "SGAS")
    only_prod_named = SlicePoly2DCollection([case1], "k", 0)
    only_prod_named.plot(60, "SGAS", well_names=["PROD"])

    assert _well_texts(inj.ax_) == ["INJ"]
    assert _well_texts(prod.ax_) == ["PROD"]
    assert _well_texts(only_prod_named.ax_) == []


def test_plot_well_names_keeps_a_named_well(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)
    coll.plot(60, "SGAS", well_names=["INJ"])

    assert _well_texts(coll.ax_) == ["INJ"]


def test_plot_unknown_well_name_raises(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.raises(KeyError, match="NOPE"):
        coll.plot(60, "SGAS", well_names=["NOPE"])


def test_animate_checks_well_names_up_front(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.raises(KeyError, match="NOPE"):
        coll.animate("SGAS", rstep_list=[0, 60], well_names=["NOPE"])


# ---------------------------------------------------------------------------
# log_scale
# ---------------------------------------------------------------------------


def _slice_collection(coll):
    return next(c for c in coll.ax_.collections if hasattr(c, "get_array"))


def test_plot_log_scale_uses_a_log_norm_with_a_positive_lower_limit(case1):
    coll = SlicePoly2DCollection([case1], "i", 5)
    coll.plot(None, "PERMX", log_scale=True)

    norm = _slice_collection(coll).norm
    assert isinstance(norm, LogNorm)
    # PERMX is 500/50/200 mD by layer; the linear path would have started its range at 0
    assert (norm.vmin, norm.vmax) == (50.0, 500.0)


def test_plot_without_log_scale_keeps_the_linear_norm(case1):
    coll = SlicePoly2DCollection([case1], "i", 5)
    coll.plot(None, "PERMX")

    assert not isinstance(_slice_collection(coll).norm, LogNorm)


def test_plot_log_scale_honours_an_explicit_clim(case1):
    coll = SlicePoly2DCollection([case1], "i", 5)
    coll.plot(None, "PERMX", log_scale=True, clim=(10, 1000))

    norm = _slice_collection(coll).norm
    assert (norm.vmin, norm.vmax) == (10.0, 1000.0)


def test_plot_log_scale_shares_limits_across_slices(case1):
    coll = SlicePoly3DCollection([case1], [("k", 0), ("k", 1)])
    coll.plot(None, "PERMX", log_scale=True)

    norms = [c.norm for c in coll.ax_.collections if hasattr(c, "get_array")]
    assert len(norms) == 2 and norms[0] is not norms[1]
    assert {(n.vmin, n.vmax) for n in norms} == {(50.0, 500.0)}


def test_plot_log_scale_with_no_positive_value_raises(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.raises(ValueError, match="needs positive values"):
        coll.plot(0, "SGAS", log_scale=True)  # SGAS is 0 everywhere at report step 0


def test_plot_log_scale_warns_about_values_it_cannot_colour(case1):
    coll = SlicePoly2DCollection([case1], "k", 0)

    with pytest.warns(UserWarning, match=r"\d+ cell value\(s\) are zero or negative"):
        coll.plot(60, "PRESSURE", log_scale=True, diff_rstep=0)


@pytest.mark.parametrize(("log_scale", "scale"), [(True, "log"), (False, "linear")])
def test_animate_colorbar_follows_log_scale(case1, log_scale, scale):
    coll = SlicePoly2DCollection([case1], "i", 5)
    coll.animate("PERMX", rstep_list=[0, 60], log_scale=log_scale)

    assert coll.fig.axes[-1].get_yscale() == scale
