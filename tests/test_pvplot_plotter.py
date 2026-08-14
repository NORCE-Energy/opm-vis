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


def test_set_scalars_diff_rstep_colours_by_the_difference(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60, diff_rstep=0)

    expected = plotter.case.diff("SGAS", 60, ref_rstep=0, kind="plain")
    mesh = plotter._actors["k0"].mesh
    np.testing.assert_allclose(
        mesh.cell_data["SGAS"], expected[mesh.cell_data["ACTIVE_INDEX"]]
    )


def test_set_scalars_diff_kind_changes_the_values_drawn(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60, diff_rstep=0, diff_kind="plain")
    plain = plotter._actors["k0"].mesh.cell_data["SGAS"].copy()
    plotter.set_scalars("SGAS", 60, diff_rstep=0, diff_kind="absolute")
    absolute = plotter._actors["k0"].mesh.cell_data["SGAS"].copy()

    np.testing.assert_allclose(absolute, np.abs(plain))


def test_set_scalars_diff_takes_its_colour_limits_from_the_diff_data(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60, diff_rstep=0)

    low, high = plotter._actors["k0"].actor.mapper.scalar_range
    assert (low, high) == pytest.approx(
        plotter.case.value_range("SGAS", [60], diff_rstep=0, diff_kind="plain")
    )


def test_set_scalars_without_diff_rstep_is_unaffected(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("SGAS", 60)

    expected = plotter.case.read("SGAS", 60)
    mesh = plotter._actors["k0"].mesh
    np.testing.assert_allclose(
        mesh.cell_data["SGAS"], expected[mesh.cell_data["ACTIVE_INDEX"]]
    )


def test_global_clim_diff_rstep_covers_the_diff_not_the_values(plotter):
    # PRESSURE is nonzero at report step 0, unlike SGAS, so its diff range is not coincidentally
    # identical to its value range
    values = plotter.global_clim("PRESSURE", [60])
    diff = plotter.global_clim("PRESSURE", [60], diff_rstep=0)

    assert diff != values
    assert diff == pytest.approx(
        plotter.case.value_range("PRESSURE", [60], diff_rstep=0)
    )


# ---------------------------------------------------------------------------
# -c/--calculator (calc_kind/calc_count)
# ---------------------------------------------------------------------------


def test_set_scalars_calc_kind_averages_the_column_below_the_slice(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="mean")

    full = plotter.case.read("PRESSURE", 60)
    mesh = plotter._actors["k0"].mesh
    nx, ny, nz = plotter.grid.egrid.dimension
    expected = np.array(
        [
            np.mean(
                [full[plotter.grid.egrid.active_index(i, j, k)] for k in range(nz)]
            )
            for i in range(nx)
            for j in range(ny)
        ]
    )
    # Reorder expected (built in (i, j) order) to match the mesh's own active-index order
    act_to_expected = {
        plotter.grid.egrid.active_index(i, j, 0): expected[i * ny + j]
        for i in range(nx)
        for j in range(ny)
        if plotter.grid.egrid.active_index(i, j, 0) >= 0
    }
    ordered_expected = [
        act_to_expected[act] for act in mesh.cell_data["ACTIVE_INDEX"]
    ]
    np.testing.assert_allclose(mesh.cell_data["PRESSURE"], ordered_expected)


def test_set_scalars_calc_count_limits_the_layer_range(plotter):
    # SPE1CASE1 has 3 k-layers (0, 1, 2). slice_ind=0 is always included; calc_count=1 adds
    # just the next layer (k=1), so it must differ from both the plain slice values (k=0 alone)
    # and the full, no-count aggregate (k=0..2).
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="sum")
    full_range = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()
    plotter.set_scalars(
        "PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="sum", calc_count=1
    )
    two_layers = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()

    plain = plotter.case.read("PRESSURE", 60)
    mesh = plotter._actors["k0"].mesh
    plain_on_slice = plain[mesh.cell_data["ACTIVE_INDEX"]]

    assert not np.allclose(full_range, two_layers)
    assert not np.allclose(two_layers, plain_on_slice)

    nx, ny, _ = plotter.grid.egrid.dimension
    act_to_next_layer = {
        plotter.grid.egrid.active_index(i, j, 0): plain[plotter.grid.egrid.active_index(i, j, 1)]
        for i in range(nx)
        for j in range(ny)
        if plotter.grid.egrid.active_index(i, j, 0) >= 0
    }
    expected = plain_on_slice + np.array(
        [act_to_next_layer[act] for act in mesh.cell_data["ACTIVE_INDEX"]]
    )
    np.testing.assert_allclose(two_layers, expected)


