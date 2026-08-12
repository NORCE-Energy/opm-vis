""" Unit tests for opm_vis.pvplot.mesh, backed by the SPE1CASE1 EGRID test dataset """
import shutil

import numpy as np
import pytest

pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm.io.ecl import EGrid  # noqa: E402
from opm_vis.pvplot.mesh import ACTIVE_INDEX, GridMesh  # noqa: E402

# The case1/data_dir fixtures come from conftest.py. SPE1CASE1 is a fully active,
# standard-oriented 10x10x3 Cartesian box grid: it pins down the corner ordering and the
# active-index invariant, but has no pinched-out cells and is not mirrored, so those two
# branches use small synthetic stand-ins exposing just the EGrid interface GridMesh needs.


@pytest.fixture(scope="module")
def grid_mesh(case1):
    return GridMesh(case1)


def _bypass_init(egrid, weld=True):
    """Create a GridMesh around a synthetic EGrid without touching the filesystem."""
    obj = object.__new__(GridMesh)
    obj.egrid = egrid
    obj.weld = weld
    obj._mesh = None
    return obj


class _BoxEGrid:
    """Minimal synthetic box grid. z_sign=1 makes z increase with k, matching OPM's depth
    convention; z_sign=-1 mirrors the grid so the flipped corner order must kick in.
    Cells listed in nan_cells report NaN corners, standing in for pinch-outs."""

    def __init__(self, nx, ny, nz, z_sign=1, nan_cells=()):
        self.dimension = (nx, ny, nz)
        self.active_cells = nx * ny * nz
        self._z_sign = z_sign
        self._nan_cells = set(nan_cells)
        self._active = [(i, j, k) for k in range(nz) for j in range(ny) for i in range(nx)]

    def ijk_from_active_index(self, act):
        return list(self._active[act])

    def xyz_from_active_index(self, act, apply_mapaxes=False):
        del apply_mapaxes  # no MAPAXES on this synthetic grid
        if act in self._nan_cells:
            return [np.nan] * 8, [np.nan] * 8, [np.nan] * 8
        i, j, k = self._active[act]
        xs = [float(i + (c & 1)) for c in range(8)]
        ys = [float(j + ((c >> 1) & 1)) for c in range(8)]
        zs = [float(self._z_sign * (k + ((c >> 2) & 1))) for c in range(8)]
        return xs, ys, zs


class _FaultedPairEGrid:
    """Two unit cells side by side along i, with the second displaced down by `throw`. A
    zero throw leaves them face-to-face; any other value stands in for a fault."""

    dimension = (2, 1, 1)
    active_cells = 2

    def __init__(self, throw):
        self._throw = throw

    def ijk_from_active_index(self, act):
        return [act, 0, 0]

    def xyz_from_active_index(self, act, apply_mapaxes=False):
        del apply_mapaxes  # no MAPAXES on this synthetic grid
        offset = self._throw if act == 1 else 0.0
        xs = [float(act + (c & 1)) for c in range(8)]
        ys = [float((c >> 1) & 1) for c in range(8)]
        zs = [float(((c >> 2) & 1) + offset) for c in range(8)]
        return xs, ys, zs


# ---------------------------------------------------------------------------
# __init__ / EGRID file discovery
# ---------------------------------------------------------------------------


def test_missing_egrid_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="No .EGRID file found"):
        GridMesh(str(tmp_path / "CASE"))


def test_multiple_egrid_files_warns_and_loads_first(tmp_path, data_dir):
    shutil.copy(data_dir / "SPE1CASE1.EGRID", tmp_path / "CASE1.EGRID")
    shutil.copy(data_dir / "SPE1CASE1.EGRID", tmp_path / "CASE2.EGRID")

    with pytest.warns(UserWarning, match="Multiple .EGRID files"):
        GridMesh(str(tmp_path / "CASE"))


def test_grid_mesh_without_mapaxes_is_unaffected(case1):
    assert GridMesh(case1).apply_mapaxes is False


def test_grid_mesh_detects_and_applies_mapaxes(mapaxes_case):
    from opm.io.ecl import EGrid  # pylint: disable=import-outside-toplevel

    x1, y1, x2, y2, x3, y3 = EGrid(mapaxes_case + ".EGRID").export_mapaxes()
    assert (x3 - x2, y3 - y2) == pytest.approx((821.375, 0.0))
    assert (x1 - x2, y1 - y2) == pytest.approx((0.0, 1473.0))

    gmesh = GridMesh(mapaxes_case)
    assert gmesh.apply_mapaxes is True

    # MAPAXES.EGRID's transform is a pure translation to (x2, y2); cell (i=0, j=0) sits at the
    # grid's local (x, y) origin, so the mesh's minimum bound should land exactly there.
    assert gmesh.mesh.bounds.x_min == pytest.approx(x2)
    assert gmesh.mesh.bounds.y_min == pytest.approx(y2)


