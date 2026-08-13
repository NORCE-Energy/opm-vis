""" Unit tests for opm_vis.utils.grid, backed by the SPE1CASE1 EGRID test dataset """
import shutil

import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.utils.grid import (
    GridSlice2D,
    GridSlice3D,
    slice_active_indices,
    slice_layer_grid,
    slice_range_first_active_indices,
    slice_range_layer_grid,
)

# The case1/data_dir fixtures come from conftest.py. SPE1CASE1 is a fully active,
# standard-oriented 10x10x3 Cartesian box grid (no inactive cells, no NaNs). A handful of
# edge cases below - each covering a specific bug fix - can't be produced from that real
# dataset, so they use small synthetic stand-ins exposing just the interface the method
# under test needs.


@pytest.fixture(scope="module")
def real_egrid(data_dir):
    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


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


def test_invalid_slice_dim_raises_type_error(case1):
    with pytest.raises(TypeError, match="slice dimension is not valid"):
        GridSlice3D(case1, "x", 0)


def test_slice_ind_out_of_bounds_raises_value_error(case1):
    with pytest.raises(ValueError, match="out of bounds"):
        GridSlice3D(case1, "k", 3)  # SPE1CASE1 has 3 layers: valid range is 0-2


def test_missing_egrid_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        GridSlice3D(str(tmp_path / "CASE"), "k", 0)


def test_multiple_egrid_files_warns_and_still_validates(tmp_path, data_dir):
    shutil.copy(data_dir / "SPE1CASE1.EGRID", tmp_path / "CASE1.EGRID")
    shutil.copy(data_dir / "SPE1CASE1.EGRID", tmp_path / "CASE2.EGRID")

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

    def xyz_from_active_index(self, act, apply_mapaxes=False):
        del apply_mapaxes  # no MAPAXES on this synthetic grid
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
# slice_active_indices
# ---------------------------------------------------------------------------


def test_slice_active_indices_matches_full_plane_for_spe1(real_egrid):
    nx, ny, _ = real_egrid.dimension

    act = slice_active_indices(real_egrid, "k", 1)

    expected = [real_egrid.active_index(i, j, 1) for i in range(nx) for j in range(ny)]
    assert act == expected
    assert len(act) == nx * ny  # SPE1CASE1 has no inactive cells


def test_slice_active_indices_skips_inactive_cells():
    # SPE1CASE1 has no inactive cells, so the skip-if-inactive branch needs a
    # small synthetic (i, j) plane instead.
    inactive = {(1, 0)}

    class _PlaneEGrid:
        dimension = (3, 2, 1)

        def active_index(self, i, j, k):
            del k
            return -1 if (i, j) in inactive else i + j * 3

    egrid = _PlaneEGrid()

    act = slice_active_indices(egrid, "k", 0)

    expected = [egrid.active_index(i, j, 0) for i in range(3) for j in range(2)]
    expected = [a for a in expected if a >= 0]
    assert act == expected
    assert len(act) == 5  # one of the 6 (i, j) cells is inactive


def test_slice_active_indices_reads_no_corners(real_egrid, monkeypatch):
    # The whole point of pulling this out of _GridSlice: getting a slice's active cells must
    # never need a single corner read, unlike GridSlice3D's own __init__.
    def fail(*_args, **_kwargs):
        raise AssertionError("slice_active_indices should never read any cell corners")

    monkeypatch.setattr(EGrid, "xyz_from_active_index", fail)

    act = slice_active_indices(real_egrid, "k", 1)

    assert len(act) == 100  # 10x10 k-slice of SPE1CASE1


# ---------------------------------------------------------------------------
# slice_layer_grid / slice_range_layer_grid
# ---------------------------------------------------------------------------


def test_slice_layer_grid_matches_full_plane_for_spe1(real_egrid):
    nx, ny, _ = real_egrid.dimension

    layer = slice_layer_grid(real_egrid, "k", 1)

    expected = [[real_egrid.active_index(i, j, 1) for j in range(ny)] for i in range(nx)]
    assert layer.shape == (nx, ny)
    np.testing.assert_array_equal(layer, expected)
    assert (layer >= 0).all()  # SPE1CASE1 has no inactive cells