def test_set_scalars_calc_kind_combines_with_diff(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars(
        "PRESSURE",
        60,
        slice_dim="k",
        slice_ind=0,
        calc_kind="mean",
        diff_rstep=0,
        diff_kind="relative",
    )
    diffed_then_aggregated = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()

    plotter.set_scalars("PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="mean")
    at_60 = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()
    plotter.set_scalars("PRESSURE", 0, slice_dim="k", slice_ind=0, calc_kind="mean")
    at_0 = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()
    # relative change between the two report steps' own means - "aggregate first, then diff",
    # the ordering this feature does NOT use
    aggregated_then_diffed = (at_60 - at_0) / at_0 * 100.0

    # "diff first, then aggregate": each cell's own relative change is computed before
    # averaging, so this must differ from relative-differencing the two means afterwards -
    # relative change is nonlinear, so the two orderings are not coincidentally equal here.
    assert not np.allclose(diffed_then_aggregated, aggregated_then_diffed)

    full = plotter.case.diff("PRESSURE", 60, ref_rstep=0, kind="relative")
    nx, ny, nz = plotter.grid.egrid.dimension
    mesh = plotter._actors["k0"].mesh
    act_to_expected = {
        plotter.grid.egrid.active_index(i, j, 0): np.mean(
            [full[plotter.grid.egrid.active_index(i, j, k)] for k in range(nz)]
        )
        for i in range(nx)
        for j in range(ny)
        if plotter.grid.egrid.active_index(i, j, 0) >= 0
    }
    expected = [act_to_expected[act] for act in mesh.cell_data["ACTIVE_INDEX"]]
    np.testing.assert_allclose(diffed_then_aggregated, expected)


def test_global_clim_calc_kind_covers_the_aggregate_not_the_plain_values(plotter):
    values = plotter.global_clim("PRESSURE", [60])
    aggregated = plotter.global_clim(
        "PRESSURE", [60], slice_dim="k", slice_ind=0, calc_kind="mean"
    )

    assert aggregated != values


# ---------------------------------------------------------------------------
# calc_kind="surface" - SPE1CASE1 has no inactive cells, so surface's own gap-filling geometry
# has nothing to fill in here (see opm_vis.utils.grid.slice_range_first_active_indices's own
# tests, and mesh.py's extract_range_slice/quad_slice(surface=True) tests, for that with
# synthetic data). These confirm add_slice/set_scalars/global_clim wire "surface" through
# correctly and take the plain, non-aggregating path - not apply_slice_calc, which raises for
# "surface".
# ---------------------------------------------------------------------------


def test_add_slice_surface_matches_plain_when_fully_active(plotter):
    plotter.add_slice("k", 0, name="plain")
    plotter.add_slice("k", 0, surface=True, name="surface")

    plain = plotter._actors["plain"].mesh
    surface = plotter._actors["surface"].mesh
    assert surface.n_cells == plain.n_cells
    np.testing.assert_array_equal(
        sorted(surface.cell_data["ACTIVE_INDEX"]), sorted(plain.cell_data["ACTIVE_INDEX"])
    )


def test_add_slice_surface_with_quads_matches_plain_when_fully_active(plotter):
    plotter.add_slice("k", 0, quads=True, name="plain")
    plotter.add_slice("k", 0, quads=True, surface=True, name="surface")

    plain = plotter._actors["plain"].mesh
    surface = plotter._actors["surface"].mesh
    assert surface.n_cells == plain.n_cells
    np.testing.assert_array_equal(
        sorted(surface.cell_data["ACTIVE_INDEX"]), sorted(plain.cell_data["ACTIVE_INDEX"])
    )


def test_set_scalars_calc_kind_surface_matches_plain_values(plotter):
    plotter.add_slice("k", 0, surface=True)

    plotter.set_scalars("PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="surface")
    surface_values = plotter._actors["k0"].mesh.cell_data["PRESSURE"].copy()

    plain = plotter.case.read("PRESSURE", 60)
    mesh = plotter._actors["k0"].mesh
    np.testing.assert_allclose(surface_values, plain[mesh.cell_data["ACTIVE_INDEX"]])


def test_global_clim_calc_kind_surface_matches_plain_values(plotter):
    values = plotter.global_clim("PRESSURE", [60])
    surface = plotter.global_clim(
        "PRESSURE", [60], slice_dim="k", slice_ind=0, calc_kind="surface"
    )

    assert surface == values


# ---------------------------------------------------------------------------
# add_threshold / add_clip
# ---------------------------------------------------------------------------


def test_add_threshold_keeps_only_the_cells_that_pass(plotter):
    name = plotter.add_threshold("SGAS", 120, 0.4)

    subset = plotter._actors[name].mesh
    expected = (plotter.case.read("SGAS", 120) >= 0.4).sum()
    assert name == "SGAS-threshold"
    assert subset.n_cells == expected
    assert subset.n_cells < 300


def test_add_threshold_can_be_inverted(plotter):
    kept = plotter.add_threshold("SGAS", 120, 0.4, name="kept")
    dropped = plotter.add_threshold("SGAS", 120, 0.4, invert=True, name="dropped")

    total = plotter._actors[kept].mesh.n_cells + plotter._actors[dropped].mesh.n_cells
    assert total == 300


def test_add_threshold_accepts_a_range(plotter):
    name = plotter.add_threshold("SGAS", 120, (0.4, 0.5))

    values = plotter.case.read("SGAS", 120)
    expected = ((values >= 0.4) & (values <= 0.5)).sum()
    assert plotter._actors[name].mesh.n_cells == expected


def test_thresholded_subset_can_still_be_recoloured(plotter):
    name = plotter.add_threshold("SGAS", 120, 0.4)

    plotter.set_scalars("PRESSURE", 60)

    # The threshold fixes which cells are shown, not what they show
    subset = plotter._actors[name].mesh
    np.testing.assert_allclose(
        subset.cell_data["PRESSURE"],
        plotter.case.read("PRESSURE", 60)[subset.cell_data["ACTIVE_INDEX"]],
    )


def test_add_threshold_leaves_the_full_grid_uncoloured(plotter):
    plotter.add_grid()

    plotter.add_threshold("SGAS", 120, 0.4)

    # threshold() selects the array it filtered on; left alone that would silently start
    # colouring the full grid actor by SGAS
    assert plotter._actors["grid"].mesh.active_scalars_name is None


def test_add_clip_halves_the_grid_through_its_centre(plotter):
    name = plotter.add_clip("z")

    assert name == "clip"
    assert plotter._actors[name].mesh.n_cells < 300


def test_clipped_grid_can_still_be_recoloured(plotter):
    name = plotter.add_clip("x")

    plotter.set_scalars("SGAS", 60)

    subset = plotter._actors[name].mesh
    np.testing.assert_allclose(
        subset.cell_data["SGAS"],
        plotter.case.read("SGAS", 60)[subset.cell_data["ACTIVE_INDEX"]],
    )


def test_crinkle_clip_keeps_whole_cells(plotter):
    # Mid-cell: SPE1CASE1's columns are 1000 ft wide, so the default centre at x=5000 falls on
    # a cell boundary and splits nothing
    origin = (5500.0, 5000.0, 8375.0)

    smooth = plotter.add_clip("x", origin, name="smooth")
    crinkled = plotter.add_clip("x", origin, crinkle=True, name="crinkled")

    # A crinkle clip never splits a cell, so its cells keep their full volume
    assert plotter._actors[crinkled].mesh.volume > plotter._actors[smooth].mesh.volume


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


def test_add_wells_slices_restricts_to_wells_completed_there(plotter):
    # INJ is completed at k=0 only, PROD at k=2 only
    plotter.add_slice("k", 0)

    plotter.add_wells(60, slices=[("k", 0)])

    assert plotter._actors["pvplot-wells-open"].mesh.n_cells == 1


def test_add_wells_slices_is_a_union_across_several_slices(plotter):
    plotter.add_slice("k", 0)
    plotter.add_slice("k", 2)

    plotter.add_wells(60, slices=[("k", 0), ("k", 2)])

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


def test_scalar_bar_is_titled_with_the_diff_kind(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 60, diff_rstep=0, diff_kind="relative")

    assert list(plotter.plotter.scalar_bars.keys()) == ["ΔPRESSURE [%]"]


def test_scalar_bar_is_titled_with_the_calc_kind(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars("PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="mean")

    assert list(plotter.plotter.scalar_bars.keys()) == ["mean(PRESSURE) [psia]"]


def test_scalar_bar_is_titled_with_the_calc_kind_and_diff_kind(plotter):
    plotter.add_slice("k", 0)

    plotter.set_scalars(
        "PRESSURE", 60, slice_dim="k", slice_ind=0, calc_kind="mean", diff_rstep=0
    )

    assert list(plotter.plotter.scalar_bars.keys()) == ["mean(ΔPRESSURE) [psia]"]


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
    default = plotter.plotter.camera_position[0]

    plotter.view_3d(azimuth=45.0, elevation=60.0)

    assert plotter.plotter.camera_position[0] != default


def _visible_pixels(plotter, mask):
    """How many pixels the cells picked out by `mask` cover, i.e. are not occluded."""
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

    return int((luminance > luminance.max() * 0.9).sum()) if luminance.max() > 40 else 0


def test_view_3d_looks_down_on_the_top_of_the_model_by_default(plotter):
    plotter.add_grid(lighting=False)
    layer = plotter.grid.ijk[:, 2]

    plotter.view_3d()

    # Flipping the view-up leaves the camera below the model, so the default elevation has to
    # lift it back over the top or the base occludes everything of interest
    assert _visible_pixels(plotter, layer == 0) > _visible_pixels(plotter, layer == 2)


def test_view_3d_at_zero_elevation_looks_up_at_the_base(plotter):
    plotter.add_grid(lighting=False)
    layer = plotter.grid.ijk[:, 2]

    plotter.view_3d(elevation=0.0)

    assert _visible_pixels(plotter, layer == 2) > _visible_pixels(plotter, layer == 0)


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


def test_show_axes_grid_keeps_a_field_units_axis_in_feet_however_wide(plotter):
    plotter.add_slice("k", 0)

    # SPE1CASE1 is field units, so the km relabeling never kicks in no matter the span
    plotter.show_axes_grid(bounds=(0, 5000, 0, 5000, -100, 0))

    axes = plotter.plotter.renderer.cube_axes_actor
    assert axes.GetXTitle() == "E(x) [ft]"
    assert axes.GetXAxisRange() == (0.0, 5000.0)


def test_show_axes_grid_switches_a_wide_metric_axis_to_km(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)

        # TPSA_LAGGED's own grid only spans 100 m a side; a synthetic wide x bounds exercises
        # the km relabeling without needing test data that large. y and z keep their own small
        # spans, so they stay in metres - this is per-axis, not all-or-nothing.
        gplot.show_axes_grid(bounds=(0, 2000, 0, 100, -1020, -1000))

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXTitle() == "E(x) [km]"
        assert axes.GetYTitle() == "N(y) [m]"
        assert axes.GetZTitle() == "Depth [m]"
        assert axes.GetXAxisRange() == (0.0, 2.0)
        assert axes.GetYAxisRange() == (0.0, 100.0)
        assert axes.GetZAxisRange() == (1020.0, 1000.0)


def test_show_axes_grid_km_switch_is_skipped_with_an_explicit_axes_ranges(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)

        # An explicit axes_ranges opts out of the km relabeling, same as it already opts out
        # of the z-axis sign flip
        gplot.show_axes_grid(axes_ranges=(0, 2000, 0, 100, 1000, 1020))

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXTitle() == "E(x) [m]"
        assert axes.GetXAxisRange() == (0.0, 2000.0)


def test_show_axes_grid_gives_a_km_axis_more_decimal_precision(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)

        # show_bounds' own default format is one decimal place. At meter-scale values that is
        # plenty, but a km-scaled 1200 m span becomes 1.2 - a range only one decimal wide -
        # collapsing every tick to the same-looking label unless precision goes up too.
        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000))

        axes = gplot.plotter.renderer.cube_axes_actor
        # y stays in metres, so its format is untouched
        assert axes.y_label_format == ("%.1f" if pv.vtk_version_info < (9, 6, 0) else "{0:.1f}")
        assert axes.x_label_format == ("%.3f" if pv.vtk_version_info < (9, 6, 0) else "{0:.3f}")


def test_show_axes_grid_respects_an_explicit_fmt_on_a_km_axis(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)

        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000), fmt="%.1f")

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXTitle() == "E(x) [km]"
        assert axes.x_label_format == "%.1f"


def test_set_scalars_does_not_undo_the_km_relabeling(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)
        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000))

        # pyvista's Renderer.add_actor calls update_bounds_axes() after every actor it adds -
        # including the scalar bar set_scalars adds here - which resets a cube axes actor's
        # axis ranges straight back to its plain physical bounds unless something puts the
        # override back. Regression test for that: the km range must survive this call.
        gplot.set_scalars("PRESSURE", 0)

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXAxisRange() == (500.0, 501.2)
        assert axes.x_label_format == ("%.3f" if pv.vtk_version_info < (9, 6, 0) else "{0:.3f}")