# ---------------------------------------------------------------------------
# mesh build invariants
# ---------------------------------------------------------------------------


def test_mesh_has_one_cell_per_active_cell(grid_mesh):
    assert grid_mesh.mesh.n_cells == grid_mesh.egrid.active_cells
    assert grid_mesh.mesh.n_cells == 300  # 10x10x3, fully active


def test_mesh_is_built_once_and_cached(case1):
    gmesh = GridMesh(case1)

    assert gmesh._mesh is None  # nothing built until first access
    assert gmesh.mesh is gmesh.mesh


def test_active_index_is_identity_when_nothing_is_pinched_out(grid_mesh):
    np.testing.assert_array_equal(
        grid_mesh.mesh.cell_data[ACTIVE_INDEX], np.arange(grid_mesh.egrid.active_cells)
    )


def test_every_hexahedron_has_positive_volume(grid_mesh):
    volumes = grid_mesh.mesh.compute_cell_sizes()["Volume"]

    # A negative volume means the corners were fed to VTK in the wrong order
    assert (volumes > 0).all()


def test_total_volume_matches_egrid_cell_volumes(grid_mesh):
    expected = np.asarray(grid_mesh.egrid.cellvolumes()).sum()

    np.testing.assert_allclose(grid_mesh.mesh.volume, expected, rtol=1e-9)


def test_ijk_cell_arrays_match_egrid(grid_mesh):
    expected = np.array(
        [
            grid_mesh.egrid.ijk_from_active_index(act)
            for act in range(grid_mesh.egrid.active_cells)
        ]
    )

    np.testing.assert_array_equal(grid_mesh.ijk, expected)


def test_points_are_double_precision(grid_mesh):
    # float32 would only resolve a UTM northing to about half a metre
    assert grid_mesh.mesh.points.dtype == np.float64


def test_dimension_reports_grid_size(grid_mesh):
    assert grid_mesh.dimension == (10, 10, 3)


def test_bookkeeping_arrays_are_not_the_active_scalars(grid_mesh):
    # Attaching cell data makes the first array active, and PyVista then colours the mesh by
    # it on add_mesh - which would show ACTIVE_INDEX instead of the grid
    assert grid_mesh.mesh.active_scalars_name is None
    assert grid_mesh.quad_slice("k", 0).active_scalars_name is None
    assert grid_mesh.extract_slice("k", 0).active_scalars_name is None


# ---------------------------------------------------------------------------
# slice_mask / extract_slice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slice_dim, slice_ind, expected",
    [
        ("i", 4, 10 * 3),  # a 10x10x3 grid has ny*nz cells on an i-slice
        ("j", 5, 10 * 3),  # nx*nz on a j-slice
        ("k", 1, 10 * 10),  # nx*ny on a k-slice
    ],
)
def test_slice_has_expected_cell_count(grid_mesh, slice_dim, slice_ind, expected):
    assert grid_mesh.slice_mask(slice_dim, slice_ind).sum() == expected
    assert grid_mesh.extract_slice(slice_dim, slice_ind).n_cells == expected


def test_slice_keeps_active_index_of_its_cells(grid_mesh):
    slc = grid_mesh.extract_slice("k", 1)

    expected = [
        grid_mesh.egrid.active_index(i, j, 1) for i in range(10) for j in range(10)
    ]
    np.testing.assert_array_equal(sorted(slc.cell_data[ACTIVE_INDEX]), sorted(expected))


def test_slices_partition_the_grid(grid_mesh):
    total = sum(grid_mesh.slice_mask("k", ind).sum() for ind in range(3))

    assert total == grid_mesh.mesh.n_cells


def test_invalid_slice_dim_raises_type_error(grid_mesh):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        grid_mesh.slice_mask("x", 0)


def test_slice_ind_out_of_bounds_raises_value_error(grid_mesh):
    with pytest.raises(ValueError, match="out of bounds"):
        grid_mesh.slice_mask("k", 3)  # SPE1CASE1 has 3 layers: valid range is 0-2


def test_negative_slice_ind_raises_value_error(grid_mesh):
    with pytest.raises(ValueError, match="out of bounds"):
        grid_mesh.slice_mask("k", -1)


def test_extract_slice_does_not_need_the_full_mesh(case1):
    gmesh = GridMesh(case1)

    gmesh.extract_slice("k", 0)

    assert gmesh._mesh is None  # the expensive hexahedral build was never triggered


