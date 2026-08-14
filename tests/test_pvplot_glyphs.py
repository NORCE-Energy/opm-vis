""" Unit tests for GridPlotter's vector glyphs, backed by the TPSA_LAGGED test dataset """
import numpy as np
import pytest

pv = pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.pvplot import GridPlotter  # noqa: E402
from opm_vis.pvplot.plotter import _GLYPH_VECTORS  # noqa: E402

# The tpsa_lagged and offscreen fixtures come from conftest.py. TPSA_LAGGED is a fully active
# 5x5x5 grid with DISPX/DISPY/DISPZ displacement components at every report step; its peak
# displacement is exactly zero at report step 0 (nothing has moved yet) and non-zero from
# step 1 onward, which exercises both branches of the auto-scaling factor. Assertions are made
# on the glyph dataset and its arrays rather than on pixels, matching the rest of pvplot's
# render-backed tests.


@pytest.fixture
def plotter(tpsa_lagged, offscreen):
    del offscreen  # only needed for its side effect of forcing off-screen rendering
    with GridPlotter([tpsa_lagged], off_screen=True, window_size=(160, 120)) as gplot:
        yield gplot


# ---------------------------------------------------------------------------
# add_glyphs
# ---------------------------------------------------------------------------


def test_add_glyphs_places_one_glyph_per_active_cell(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 125  # 5x5x5, fully active


def test_add_glyphs_names_itself_after_the_three_keywords(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    assert name == "DISPX-DISPY-DISPZ"
    assert plotter.actor_names() == [name]


def test_add_glyphs_accepts_an_explicit_name(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, name="displacement")

    assert name == "displacement"


def test_add_glyphs_can_be_restricted_to_a_slice(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0)

    assert name == "DISPX-DISPY-DISPZ-k0"
    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 25  # one 5x5 layer


def test_add_glyphs_requires_slice_dim_and_slice_ind_together(plotter):
    with pytest.raises(ValueError, match="slice_ind is required"):
        plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k")
    with pytest.raises(ValueError, match="slice_dim is required"):
        plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_ind=0)


def test_add_glyphs_rejects_an_unknown_keyword(plotter):
    with pytest.raises(KeyError, match="not in restart files or .INIT file"):
        plotter.add_glyphs("NOSUCHKW", "DISPY", "DISPZ", 15)


def test_add_glyphs_defaults_to_colouring_by_magnitude(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    mapper = plotter._actors[name].actor.mapper
    assert mapper.scalar_visibility is True
    assert mapper.array_name == "GlyphScale"


def test_add_glyphs_explicit_colour_overrides_magnitude_colouring(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, color="red")

    # PyVista colours by scalars whenever they are given at all, regardless of a colour also
    # being passed, so an explicit colour must disable scalar visibility outright rather than
    # relying on the colour to win on its own
    assert plotter._actors[name].actor.mapper.scalar_visibility is False


def test_add_glyphs_adds_a_magnitude_colour_bar(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    assert "mag(DISPX, DISPY, DISPZ)" in plotter.plotter.scalar_bars


def test_add_glyphs_explicit_colour_adds_no_colour_bar(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, color="red")

    assert len(plotter.plotter.scalar_bars) == 0


def test_add_glyphs_colour_bar_coexists_with_set_scalars_own(plotter):
    plotter.add_slice("k", 0)
    plotter.set_scalars("PRESSURE", 15)
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    bars = plotter.plotter.scalar_bars
    assert "mag(DISPX, DISPY, DISPZ)" in bars
    assert "PRESSURE [barsa]" in bars


def test_add_glyphs_does_not_carry_scalars(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    # A glyph's points hold per-arrow, not per-cell, data - set_scalars must leave it alone
    assert plotter._actors[name].carries_scalars is False


def test_add_glyphs_registers_a_glyph_spec(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, scale=False, factor=2.0)

    spec = plotter._glyphs[name]
    assert (spec.x_keyword, spec.y_keyword, spec.z_keyword) == ("DISPX", "DISPY", "DISPZ")
    assert (spec.scale, spec.factor) == (False, 2.0)


def test_add_glyphs_records_the_report_step(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    assert plotter.rstep == 15


def test_add_glyphs_renders(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)
    plotter.view_3d()

    assert plotter.screenshot().shape == (120, 160, 3)


# ---------------------------------------------------------------------------
# add_glyphs(quads=True) - the cell-centre-only fast path
# ---------------------------------------------------------------------------


def test_quads_does_not_need_the_full_mesh(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, quads=True)

    assert plotter.grid._mesh is None  # the expensive hexahedral build was never triggered


def test_quads_does_not_need_the_full_mesh_on_a_slice(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, quads=True)

    assert plotter.grid._mesh is None


def test_quads_places_the_same_number_of_glyphs_as_the_default_path(plotter):
    quads_name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, quads=True, name="q")
    default_name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, name="d")

    quads_points = plotter._actors[quads_name].mesh.point_data["ACTIVE_INDEX"]
    default_points = plotter._actors[default_name].mesh.point_data["ACTIVE_INDEX"]
    assert len(np.unique(quads_points)) == len(np.unique(default_points)) == 125


def test_quads_on_a_slice_places_the_same_number_of_glyphs(plotter):
    quads_name = plotter.add_glyphs(
        "DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, quads=True, name="q"
    )

    glyphs = plotter._actors[quads_name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 25  # one 5x5 layer


def test_quads_sits_on_the_slice_face_not_mid_cell(plotter):
    # TPSA_LAGGED's k=0 layer spans depth 1000-1020 m; the face the quads path uses must sit
    # exactly on the shallow face, not at the layer's mid-depth. z points up (see
    # mesh._read_corners), so this depth comes back negated.
    name = plotter.add_glyphs(
        "DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, quads=True
    )

    source = plotter._glyphs[name].source
    np.testing.assert_allclose(source.points[:, 2], -1000.0)


def test_quads_renders_visibly_on_a_matching_quad_slice(plotter):
    # Regression test for the occlusion this option exists to avoid: glyphs placed at a
    # cell's true volumetric centre are buried inside a solid, opaque add_slice actor and
    # never show up at all; the quads path keeps them on the same surface as a quads=True
    # add_slice, where they are always visible.
    plotter.add_slice("k", 0, quads=True)
    plotter.set_scalars("PRESSURE", 15)
    plotter.view_3d()
    without_glyphs = plotter.screenshot()

    plotter.add_glyphs(
        "DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, quads=True, color="black"
    )
    with_glyphs = plotter.screenshot()

    assert not np.array_equal(without_glyphs, with_glyphs)
    assert (with_glyphs.reshape(-1, 3) == 0).all(axis=1).sum() > 0  # black arrows present


def test_default_glyphs_are_invisible_on_a_solid_matching_slice(plotter):
    # The mirror image of the test above: without quads=True, glyphs sit at the cell's true
    # volumetric centre, which a solid (non-quads) add_slice actor completely occludes
    plotter.add_slice("k", 0)  # default: solid opaque hexahedra, not quads
    plotter.set_scalars("PRESSURE", 15)
    plotter.view_3d()
    without_glyphs = plotter.screenshot()

    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, color="black")
    with_glyphs = plotter.screenshot()

    assert np.array_equal(without_glyphs, with_glyphs)


# ---------------------------------------------------------------------------
# Auto factor: the largest vector should land near one cell's width, and the
# scale=False case must not divide by the (tiny) peak displacement magnitude
# ---------------------------------------------------------------------------


def test_auto_factor_targets_the_meshs_own_characteristic_length(plotter):
    mesh = plotter.grid.mesh
    char_length = mesh.length / mesh.n_cells ** (1 / 3)

    factor = GridPlotter._auto_glyph_factor(mesh, peak_magnitude=2.0, scale=True)

    assert factor == pytest.approx(0.8 * char_length / 2.0)


def test_auto_factor_ignores_peak_magnitude_when_not_scaling(plotter):
    mesh = plotter.grid.mesh
    char_length = mesh.length / mesh.n_cells ** (1 / 3)

    # A real displacement field's magnitude (~1e-5) must not end up as a divisor here - doing
    # so would blow every arrow up by several orders of magnitude
    factor = GridPlotter._auto_glyph_factor(mesh, peak_magnitude=8.85e-5, scale=False)

    assert factor == pytest.approx(0.8 * char_length)


def test_auto_factor_is_one_when_nothing_has_moved_yet(plotter):
    # TPSA_LAGGED's own report step 0: peak displacement is exactly zero
    factor = GridPlotter._auto_glyph_factor(plotter.grid.mesh, peak_magnitude=0.0, scale=True)

    assert factor == 1.0


def test_auto_factor_rejects_an_empty_source():
    with pytest.raises(ValueError, match="empty slice"):
        GridPlotter._auto_glyph_factor(pv.PolyData(), peak_magnitude=1.0, scale=True)


def test_every_n_default_places_one_glyph_per_active_cell(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, every_n=1)

    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 125  # 5x5x5, fully active


def test_every_n_thins_the_glyphs(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, every_n=2)

    glyphs = plotter._actors[name].mesh
    # ceil(125 / 2): one glyph out of every two of TPSA_LAGGED's 125 active cells
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 63


def test_every_n_thins_a_slices_glyphs_too(plotter):
    name = plotter.add_glyphs(
        "DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, every_n=2
    )

    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 13  # ceil(25 / 2)


def test_every_n_thins_the_quads_placement_points_too(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, quads=True, every_n=2)

    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 63


def test_every_n_does_not_change_the_arrow_scale_factor(plotter):
    full = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, name="full")
    thinned = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, every_n=4, name="thinned")

    # Thinning removes arrows, but the remaining ones must stay the same size - only their
    # count should change from every_n, never their scaling
    assert plotter._glyphs[thinned].factor == plotter._glyphs[full].factor


def test_every_n_rejects_less_than_one(plotter):
    with pytest.raises(ValueError, match="every_n must be at least 1"):
        plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, every_n=0)


