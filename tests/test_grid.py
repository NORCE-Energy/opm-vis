""" Unit tests for opm_vis.utils.grid, backed by the SPE1CASE1 EGRID test dataset """
import shutil
from pathlib import Path

import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.utils.grid import GridSlice2D, GridSlice3D

DATA_DIR = Path(__file__).parent / "data"
CASE = str(DATA_DIR / "SPE1CASE1")  # "path" prefix, as grid.py's glob() expects

# SPE1CASE1 is a fully active, standard-oriented 10x10x3 Cartesian box grid (no
# inactive cells, no NaNs). A handful of edge cases below - each covering a specific
# bug fix - can't be produced from that real dataset, so they use small synthetic
# stand-ins exposing just the interface the method under test needs.


@pytest.fixture(scope="module")
def real_egrid():
    return EGrid(str(DATA_DIR / "SPE1CASE1.EGRID"))


def _bypass_init(cls, egrid, **attrs):
    """Create an instance of a _GridSlice subclass without running __init__."""
    obj = object.__new__(cls)
    obj.egrid = egrid
    for name, value in attrs.items():
        setattr(obj, name, value)
    return obj


# ---------------------------------------------------------------------------
# __init__ validation (through the real constructor, real EGRID file)
# ---------------------------------------------------------------------------


def test_invalid_slice_dim_raises_type_error():
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        GridSlice3D(CASE, "x", 0)


def test_slice_ind_out_of_bounds_raises_value_error():
    with pytest.raises(ValueError, match="out of bounds"):
        GridSlice3D(CASE, "k", 3)  # SPE1CASE1 has 3 layers: valid range is 0-2


def test_missing_egrid_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        GridSlice3D(str(tmp_path / "CASE"), "k", 0)


def test_multiple_egrid_files_warns_and_still_validates(tmp_path):
    shutil.copy(DATA_DIR / "SPE1CASE1.EGRID", tmp_path / "CASE1.EGRID")
    shutil.copy(DATA_DIR / "SPE1CASE1.EGRID", tmp_path / "CASE2.EGRID")

    with pytest.warns(UserWarning, match="Multiple .EGRID files"):
        with pytest.raises(TypeError):
            GridSlice3D(str(tmp_path / "CASE"), "invalid", 0)


# ---------------------------------------------------------------------------
# _active_index_from_end
# ---------------------------------------------------------------------------


def test_active_index_from_end_finds_far_active_cell(real_egrid):
    obj = _bypass_init(GridSlice3D, real_egrid)
    nx = real_egrid.dimension[0]

    expected = real_egrid.active_index(nx - 1, 0, 0)
    assert obj._active_index_from_end(0, 0, 0, axis=0, origin_axis=0) == expected


class _PartiallyActiveLine:
    """A single grid line along axis 0, with some cells inactive - SPE1CASE1 has no
    inactive cells, so this covers the "no active cell found"/"stop at origin" edge
    cases of _active_index_from_end on its own."""

    def __init__(self, size, inactive):
        self.dimension = (size, 1, 1)
        self._inactive = inactive

    def active_index(self, i, j, k):
        del j, k
        return -1 if i in self._inactive else i


def test_active_index_from_end_returns_minus_one_when_line_fully_inactive():
    egrid = _PartiallyActiveLine(size=4, inactive={0, 1, 2, 3})
    obj = _bypass_init(GridSlice3D, egrid)

    assert obj._active_index_from_end(0, 0, 0, axis=0, origin_axis=0) == -1


def test_active_index_from_end_never_searches_past_origin():
    egrid = _PartiallyActiveLine(size=4, inactive=set())
    obj = _bypass_init(GridSlice3D, egrid)

    # origin_axis=2: only candidates 3 and 2 may be tried, even though 0 and 1
    # are also active - the search must not go past the origin.
    assert obj._active_index_from_end(2, 0, 0, axis=0, origin_axis=2) == 3


# ---------------------------------------------------------------------------
# is_aligned
# ---------------------------------------------------------------------------


def test_is_aligned_for_spe1_grid(real_egrid):
    obj = _bypass_init(GridSlice3D, real_egrid)

    # Ground truth from the real dataset's own corner-point ordering
    assert obj.is_aligned() == False  # noqa: E712 (np.bool_, not identical to bool)