def test_add_wells_does_not_undo_the_km_relabeling(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)
        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000))

        gplot.add_wells(0)

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXAxisRange() == (500.0, 501.2)


def test_set_title_does_not_undo_the_km_relabeling(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)
        gplot.set_scalars("PRESSURE", 0)
        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000))

        gplot.set_title()

        axes = gplot.plotter.renderer.cube_axes_actor
        assert axes.GetXAxisRange() == (500.0, 501.2)


def test_km_relabeling_never_flashes_the_raw_range_mid_animation(tpsa_lagged, offscreen):
    del offscreen
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        gplot.add_slice("k", 0)
        gplot.show_axes_grid(bounds=(500_000, 501_200, 0, 100, -1020, -1000))

        # pyvista's Renderer.remove_actor renders *before* returning, so a fix applied only
        # after add_wells finishes (once its removed wells are re-added) would be one render
        # too late: the frame produced by the removal itself, mid-call, already went out with
        # the raw metre range. Recording every render() call here - mirroring what
        # animate()'s per-frame set_scalars/add_wells/set_title calls do - is how to catch
        # that: a fix that is merely "eventually correct" would still show up as a bad frame
        # partway through, even though the state checked at the end of each call looks fine.
        seen_ranges = []
        real_render = gplot.plotter.render

        def instrumented_render(*args, **kwargs):
            result = real_render(*args, **kwargs)
            axes = gplot.plotter.renderer.cube_axes_actor
            if axes is not None:
                seen_ranges.append(axes.GetXAxisRange())
            return result

        gplot.plotter.render = instrumented_render

        gplot.set_scalars("PRESSURE", 0)
        gplot.add_wells(0)
        gplot.set_title()
        # A second frame: add_wells now removes the first frame's well actors before re-adding
        # them, exercising remove_actor's own reset.
        gplot.add_wells(0)
        gplot.set_scalars("PRESSURE", 5)
        gplot.set_title()

        assert len(seen_ranges) > 0
        assert all(rng == (500.0, 501.2) for rng in seen_ranges)