def test_add_glyphs_scale_false_keeps_arrows_within_the_grids_own_scale(plotter):
    # Regression test for the bug the two unit tests above pin down directly: at one point the
    # scale=False factor was computed the same way as scale=True's, which - given a
    # displacement magnitude around 1e-5 - inflated every arrow by close to five orders of
    # magnitude
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, scale=False)

    glyphs = plotter._actors[name].mesh
    mesh_diagonal = plotter.grid.mesh.length
    glyph_diagonal = np.linalg.norm(
        np.array(glyphs.bounds[1::2]) - np.array(glyphs.bounds[0::2])
    )
    assert glyph_diagonal < 3 * mesh_diagonal


# ---------------------------------------------------------------------------
# set_vectors
# ---------------------------------------------------------------------------


def test_set_vectors_rebuilds_the_glyph_mesh(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)
    before = plotter._actors[name].mesh

    plotter.set_vectors(15)

    assert plotter._actors[name].mesh is not before


def test_set_vectors_keeps_the_same_actor(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)
    actor_before = plotter._actors[name].actor

    plotter.set_vectors(15)

    # The whole point: stepping through report steps reuses one actor, as set_scalars does
    assert plotter.actor_names() == [name]
    assert plotter._actors[name].actor is actor_before


def test_set_vectors_actually_changes_the_vectors(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)  # all-zero displacement

    plotter.set_vectors(15)

    # The glyph mesh itself only carries PyVista's own "GlyphVector"/"GlyphScale" point
    # arrays; the vectors this rebuild used are what _build_glyphs wrote onto the source mesh
    vectors = plotter._glyphs[name].source.cell_data[_GLYPH_VECTORS]
    assert np.linalg.norm(vectors, axis=1).max() > 0.0


