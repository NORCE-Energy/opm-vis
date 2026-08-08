""" Unit tests for opm_vis.pvplot.mesh, backed by the SPE1CASE1 EGRID test dataset """
import shutil

import numpy as np
import pytest

from opm_vis.pvplot.mesh import ACTIVE_INDEX, GridMesh

# The case1/data_dir fixtures come from conftest.py. SPE1CASE1 is a fully active,
# standard-oriented 10x10x3 Cartesian box grid: it pins down the corner ordering and the
# active-index invariant, but has no pinched-out cells and is not mirrored, so those two
# branches use small synthetic stand-ins exposing just the EGrid interface GridMesh needs.


@pytest.fixture(scope="module")
def grid_mesh(case1):
    return GridMesh(case1)


def _bypass_init(egrid):
    """Create a GridMesh around a synthetic EGrid without touching the filesystem."""
    obj = object.__new__(GridMesh)
    obj.egrid = egrid
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

    def xyz_from_active_index(self, act):
        if act in self._nan_cells:
            return [np.nan] * 8, [np.nan] * 8, [np.nan] * 8
        i, j, k = self._active[act]
        xs = [float(i + (c & 1)) for c in range(8)]
        ys = [float(j + ((c >> 1) & 1)) for c in range(8)]
        zs = [float(self._z_sign * (k + ((c >> 2) & 1))) for c in range(8)]
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