def test_extract_slice_reads_only_the_slices_own_cells(case1, monkeypatch):
    # SPE1CASE1 is a 10x10x3 grid (300 active cells); a k-slice is only 100 of them
    calls = []
    original = EGrid.xyz_from_active_index

    def counting(self, act, apply_mapaxes=False):
        calls.append(act)
        return original(self, act, apply_mapaxes)

    monkeypatch.setattr(EGrid, "xyz_from_active_index", counting)

    GridMesh(case1).extract_slice("k", 1)

    assert len(calls) == 100


def test_extract_slice_matches_the_hexahedral_meshs_own_slice(case1):
    # Two separate GridMesh instances: one whose full mesh is forced to build first (the
    # always-correct path extract_slice used to take unconditionally), one left alone (the
    # new, lean path) - so the comparison cannot accidentally make the lean path look right
    # just by secretly sharing the other's already-built mesh
    lean = GridMesh(case1).extract_slice("k", 1)

    built_first = GridMesh(case1)
    _ = built_first.mesh
    cached = built_first.extract_slice("k", 1)

    assert lean.n_cells == cached.n_cells
    assert lean.n_points == cached.n_points
    np.testing.assert_array_equal(
        sorted(lean.cell_data[ACTIVE_INDEX]), sorted(cached.cell_data[ACTIVE_INDEX])
    )
    np.testing.assert_allclose(lean.bounds, cached.bounds)
    np.testing.assert_allclose(lean.volume, cached.volume)


def test_extract_slice_reuses_an_already_built_mesh(case1, monkeypatch):
    # The other direction from test_extract_slice_reads_only_the_slices_own_cells: once the
    # full mesh is already in memory, extract_slice must not re-read any corners from the
    # file a second time - it should fall back to the cheap extract_cells() path instead
    gmesh = GridMesh(case1)
    _ = gmesh.mesh

    calls = []
    original = EGrid.xyz_from_active_index

    def counting(self, act, apply_mapaxes=False):
        calls.append(act)
        return original(self, act, apply_mapaxes)

    monkeypatch.setattr(EGrid, "xyz_from_active_index", counting)

    gmesh.extract_slice("k", 1)

    assert len(calls) == 0


# ---------------------------------------------------------------------------
# quad_slice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slice_dim, slice_ind", [("i", 4), ("j", 5), ("k", 1)])
def test_quad_slice_covers_the_same_cells_as_extract_slice(
    grid_mesh, slice_dim, slice_ind
):
    quads = grid_mesh.quad_slice(slice_dim, slice_ind)
    hexes = grid_mesh.extract_slice(slice_dim, slice_ind)

    assert quads.n_cells == hexes.n_cells
    np.testing.assert_array_equal(
        sorted(quads.cell_data[ACTIVE_INDEX]), sorted(hexes.cell_data[ACTIVE_INDEX])
    )


def test_quad_slice_areas_match_the_grid_geometry(grid_mesh):
    # SPE1CASE1 cells are 1000x1000 ft with layer thicknesses of 20, 30 and 50 ft, so a
    # j-slice spans 10 columns of (20 + 30 + 50) ft x 1000 ft
    quads = grid_mesh.quad_slice("j", 5)

    np.testing.assert_allclose(quads.area, 10 * 1000 * (20 + 30 + 50))


def test_quad_slice_produces_quads_not_triangles(grid_mesh):
    quads = grid_mesh.quad_slice("k", 0)

    assert quads.n_points == 4 * quads.n_cells
    assert (quads.faces.reshape(-1, 5)[:, 0] == 4).all()


def test_quad_slice_validates_its_arguments(grid_mesh):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        grid_mesh.quad_slice("x", 0)
    with pytest.raises(ValueError, match="out of bounds"):
        grid_mesh.quad_slice("k", 3)


def test_quad_slice_does_not_need_the_full_mesh(case1):
    gmesh = GridMesh(case1)

    gmesh.quad_slice("k", 0)

    assert gmesh._mesh is None  # the expensive hexahedral build was never triggered


# ---------------------------------------------------------------------------
# cell_centers / slice_cell_centers
# ---------------------------------------------------------------------------


def test_cell_centers_places_one_point_per_active_cell(grid_mesh):
    centers = grid_mesh.cell_centers()

    assert centers.n_points == 300  # 10x10x3, fully active
    np.testing.assert_array_equal(
        sorted(centers.cell_data[ACTIVE_INDEX]), np.arange(300)
    )


def test_cell_centers_matches_the_hexahedral_meshs_own_centers(case1):
    # Two separate GridMesh instances, so building one's full mesh for comparison cannot
    # accidentally make the other's cell_centers() look cheap when it was not
    cheap = GridMesh(case1).cell_centers()
    from_hex = GridMesh(case1).mesh.cell_centers()

    np.testing.assert_allclose(cheap.points, from_hex.points, atol=1e-3)


