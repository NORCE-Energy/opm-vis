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
# set_scalars / global_clim
# ---------------------------------------------------------------------------


def test_set_scalars_writes_the_keyword_onto_every_slice(plotter):
    plotter.add_slice("k", 0)
    plotter.add_slice("i", 4)

    plotter.set_scalars("SGAS", 60)

    expected = plotter.case.read("SGAS", 60)
    for name in ("k0", "i4"):
        mesh = plotter._actors[name].mesh
        np.testing.assert_allclose(
            mesh.cell_data["SGAS"], expected[mesh.cell_data["ACTIVE_INDEX"]]
        )
        assert mesh.active_scalars_name == "SGAS"


def test_set_scalars_does_not_add_or_replace_actors(plotter):
    plotter.add_slice("k", 0)
    before = plotter._actors["k0"].actor

    for rstep in (0, 60, 120):
        plotter.set_scalars("SGAS", rstep)

    # The whole point: stepping through report steps reuses one actor and one dataset
    assert plotter.actor_names() == ["k0"]
    assert plotter._actors["k0"].actor is before


def test_set_scalars_changes_what_is_rendered(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 0, clim=(0.0, 1.0))
    early = plotter.screenshot()
    plotter.set_scalars("SGAS", 120, clim=(0.0, 1.0))
    late = plotter.screenshot()

    # Gas has spread through the top layer by the end of the run
    assert not np.array_equal(early, late)


def test_set_scalars_colours_by_the_requested_keyword(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60)
    by_sgas = plotter.screenshot()
    plotter.set_scalars("PRESSURE", 60)
    by_pressure = plotter.screenshot()

    # Guards against the mapper staying bound to a previously selected array: writing the
    # values and setting the dataset's active scalars is not on its own enough
    assert not np.array_equal(by_sgas, by_pressure)


def test_set_scalars_takes_its_colour_limits_from_the_data(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 1)

    low, high = plotter._actors["k0"].actor.mapper.scalar_range
    assert low > 3000.0  # not clamped to zero the way opm_vis.plot would
    assert (low, high) == pytest.approx(plotter.case.value_range("PRESSURE", [1]))


def test_set_scalars_honours_an_explicit_clim(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60, clim=(0.0, 1.0))

    assert plotter._actors["k0"].actor.mapper.scalar_range == (0.0, 1.0)