def test_show_axes_grid_omits_the_axis_pointing_at_the_camera(plotter):
    plotter.add_slice("j", 5)
    plotter.view_2d("j")

    plotter.show_axes_grid()

    # A j-slice is viewed along y, so a y axis would run meaninglessly across the picture
    axes = plotter.plotter.renderer.cube_axes_actor
    assert axes.GetXAxisVisibility() == 1
    assert axes.GetZAxisVisibility() == 1
    assert axes.GetYAxisVisibility() == 0


def test_show_axes_grid_restores_all_axes_in_a_3d_view(plotter):
    plotter.add_slice("j", 5)
    plotter.view_2d("j")
    plotter.show_axes_grid()

    plotter.view_3d()
    plotter.show_axes_grid()

    axes = plotter.plotter.renderer.cube_axes_actor
    assert axes.GetYAxisVisibility() == 1


def test_show_axes_grid_still_draws_after_a_render_and_a_view_change(plotter):
    plotter.add_slice("j", 5)
    plotter.set_scalars("SGAS", 60)
    plotter.view_3d()
    plotter.show_axes_grid()
    plotter.screenshot()

    plotter.view_2d("j")
    plotter.show_axes_grid()

    # Once something has been rendered, a newly added bounds box needs an explicit render or
    # it never appears
    assert plotter.plotter.renderer.cube_axes_actor.GetVisibility() == 1
    assert len(np.unique(plotter.screenshot().reshape(-1, 3), axis=0)) > 100


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