class _BoxEGrid:
    """Minimal synthetic box grid for is_aligned edge cases: a grid known to be
    aligned/mirrored by construction (to confirm both branches of the sign check),
    and a degenerate line-grid that can never form a valid parallelepiped."""

    def __init__(self, nx, ny, nz, z_sign=-1):
        self.dimension = (nx, ny, nz)
        self._z_sign = z_sign
        self._active = [(i, j, k) for k in range(nz) for j in range(ny) for i in range(nx)]

    def active_index(self, i, j, k):
        try:
            return self._active.index((i, j, k))
        except ValueError:
            return -1

    def ijk_from_active_index(self, act):
        return list(self._active[act])

    def xyz_from_active_index(self, act):
        i, j, k = self._active[act]
        xs = [float(i + (c & 1)) for c in range(8)]
        ys = [float(j + ((c >> 1) & 1)) for c in range(8)]
        zs = [float(self._z_sign * (k + ((c >> 2) & 1))) for c in range(8)]
        return xs, ys, zs


def test_is_aligned_true_for_aligned_grid():
    egrid = _BoxEGrid(nx=3, ny=3, nz=3, z_sign=-1)
    obj = _bypass_init(GridSlice3D, egrid)

    assert obj.is_aligned() == True  # noqa: E712 (np.bool_, not identical to bool)


def test_is_aligned_false_for_mirrored_grid():
    egrid = _BoxEGrid(nx=3, ny=3, nz=3, z_sign=1)
    obj = _bypass_init(GridSlice3D, egrid)

    assert obj.is_aligned() == False  # noqa: E712 (np.bool_, not identical to bool)


def test_is_aligned_warns_when_no_parallelepiped_can_be_built():
    # nx = ny = 1 collapses every candidate vector to zero length; with enough
    # active cells to survive all 10 retries, alignment can never be determined.
    egrid = _BoxEGrid(nx=1, ny=1, nz=15)
    obj = _bypass_init(GridSlice3D, egrid)

    with pytest.warns(UserWarning, match="not successful"):
        aligned = obj.is_aligned()
    assert aligned is False


# ---------------------------------------------------------------------------
# _compute_active_indices
# ---------------------------------------------------------------------------


def test_compute_active_indices_matches_full_plane_for_spe1(real_egrid):
    nx, ny, _ = real_egrid.dimension
    obj = _bypass_init(
        GridSlice3D, real_egrid, slice_dim="k", slice_ind=1, nx1=nx, nx2=ny, act=[]
    )

    obj._compute_active_indices()

    expected = [real_egrid.active_index(i, j, 1) for i in range(nx) for j in range(ny)]
    assert obj.act == expected
    assert len(obj.act) == nx * ny  # SPE1CASE1 has no inactive cells


def test_compute_active_indices_skips_inactive_cells():
    # SPE1CASE1 has no inactive cells, so the skip-if-inactive branch needs a
    # small synthetic (i, j) plane instead.
    inactive = {(1, 0)}

    class _PlaneEGrid:
        dimension = (3, 2, 1)

        def active_index(self, i, j, k):
            del k
            return -1 if (i, j) in inactive else i + j * 3

    egrid = _PlaneEGrid()
    obj = _bypass_init(
        GridSlice3D, egrid, slice_dim="k", slice_ind=0, nx1=3, nx2=2, act=[]
    )

    obj._compute_active_indices()

    expected = [egrid.active_index(i, j, 0) for i in range(3) for j in range(2)]
    expected = [act for act in expected if act >= 0]
    assert obj.act == expected
    assert len(obj.act) == 5  # one of the 6 (i, j) cells is inactive


# ---------------------------------------------------------------------------
# _cell_corners
# ---------------------------------------------------------------------------


def test_cell_corners_matches_known_coordinates_for_spe1(real_egrid):
    obj = _bypass_init(GridSlice3D, real_egrid, slice_dim="k", act=[0])

    obj._cell_corners()

    assert obj.act == [0]
    # Cell (i=0, j=0, k=0) is a 1000x1000 ft column with its top face at z=8325 ft
    np.testing.assert_allclose(obj.corn[0, :, 2], 8325.0)
    assert obj.corn[0, :, 0].min() == 0.0
    assert obj.corn[0, :, 0].max() == 1000.0
    assert obj.corn[0, :, 1].min() == 0.0
    assert obj.corn[0, :, 1].max() == 1000.0