def test_set_scalars_can_colour_a_static_keyword(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PORO", 60)

    np.testing.assert_allclose(plotter._actors["k0"].mesh.cell_data["PORO"], 0.3)


def test_set_scalars_records_what_is_shown(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60)

    assert (plotter.keyword, plotter.rstep) == ("SGAS", 60)


def test_set_scalars_applies_cmap_and_log_scale(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PERMX", 60, cmap="magma", log_scale=True)

    lut = plotter._actors["k0"].actor.mapper.lookup_table
    assert lut.log_scale is True


def test_set_scalars_leaves_the_wireframe_uncoloured(plotter):
    plotter.add_slice("k", 0)
    plotter.add_wireframe()

    plotter.set_scalars("SGAS", 60)

    assert "SGAS" in plotter._actors["k0"].mesh.cell_data
    assert "SGAS" not in plotter._actors["wireframe"].mesh.cell_data


def test_set_scalars_with_nothing_added_raises(plotter):
    with pytest.raises(RuntimeError, match="Nothing to colour"):
        plotter.set_scalars("SGAS", 60)


def test_set_scalars_rejects_an_unknown_keyword(plotter):
    plotter.add_slice("k", 0)

    with pytest.raises(KeyError, match="not in restart files or .INIT file"):
        plotter.set_scalars("NOSUCHKW", 60)


def test_global_clim_covers_every_report_step_by_default(plotter):
    everywhere = plotter.global_clim("SGAS")
    one_step = plotter.global_clim("SGAS", [60])

    assert everywhere[0] <= one_step[0]
    assert everywhere[1] >= one_step[1]


# ---------------------------------------------------------------------------
# add_wells
# ---------------------------------------------------------------------------


def test_add_wells_draws_the_open_wells(plotter):
    plotter.add_slice("k", 0)

    plotter.add_wells(60)

    # Both SPE1CASE1 wells are open for the whole run, so there is no shut actor
    assert "pvplot-wells-open" in plotter.actor_names()
    assert "pvplot-wells-shut" not in plotter.actor_names()


def test_add_wells_is_not_restricted_to_the_slices_on_screen(plotter):
    # PROD is completed in k=2 only, so a k=0 slice would hide it in opm_vis.plot
    plotter.add_slice("k", 0)

    plotter.add_wells(60)

    assert plotter._actors["pvplot-wells-open"].mesh.n_cells == 2


def test_add_wells_replaces_rather_than_stacks(plotter):
    plotter.add_slice("k", 0)

    plotter.add_wells(60)
    after_one = len(plotter.plotter.actors)
    plotter.add_wells(120)

    assert len(plotter.plotter.actors) == after_one


def test_add_wells_is_a_no_op_when_a_report_step_has_no_wells(plotter):
    plotter.add_slice("k", 0)

    # SPE1CASE1's restart file carries no well arrays at report step 0
    plotter.add_wells(0)

    assert "pvplot-wells-open" not in plotter.actor_names()


def _label_actors(plotter):
    """Label actor names. add_point_labels suffixes the name it is given."""
    return [n for n in plotter.plotter.actors if n.startswith("pvplot-well-labels")]


def test_add_wells_labels_can_be_turned_off(plotter):
    plotter.add_slice("k", 0)

    plotter.add_wells(60, labels=False)

    assert _label_actors(plotter) == []


def test_add_wells_labels_each_well_by_name(plotter):
    plotter.add_slice("k", 0)

    plotter.add_wells(60)

    assert _label_actors(plotter) != []


def test_add_wells_labels_are_replaced_not_stacked(plotter):
    plotter.add_slice("k", 0)

    plotter.add_wells(60)
    after_one = len(_label_actors(plotter))
    plotter.add_wells(120)

    assert after_one > 0
    assert len(_label_actors(plotter)) == after_one


def test_wells_are_not_coloured_by_set_scalars(plotter):
    plotter.add_slice("k", 0)
    plotter.add_wells(60)

    plotter.set_scalars("SGAS", 60)

    # Wells are drawn in their open/shut colour, not in the property colour map
    assert "SGAS" not in plotter._actors["pvplot-wells-open"].mesh.cell_data


def test_add_wells_renders(plotter):
    plotter.add_slice("k", 0)
    plotter.set_scalars("SGAS", 60)
    without = plotter.screenshot()

    plotter.add_wells(60)
    plotter.plotter.render()

    assert not np.array_equal(without, plotter.screenshot())


# ---------------------------------------------------------------------------
# Scalar bar
# ---------------------------------------------------------------------------


def test_scalar_bar_is_titled_with_the_keyword_and_its_unit(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 60)

    # SPE1CASE1 is a field-units case, and the unit must be plain text, not mathtext
    assert list(plotter.plotter.scalar_bars.keys()) == ["PRESSURE [psia]"]


def test_scalar_bar_omits_empty_brackets_for_an_untabulated_unit(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SATNUM", 60)

    assert list(plotter.plotter.scalar_bars.keys()) == ["SATNUM"]


def test_scalar_bar_is_replaced_when_the_keyword_changes(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60)
    plotter.set_scalars("PRESSURE", 60)

    assert list(plotter.plotter.scalar_bars.keys()) == ["PRESSURE [psia]"]


def test_scalar_bar_survives_stepping_through_report_steps(plotter):
    plotter.add_slice("k", 0)

    for rstep in (0, 60, 120):
        plotter.set_scalars("SGAS", rstep)

    assert list(plotter.plotter.scalar_bars.keys()) == ["SGAS [-]"]


def test_scalar_bar_can_be_turned_off(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60, scalar_bar=False)

    assert list(plotter.plotter.scalar_bars.keys()) == []


# ---------------------------------------------------------------------------
# Camera presets, axes and title
# ---------------------------------------------------------------------------


def _screen_height_of(plotter, mask):
    """Mean vertical pixel position of the cells picked out by `mask`, 0 being the top."""
    mesh = plotter._actors["grid"].mesh
    mesh.cell_data["MARK"] = mask.astype(float)
    mesh.set_active_scalars("MARK")
    mapper = plotter._actors["grid"].actor.mapper
    mapper.SetScalarModeToUseCellFieldData()
    mapper.SelectColorArray("MARK")
    mapper.scalar_visibility = True
    mapper.scalar_range = (0.0, 1.0)

    plotter.plotter.background_color = "black"
    plotter.plotter.render()
    luminance = plotter.screenshot().mean(axis=2)
    rows, _ = np.where(luminance > luminance.max() * 0.9)

    return rows.mean()


def test_view_3d_puts_shallow_cells_above_deep_ones(plotter):
    plotter.add_grid(lighting=False)
    plotter.view_3d()
    layer = plotter.grid.ijk[:, 2]

    shallow = _screen_height_of(plotter, layer == 0)
    deep = _screen_height_of(plotter, layer == 2)

    # PyVista assumes z points up; without flipping the view-up vector for OPM's
    # depth-positive-down z, the model renders upside down
    assert shallow < deep


def test_view_2d_cross_section_puts_shallow_cells_above_deep_ones(plotter):
    plotter.add_grid(lighting=False)
    plotter.view_2d("j")
    layer = plotter.grid.ijk[:, 2]

    assert _screen_height_of(plotter, layer == 0) < _screen_height_of(plotter, layer == 2)


def test_view_2d_uses_parallel_projection(plotter):
    plotter.add_slice("k", 0)

    plotter.view_2d("k")

    assert plotter.plotter.camera.parallel_projection is True


def test_view_3d_turns_parallel_projection_back_off(plotter):
    plotter.add_slice("k", 0)
    plotter.view_2d("k")

    plotter.view_3d()

    assert plotter.plotter.camera.parallel_projection is False


@pytest.mark.parametrize("slice_dim", ["i", "j", "k"])
def test_view_2d_works_for_every_slice_dimension(plotter, slice_dim):
    plotter.add_slice(slice_dim, 0)

    plotter.view_2d(slice_dim)

    assert plotter.screenshot().shape == (120, 160, 3)


def test_view_2d_rejects_an_invalid_slice_dimension(plotter):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        plotter.view_2d("x")


def test_view_3d_accepts_camera_rotations(plotter):
    plotter.add_slice("k", 0)
    plotter.view_3d()
    straight_on = plotter.plotter.camera_position[0]

    plotter.view_3d(azimuth=45.0, elevation=20.0)

    assert plotter.plotter.camera_position[0] != straight_on


def test_set_z_scale_stretches_the_depth_axis(plotter):
    plotter.add_slice("j", 5)

    plotter.set_z_scale(20.0)

    assert plotter.plotter.scale[2] == 20.0


def test_z_scale_can_be_set_at_construction(case1, offscreen):
    del offscreen
    with GridPlotter([case1], off_screen=True, z_scale=15.0) as gplot:
        assert gplot.plotter.scale[2] == 15.0


def test_show_axes_grid_labels_axes_in_the_cases_own_units(plotter):
    plotter.add_slice("k", 0)

    plotter.show_axes_grid()

    # SPE1CASE1 is a field-units case, so feet and not metres
    assert plotter.plotter.renderer.cube_axes_actor.GetXTitle() == "E(x) [ft]"
    assert plotter.plotter.renderer.cube_axes_actor.GetZTitle() == "Depth [ft]"


def test_set_title_uses_the_report_date_by_default(plotter):
    plotter.add_slice("k", 0)
    plotter.set_scalars("SGAS", 0)

    plotter.set_title()

    assert plotter.title == "01.01.2015"
    assert "pvplot-title" in plotter.plotter.actors


def test_set_title_replaces_rather_than_stacks(plotter):
    plotter.add_slice("k", 0)

    plotter.set_title("first")
    before = len(plotter.plotter.actors)
    plotter.set_title("second")

    assert plotter.title == "second"
    assert len(plotter.plotter.actors) == before  # replaced under the same name


def test_set_title_without_a_report_step_raises(plotter):
    plotter.add_slice("k", 0)

    with pytest.raises(RuntimeError, match="no date to title with"):
        plotter.set_title()


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