# ---------------------------------------------------------------------------
# animate
# ---------------------------------------------------------------------------


def test_animate_writes_a_gif(plotter, tmp_path):
    plotter.add_slice("k", 0)
    target = tmp_path / "sgas.gif"

    plotter.animate("SGAS", target, rsteps=range(0, 121, 40))

    assert target.exists() and target.stat().st_size > 0


def test_animate_writes_a_movie(plotter, tmp_path):
    plotter.add_slice("k", 0)
    target = tmp_path / "sgas.mp4"

    # open_movie names its frame rate differently from open_gif and mangles an fps kwarg
    plotter.animate("SGAS", target, rsteps=range(0, 121, 40))

    assert target.exists() and target.stat().st_size > 0


def test_animate_uses_one_colour_range_for_every_frame(plotter, tmp_path):
    plotter.add_slice("k", 0)
    rsteps = [0, 60, 120]

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=rsteps)

    # Per-frame limits would make a frame's colours meaningless next to its neighbours'
    assert plotter._actors["k0"].actor.mapper.scalar_range == pytest.approx(
        plotter.global_clim("SGAS", rsteps)
    )


def test_animate_diff_rstep_uses_the_diff_colour_range(plotter, tmp_path):
    plotter.add_slice("k", 0)
    rsteps = [0, 60, 120]

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=rsteps, diff_rstep=0)

    assert plotter._actors["k0"].actor.mapper.scalar_range == pytest.approx(
        plotter.case.value_range("SGAS", rsteps, diff_rstep=0)
    )
    # The last frame animated should have been coloured by its diff from report step 0
    np.testing.assert_allclose(
        plotter._actors["k0"].mesh.cell_data["SGAS"],
        plotter.case.diff("SGAS", rsteps[-1], ref_rstep=0)[
            plotter._actors["k0"].mesh.cell_data["ACTIVE_INDEX"]
        ],
    )