def test_cell_corners_drops_rows_with_nan():
    # A degenerate/pinched-out cell can produce NaN corners in real data; SPE1CASE1
    # has none, so this uses a small stub returning pre-set corner coordinates.
    corners = {
        10: (list(range(8)), list(range(8)), list(range(8))),
        20: ([float("nan")] * 8, [0.0] * 8, [0.0] * 8),
        30: ([0.0] * 8, [0.0] * 8, [0.0] * 8),
    }

    class _StubCornerEGrid:
        def xyz_from_active_index(self, act):
            return corners[act]

    obj = _bypass_init(
        GridSlice3D, _StubCornerEGrid(), slice_dim="k", act=[10, 20, 30]
    )

    obj._cell_corners()

    assert obj.act == [10, 30]
    assert obj.corn.shape == (2, 4, 3)
    # local indices for "k" slice are [0, 2, 3, 1]
    np.testing.assert_array_equal(obj.corn[0, :, 0], [0, 2, 3, 1])


# ---------------------------------------------------------------------------
# _cell_centers
# ---------------------------------------------------------------------------


def test_cell_centers_raises_if_corners_not_computed():
    obj = _bypass_init(GridSlice3D, egrid=None, corn=np.empty(0))

    with pytest.raises(ValueError, match="have not been calculated"):
        obj._cell_centers()


def test_cell_centers_averages_corners():
    corn = np.array([[[1, 1, 1], [3, 3, 3], [5, 5, 5], [7, 7, 7]]], dtype=float)
    obj = _bypass_init(GridSlice3D, egrid=None, corn=corn)

    obj._cell_centers()

    np.testing.assert_allclose(obj.cent, [[4.0, 4.0, 4.0]])


# ---------------------------------------------------------------------------
# GridSlice3D / GridSlice2D accessors
# ---------------------------------------------------------------------------


def test_grid_slice_3d_accessors_return_stored_arrays():
    corn = np.zeros((2, 4, 3))
    cent = np.zeros((2, 3))
    obj = _bypass_init(GridSlice3D, egrid=None, corn=corn, cent=cent)

    assert obj.cell_corners() is corn
    assert obj.cell_centers() is cent


def test_grid_slice_2d_drops_slice_axis():
    # i-slice: slice_axis = [1, 2] (y, z kept; x dropped)
    corn = np.zeros((2, 4, 3))
    corn[..., 0] = 100.0  # x
    corn[..., 1] = 1.0  # y
    corn[..., 2] = 2.0  # z
    cent = np.zeros((2, 3))
    cent[:, 0] = 100.0
    cent[:, 1] = 1.0
    cent[:, 2] = 2.0

    obj = _bypass_init(GridSlice2D, egrid=None, corn=corn, cent=cent, slice_axis=[1, 2])

    corners_2d = obj.cell_corners()
    assert corners_2d.shape == (2, 4, 2)
    np.testing.assert_allclose(corners_2d[..., 0], 1.0)
    np.testing.assert_allclose(corners_2d[..., 1], 2.0)

    centers_2d = obj.cell_centers()
    assert centers_2d.shape == (2, 2)
    np.testing.assert_allclose(centers_2d, [[1.0, 2.0]] * 2)


# ---------------------------------------------------------------------------
# Full construction (happy path), against the real EGRID file
# ---------------------------------------------------------------------------


def test_grid_slice_3d_full_construction():
    slc = GridSlice3D(CASE, "k", 1)

    assert len(slc.active_indices()) == 100  # 10x10 plane, all active
    assert slc.cell_corners().shape == (100, 4, 3)
    assert slc.cell_centers().shape == (100, 3)
    # Ground truth from the real dataset's own corner-point ordering
    assert slc.aligned_grid == False  # noqa: E712 (np.bool_, not identical to bool)


def test_grid_slice_2d_full_construction():
    slc = GridSlice2D(CASE, "k", 1)

    assert slc.cell_corners().shape == (100, 4, 2)
    assert slc.cell_centers().shape == (100, 2)