def test_cell_centers_does_not_need_the_full_mesh(case1):
    gmesh = GridMesh(case1)

    gmesh.cell_centers()

    assert gmesh._mesh is None  # the expensive hexahedral build was never triggered


@pytest.mark.parametrize("slice_dim, slice_ind", [("i", 4), ("j", 5), ("k", 1)])
def test_slice_cell_centers_covers_the_same_cells_as_quad_slice(
    grid_mesh, slice_dim, slice_ind
):
    centers = grid_mesh.slice_cell_centers(slice_dim, slice_ind)
    quads = grid_mesh.quad_slice(slice_dim, slice_ind)

    assert centers.n_points == quads.n_cells
    np.testing.assert_array_equal(
        sorted(centers.cell_data[ACTIVE_INDEX]), sorted(quads.cell_data[ACTIVE_INDEX])
    )


def test_slice_cell_centers_sits_on_the_slice_face_not_mid_cell(grid_mesh):
    # SPE1CASE1's k=0 layer spans depth 8325-8345 ft; the face centre for a k-slice must sit
    # exactly on the shallow face, not at the layer's mid-depth. z points up (see
    # _read_corners), so this depth comes back negated.
    centers = grid_mesh.slice_cell_centers("k", 0)

    np.testing.assert_allclose(centers.points[:, 2], -8325.0)


def test_slice_cell_centers_validates_its_arguments(grid_mesh):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        grid_mesh.slice_cell_centers("x", 0)
    with pytest.raises(ValueError, match="out of bounds"):
        grid_mesh.slice_cell_centers("k", 3)


def test_slice_cell_centers_does_not_need_the_full_mesh(case1):
    gmesh = GridMesh(case1)

    gmesh.slice_cell_centers("k", 0)

    assert gmesh._mesh is None  # the expensive hexahedral build was never triggered


# ---------------------------------------------------------------------------
# Point welding
# ---------------------------------------------------------------------------


def test_welding_merges_shared_corner_points(grid_mesh):
    # A 10x10x3 Cartesian box has 11x11 pillars carrying 4 distinct depths each
    assert grid_mesh.mesh.n_points == 11 * 11 * 4


def test_welding_leaves_cells_and_geometry_untouched(case1):
    welded = GridMesh(case1).mesh
    unwelded = GridMesh(case1, weld=False).mesh

    assert unwelded.n_points == 8 * unwelded.n_cells  # one copy per cell corner
    assert welded.n_points < unwelded.n_points
    assert welded.n_cells == unwelded.n_cells
    np.testing.assert_allclose(welded.volume, unwelded.volume, rtol=1e-9)
    np.testing.assert_array_equal(
        welded.cell_data[ACTIVE_INDEX], unwelded.cell_data[ACTIVE_INDEX]
    )


def test_welding_keeps_faulted_cells_apart():
    # Two cells side by side in i. Without a throw they share a face and its 4 corners get
    # merged; with a throw nothing coincides, so all 16 points must survive. This is what
    # the zero tolerance protects - a fault must not be welded shut.
    juxtaposed = _bypass_init(_FaultedPairEGrid(throw=0.0))
    faulted = _bypass_init(_FaultedPairEGrid(throw=0.5))

    assert juxtaposed.mesh.n_points == 12  # 16 corners, 4 of them shared
    assert faulted.mesh.n_points == 16


# ---------------------------------------------------------------------------
# _is_mirrored / pinched-out cells (synthetic grids)
# ---------------------------------------------------------------------------


def test_mirrored_grid_still_yields_positive_volumes():
    gmesh = _bypass_init(_BoxEGrid(nx=2, ny=2, nz=2, z_sign=-1))

    volumes = gmesh.mesh.compute_cell_sizes()["Volume"]
    assert gmesh.mesh.n_cells == 8
    assert (volumes > 0).all()


def test_standard_grid_is_not_reported_as_mirrored():
    gmesh = _bypass_init(_BoxEGrid(nx=2, ny=2, nz=2, z_sign=1))

    volumes = gmesh.mesh.compute_cell_sizes()["Volume"]
    assert (volumes > 0).all()


def test_pinched_out_cells_are_dropped_and_recorded_in_active_index():
    # SPE1CASE1 has no NaN corners, so pinch-outs need a synthetic grid
    gmesh = _bypass_init(_BoxEGrid(nx=2, ny=2, nz=2, nan_cells=(1, 5)))

    assert gmesh.mesh.n_cells == 6  # 8 cells less the 2 pinched out
    np.testing.assert_array_equal(
        gmesh.mesh.cell_data[ACTIVE_INDEX], [0, 2, 3, 4, 6, 7]
    )
    assert np.isfinite(gmesh.mesh.points).all()