def test_set_vectors_keeps_the_every_n_thinning(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0, every_n=2)

    plotter.set_vectors(15)

    glyphs = plotter._actors[name].mesh
    assert len(np.unique(glyphs.point_data["ACTIVE_INDEX"])) == 63  # ceil(125 / 2)


def test_set_vectors_does_not_recompute_the_factor(plotter):
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)
    factor_before = plotter._glyphs[name].factor

    plotter.set_vectors(2)  # TPSA_LAGGED's own largest-displacement report step

    # Recomputing per step would make the same physical displacement draw at a different size
    # depending on which step is showing, the same distortion global_clim exists to prevent
    assert plotter._glyphs[name].factor == factor_before


def test_set_vectors_updates_only_the_named_actor(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0, name="full")
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0, slice_dim="k", slice_ind=0, name="slice")
    slice_mesh_before = plotter._actors["slice"].mesh

    plotter.set_vectors(15, name="full")

    assert plotter._actors["slice"].mesh is slice_mesh_before


def test_set_vectors_updates_every_actor_when_no_name_is_given(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0, name="full")
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0, slice_dim="k", slice_ind=0, name="slice")
    full_before = plotter._actors["full"].mesh
    slice_before = plotter._actors["slice"].mesh

    plotter.set_vectors(15)

    assert plotter._actors["full"].mesh is not full_before
    assert plotter._actors["slice"].mesh is not slice_before


