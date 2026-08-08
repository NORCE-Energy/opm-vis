""" Unit tests for opm_vis.pvplot.plotter, backed by the SPE1CASE1 test dataset """
import numpy as np
import pytest

pv = pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.pvplot import GridPlotter  # noqa: E402

# The case1 and offscreen fixtures come from conftest.py. Everything here renders off-screen,
# and assertions are made on the datasets and their cell arrays rather than on pixels - pixel
# comparisons would be brittle across VTK and driver versions. The screenshot tests only check
# that a render happens at all.


@pytest.fixture
def plotter(case1, offscreen):
    del offscreen  # only needed for its side effect of forcing off-screen rendering
    with GridPlotter([case1], off_screen=True, window_size=(160, 120)) as gplot:
        yield gplot


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_picks_up_the_cases_unit_convention(plotter):
    assert plotter.label.unit_convention() == "field"


def test_init_adds_nothing_by_itself(plotter):
    assert plotter.actor_names() == []


def test_init_does_not_build_the_mesh(case1, offscreen):
    del offscreen
    with GridPlotter([case1], off_screen=True) as gplot:
        # Constructing a plotter should be cheap; the hexahedral build waits for a request
        assert gplot.grid._mesh is None


# ---------------------------------------------------------------------------
# add_slice / add_grid / add_wireframe
# ---------------------------------------------------------------------------


def test_add_slice_registers_the_slice_under_a_derived_name(plotter):
    name = plotter.add_slice("k", 0)

    assert name == "k0"
    assert plotter.actor_names() == ["k0"]
    assert plotter._actors["k0"].mesh.n_cells == 100


def test_add_slice_accepts_an_explicit_name(plotter):
    assert plotter.add_slice("j", 5, name="cross-section") == "cross-section"


def test_add_slice_can_use_the_quad_fast_path(plotter):
    plotter.add_slice("k", 0, quads=True, name="quads")
    plotter.add_slice("k", 0, name="hexes")

    quads = plotter._actors["quads"].mesh
    hexes = plotter._actors["hexes"].mesh
    assert isinstance(quads, pv.PolyData)
    assert isinstance(hexes, pv.UnstructuredGrid)
    assert quads.n_cells == hexes.n_cells


def test_add_multiple_slices_keeps_them_all(plotter):
    plotter.add_slice("k", 0)
    plotter.add_slice("i", 4)
    plotter.add_slice("j", 5)

    assert plotter.actor_names() == ["k0", "i4", "j5"]


def test_add_grid_adds_every_active_cell(plotter):
    plotter.add_grid()

    assert plotter._actors["grid"].mesh.n_cells == 300


def test_add_wireframe_draws_only_the_boundary(plotter):
    plotter.add_wireframe()

    surface = plotter._actors["wireframe"].mesh
    assert isinstance(surface, pv.PolyData)
    assert surface.n_cells < 300 * 6  # a boundary, not every face of every cell


def test_adding_the_same_name_twice_raises(plotter):
    plotter.add_slice("k", 0)

    with pytest.raises(ValueError, match="has already been added"):
        plotter.add_slice("k", 0)


def test_add_slice_forwards_kwargs_to_add_mesh(plotter):
    # show_edges is an add_mesh argument, so this fails loudly if kwargs are swallowed
    plotter.add_slice("k", 0, show_edges=True, opacity=0.5)

    assert plotter._actors["k0"].actor is not None


def test_add_slice_validates_its_arguments(plotter):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        plotter.add_slice("x", 0)
    with pytest.raises(ValueError, match="out of bounds"):
        plotter.add_slice("k", 3)


# ---------------------------------------------------------------------------
# screenshot / lifecycle
# ---------------------------------------------------------------------------


def test_screenshot_renders_an_image(plotter):
    plotter.add_slice("k", 0)

    image = plotter.screenshot()

    assert image.shape == (120, 160, 3)
    assert image.dtype == np.uint8


def test_screenshot_writes_a_file(plotter, tmp_path):
    plotter.add_slice("k", 0)
    target = tmp_path / "slice.png"

    plotter.screenshot(target)

    assert target.exists() and target.stat().st_size > 0


def test_context_manager_closes_the_render_window(case1, offscreen):
    del offscreen
    with GridPlotter([case1], off_screen=True) as gplot:
        gplot.add_slice("k", 0)

    # PyVista marks a closed plotter's render window as gone
    assert gplot.plotter._closed is True