def test_slice_layer_grid_keeps_minus_one_for_inactive_cells():
    # slice_active_indices() drops inactive positions; slice_layer_grid() must keep them as -1
    # instead, so that position (ind_1, ind_2) means the same thing on every layer.
    inactive = {(1, 0)}

    class _PlaneEGrid:
        dimension = (3, 2, 1)

        def active_index(self, i, j, k):
            del k
            return -1 if (i, j) in inactive else i + j * 3

    egrid = _PlaneEGrid()

    layer = slice_layer_grid(egrid, "k", 0)

    assert layer.shape == (3, 2)
    assert layer[1, 0] == -1
    assert (layer >= 0).sum() == 5  # every other (i, j) position is active


def test_slice_range_layer_grid_stacks_each_layer_in_order(real_egrid):
    stacked = slice_range_layer_grid(real_egrid, "k", 0, 2)

    assert stacked.shape == (3, 10, 10)
    for k in range(3):
        np.testing.assert_array_equal(stacked[k], slice_layer_grid(real_egrid, "k", k))


def test_slice_range_layer_grid_single_layer_range(real_egrid):
    stacked = slice_range_layer_grid(real_egrid, "k", 1, 1)

    assert stacked.shape == (1, 10, 10)
    np.testing.assert_array_equal(stacked[0], slice_layer_grid(real_egrid, "k", 1))


# ---------------------------------------------------------------------------
# slice_range_first_active_indices
# ---------------------------------------------------------------------------


def test_slice_range_first_active_indices_matches_slice_active_indices_when_fully_active(
    real_egrid,
):
    # With no inactive cells in the range, the first active layer is always start_ind's own -
    # same result as slice_active_indices(start_ind).
    act = slice_range_first_active_indices(real_egrid, "k", 0, 2)

    assert act == slice_active_indices(real_egrid, "k", 0)


class _ColumnEGrid:
    """
    3x2x3 (i, j, k) grid with a handful of inactive cells, for surface tests.

    Per (i, j) column: (0,0), (0,1), (1,1) and (2,0) are active on every layer; (1,0) is
    inactive on layers 0 and 1 (active only on 2); (2,1) is inactive on layer 0 only (active on
    1 and 2).
    """

    dimension = (3, 2, 3)

    _inactive = {(1, 0, 0), (1, 0, 1), (2, 1, 0)}

    def active_index(self, i, j, k):
        if (i, j, k) in self._inactive:
            return -1
        # A stable, order-preserving index scheme is enough for these tests: only which
        # cells are >=0 (and, for slice_range_first_active_indices, which layer is found
        # first) is checked, never the index values' own meaning.
        return (k * 2 + j) * 3 + i


def test_slice_range_first_active_indices_skips_an_inactive_start_layer():
    egrid = _ColumnEGrid()

    # i outer, j inner - same nested-loop order as slice_active_indices. (1, 0) skips its
    # inactive layers 0 and 1 to reach layer 2; (2, 1) skips its inactive layer 0 to reach 1;
    # every other position uses its own (active) layer 0.
    act = slice_range_first_active_indices(egrid, "k", 0, 2)

    assert act == [
        egrid.active_index(0, 0, 0),
        egrid.active_index(0, 1, 0),
        egrid.active_index(1, 0, 2),
        egrid.active_index(1, 1, 0),
        egrid.active_index(2, 0, 0),
        egrid.active_index(2, 1, 1),
    ]


def test_slice_range_first_active_indices_omits_a_position_inactive_throughout():
    egrid = _ColumnEGrid()

    # Restricted to layer 1 alone: (1, 0) is inactive there (and the range no longer reaches
    # its active layer 2), so it has nothing active in range and must be omitted entirely.
    # Every other position is active on layer 1 itself.
    act = slice_range_first_active_indices(egrid, "k", 1, 1)

    assert act == [
        egrid.active_index(0, 0, 1),
        egrid.active_index(0, 1, 1),
        egrid.active_index(1, 1, 1),
        egrid.active_index(2, 0, 1),
        egrid.active_index(2, 1, 1),
    ]


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
        def xyz_from_active_index(self, act, apply_mapaxes=False):
            del apply_mapaxes
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