def test_set_vectors_records_the_report_step(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)

    plotter.set_vectors(15)

    assert plotter.rstep == 15


def test_set_vectors_raises_for_an_unknown_name(plotter):
    plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)

    with pytest.raises(KeyError, match="No glyph actor named"):
        plotter.set_vectors(15, name="nosuch")


def test_set_vectors_with_nothing_added_raises(plotter):
    with pytest.raises(RuntimeError, match="Nothing to update"):
        plotter.set_vectors(15)


# ---------------------------------------------------------------------------
# global_glyph_factor
# ---------------------------------------------------------------------------


def test_global_glyph_factor_covers_the_true_peak_over_every_step(plotter):
    # TPSA_LAGGED's own largest displacement occurs at report step 2, not at the last step
    single_step = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [10])
    every_step = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ")

    # A larger true peak divides the factor down further, so covering every step must not
    # give a larger factor than a single step that misses the true peak
    assert every_step <= single_step


def test_global_glyph_factor_matches_add_glyphs_own_auto_factor_for_one_step(plotter):
    factor = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [15])

    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15)

    assert factor == pytest.approx(plotter._glyphs[name].factor)


def test_global_glyph_factor_quads_matches_add_glyphs_quads(plotter):
    factor = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [15], quads=True)

    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, quads=True)

    assert factor == pytest.approx(plotter._glyphs[name].factor)


def test_global_glyph_factor_quads_does_not_need_the_full_mesh(plotter):
    plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [15], quads=True)

    assert plotter.grid._mesh is None


def test_global_glyph_factor_respects_scale_false(plotter):
    scaled = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [15], scale=True)
    unscaled = plotter.global_glyph_factor("DISPX", "DISPY", "DISPZ", [15], scale=False)

    assert scaled != unscaled


def test_global_glyph_factor_can_match_a_slice(plotter):
    factor = plotter.global_glyph_factor(
        "DISPX", "DISPY", "DISPZ", [15], slice_dim="k", slice_ind=0
    )

    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0)

    assert factor == pytest.approx(plotter._glyphs[name].factor)


# ---------------------------------------------------------------------------
# animate(vectors=True)
# ---------------------------------------------------------------------------


def test_animate_can_follow_vectors(plotter, tmp_path):
    plotter.add_slice("k", 0)
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)
    before = plotter._actors[name].mesh

    plotter.animate("PRESSURE", tmp_path / "a.gif", rsteps=[0, 15], vectors=True)

    target = tmp_path / "a.gif"
    assert target.exists() and target.stat().st_size > 0
    # Same actor throughout, but rebuilt to the last frame's vectors
    assert plotter.actor_names() == ["k0", name]
    assert plotter._actors[name].mesh is not before


def test_animate_without_vectors_leaves_glyphs_untouched(plotter, tmp_path):
    plotter.add_slice("k", 0)
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)
    before = plotter._actors[name].mesh

    plotter.animate("PRESSURE", tmp_path / "a.gif", rsteps=[0, 15])

    assert plotter._actors[name].mesh is before


def test_animate_vectors_keeps_the_scale_factor_fixed(plotter, tmp_path):
    plotter.add_slice("k", 0)
    name = plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 0)
    factor_before = plotter._glyphs[name].factor

    plotter.animate("PRESSURE", tmp_path / "a.gif", rsteps=[0, 15], vectors=True)

    # Recomputing the factor per frame would make the same physical displacement draw at a
    # different size depending on which frame is showing
    assert plotter._glyphs[name].factor == factor_before


def test_animate_vectors_without_add_glyphs_raises(plotter, tmp_path):
    plotter.add_slice("k", 0)

    with pytest.raises(RuntimeError, match="Nothing to update! Call add_glyphs"):
        plotter.animate("PRESSURE", tmp_path / "a.gif", rsteps=[0, 15], vectors=True)