def test_animate_reuses_the_geometry_for_every_frame(plotter, tmp_path):
    plotter.add_slice("k", 0)
    before = plotter._actors["k0"].actor

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=range(0, 121, 40))

    assert plotter.actor_names() == ["k0"]
    assert plotter._actors["k0"].actor is before


def test_animate_leaves_the_plotter_usable(plotter, tmp_path):
    plotter.add_slice("k", 0)

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=[0, 60])

    # Only the writer is closed, not the render window
    assert plotter.screenshot().shape == (120, 160, 3)


def test_animate_titles_each_frame_with_its_report_date(plotter, tmp_path):
    plotter.add_slice("k", 0)

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=[0, 120])

    assert plotter.title == "29.12.2024"  # the last frame's report date


def test_animate_can_follow_wells(plotter, tmp_path):
    plotter.add_slice("k", 0)

    plotter.animate("SGAS", tmp_path / "a.gif", rsteps=[60, 120], wells=True)

    assert "pvplot-wells-open" in plotter.actor_names()


def test_animate_with_nothing_added_raises(plotter, tmp_path):
    with pytest.raises(RuntimeError, match="Nothing to animate"):
        plotter.animate("SGAS", tmp_path / "a.gif", rsteps=[0])


def test_animate_rejects_an_unknown_keyword_before_opening_the_file(plotter, tmp_path):
    plotter.add_slice("k", 0)
    target = tmp_path / "a.gif"

    with pytest.raises(KeyError, match="not in restart files or .INIT file"):
        plotter.animate("NOSUCHKW", target, rsteps=[0, 60])

    assert not target.exists()


def test_animate_closes_the_writer_even_when_a_frame_fails(plotter, tmp_path):
    plotter.add_slice("k", 0)
    target = tmp_path / "a.gif"

    # An explicit clim gets past the up-front range scan, so the failure lands on the second
    # frame with the writer already open
    with pytest.raises(ValueError, match="Report step 9999 was not found"):
        plotter.animate("SGAS", target, rsteps=[0, 9999], clim=(0.0, 1.0))

    # A half-written animation must still be finalised rather than left holding the file open
    assert plotter.plotter.mwriter.closed
    assert target.exists()


def test_context_manager_closes_the_render_window(case1, offscreen):
    del offscreen
    with GridPlotter([case1], off_screen=True) as gplot:
        gplot.add_slice("k", 0)

    # PyVista marks a closed plotter's render window as gone
    assert gplot.plotter._closed is True