def test_grid_slice_3d_full_construction(case1):
    slc = GridSlice3D(case1, "k", 1)

    assert len(slc.active_indices()) == 100  # 10x10 plane, all active
    assert slc.cell_corners().shape == (100, 4, 3)
    assert slc.cell_centers().shape == (100, 3)
    # Ground truth from the real dataset's own corner-point ordering
    assert slc.aligned_grid == False  # noqa: E712 (np.bool_, not identical to bool)


# ---------------------------------------------------------------------------
# Full construction with surface=True (--calculator surface)
# ---------------------------------------------------------------------------


class _GapEGrid:
    """
    2x1x2 (i, j, k) box grid with one inactive cell (i=1, j=0, k=0), for surface's full
    construction path - SPE1CASE1 itself has no inactive cells to exercise this with.
    """

    dimension = (2, 1, 2)
    _inactive = {(1, 0, 0)}

    def active_index(self, i, j, k):
        if (i, j, k) in self._inactive:
            return -1
        return (k * 1 + j) * 2 + i

    def ijk_from_active_index(self, act):
        for k in range(2):
            for j in range(1):
                for i in range(2):
                    if self.active_index(i, j, k) == act:
                        return [i, j, k]
        raise ValueError(act)

    def xyz_from_active_index(self, act, apply_mapaxes=False):
        del apply_mapaxes
        i, j, k = self.ijk_from_active_index(act)
        xs = [float(i + (c & 1)) for c in range(8)]
        ys = [float(j + ((c >> 1) & 1)) for c in range(8)]
        zs = [float(k + ((c >> 2) & 1)) for c in range(8)]
        return xs, ys, zs


def test_gridslice3d_surface_false_leaves_a_gap_at_an_inactive_position():
    obj = _bypass_init(GridSlice3D, _GapEGrid(), slice_dim="k", slice_ind=0, calc_end=None)

    obj._compute_active_indices()

    # (1, 0) is inactive on k=0, so the plain (single-layer) path just drops it: only (0, 0)'s
    # own cell is on the slice.
    assert len(obj.active_indices()) == 1
    assert obj.active_indices() == [_GapEGrid().active_index(0, 0, 0)]


def test_gridslice3d_surface_true_fills_the_gap_from_the_next_layer():
    egrid = _GapEGrid()
    obj = _bypass_init(GridSlice3D, egrid, slice_dim="k", slice_ind=0, calc_end=1)

    obj._compute_active_indices()
    obj._cell_corners()
    obj._cell_centers()

    # With surface's range extended to k=1, (1, 0) is now backed by its own active cell there
    # instead of being dropped - both lateral positions are present.
    assert len(obj.active_indices()) == 2
    assert egrid.active_index(0, 0, 0) in obj.active_indices()
    assert egrid.active_index(1, 0, 1) in obj.active_indices()

    # And its geometry is genuinely draped, not just relabelled: _INDICES["k"] picks each
    # cell's own top face (z equal to its own k, the same for all 4 corners), so (1, 0)'s
    # corners sit one unit deeper (z=1, from k=1) than (0, 0)'s (z=0, from its own k=0).
    corners = dict(zip(obj.active_indices(), obj.cell_corners()))
    np.testing.assert_allclose(corners[egrid.active_index(0, 0, 0)][:, 2], [0.0] * 4)
    np.testing.assert_allclose(corners[egrid.active_index(1, 0, 1)][:, 2], [1.0] * 4)


def test_grid_slice_2d_full_construction(case1):
    slc = GridSlice2D(case1, "k", 1)

    assert slc.cell_corners().shape == (100, 4, 2)
    assert slc.cell_centers().shape == (100, 2)
