""" Unit tests for opm_vis.plot.faults, backed by the SPE1CASE1 test dataset """
import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.plot.faults import fault_edges
from opm_vis.utils.fault import FaultFace

# The data_dir fixture comes from conftest.py. SPE1CASE1 is a fully active 10x10x3 grid with
# 1000x1000 ft cells and no NaN corner points - see conftest.py's own docstring - so it is used
# here purely for its real geometry, not for anything fault-specific.


@pytest.fixture(scope="module")
def egrid(data_dir):
    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


# ---------------------------------------------------------------------------
# fault_edges against the real dataset
# ---------------------------------------------------------------------------


def test_x_fault_gives_one_segment_per_j_on_a_k_slice(egrid):
    # 'X' face at i=4 (0-based), spanning j=0..2, k=0..2; on a k=0 slice, one segment per j
    face = FaultFace(4, 4, 0, 2, 0, 2, "X")

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.segments.shape == (3, 2, 3)


def test_x_fault_segment_sits_at_the_high_i_side_of_the_cell(egrid):
    # Cell (4, 0, 0) spans x in [4000, 5000], y in [0, 1000]; the 'X' (high-i) face sits at
    # x=5000. OPM's native (depth-positive-down) z is kept as-is here, unlike
    # opm_vis.pvplot.faults.
    face = FaultFace(4, 4, 0, 0, 0, 0, "X")

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.segments.shape == (1, 2, 3)
    np.testing.assert_allclose(result.segments[0, :, 0], 5000.0)
    assert sorted(result.segments[0, :, 1]) == [0.0, 1000.0]
    np.testing.assert_allclose(result.segments[0, :, 2], 8325.0)


def test_y_fault_segment_sits_at_the_high_j_side_of_the_cell(egrid):
    face = FaultFace(0, 0, 5, 5, 0, 0, "Y")

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.segments.shape == (1, 2, 3)
    np.testing.assert_allclose(result.segments[0, :, 1], 6000.0)
    assert sorted(result.segments[0, :, 0]) == [0.0, 1000.0]


def test_fault_matching_the_slices_own_axis_gives_no_segments(egrid):
    # An 'X' fault is coincident with the whole plane of an i-slice, not a line on it
    face = FaultFace(4, 4, 0, 9, 0, 2, "X")

    result = fault_edges(egrid, {"F": [face]}, "i", 4)

    assert result.is_empty()


def test_fault_out_of_the_slices_range_gives_no_segments(egrid):
    face = FaultFace(4, 4, 0, 9, 0, 2, "X")

    result = fault_edges(egrid, {"F": [face]}, "k", 5)  # k1..k2 is 0..2

    assert result.is_empty()


def test_several_faults_are_concatenated(egrid):
    faces_by_name = {
        "F1": [FaultFace(4, 4, 0, 0, 0, 0, "X")],
        "F2": [FaultFace(0, 0, 5, 5, 0, 0, "Y")],
    }

    result = fault_edges(egrid, faces_by_name, "k", 0)

    assert result.segments.shape == (2, 2, 3)
    assert result.label_names == ["F1", "F2"]


def test_no_faces_gives_an_empty_result(egrid):
    result = fault_edges(egrid, {}, "k", 0)

    assert result.is_empty()
    assert result.label_names == []
    assert result.label_points.shape == (0, 3)


# ---------------------------------------------------------------------------
# fault_edges label anchors
# ---------------------------------------------------------------------------


def test_label_point_is_the_shallowest_point_of_its_own_fault(egrid):
    # Box spans k=0..2 (depths 8325-8425); on an i-slice all three layers are visible, so the
    # label anchors at the shallowest of them, 8325 - not the single layer a k-slice would see.
    face = FaultFace(0, 0, 5, 5, 0, 2, "Y")

    result = fault_edges(egrid, {"F": [face]}, "i", 0)

    assert result.label_names == ["F"]
    np.testing.assert_allclose(result.label_points[0, 2], 8325.0)


def test_label_excludes_a_fault_with_no_surviving_segment(egrid):
    faces_by_name = {
        "IN": [FaultFace(4, 4, 0, 0, 0, 0, "X")],
        "OUT": [FaultFace(4, 4, 0, 9, 0, 2, "X")],  # coincident with an i-slice
    }

    result = fault_edges(egrid, faces_by_name, "i", 4)

    assert result.label_names == []


# ---------------------------------------------------------------------------
# fault_edges every slice_dim / in-plane direction combination
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slice_dim,directions", [("i", "YZ"), ("j", "XZ"), ("k", "XY")]
)
def test_every_in_plane_direction_gives_a_segment(egrid, slice_dim, directions):
    for letter in directions:
        for sign in ("", "-"):
            face = FaultFace(1, 1, 1, 1, 1, 1, f"{letter}{sign}")
            slice_ind = {"i": 1, "j": 1, "k": 1}[slice_dim]

            result = fault_edges(egrid, {"F": [face]}, slice_dim, slice_ind)

            assert result.segments.shape == (1, 2, 3), (slice_dim, letter, sign)


@pytest.mark.parametrize("slice_dim,own_letter", [("i", "X"), ("j", "Y"), ("k", "Z")])
def test_the_slices_own_direction_gives_no_segment(egrid, slice_dim, own_letter):
    for sign in ("", "-"):
        face = FaultFace(1, 1, 1, 1, 1, 1, f"{own_letter}{sign}")
        slice_ind = {"i": 1, "j": 1, "k": 1}[slice_dim]

        result = fault_edges(egrid, {"F": [face]}, slice_dim, slice_ind)

        assert result.is_empty()


# ---------------------------------------------------------------------------
# fault_edges edge cases (stub EGrid: inactive/pinched-out cells, MAPAXES)
# ---------------------------------------------------------------------------


class _StubEGrid:
    """Minimal stand-in exposing exactly what fault_edges needs: active_index and xyz_from_ijk.
    Each active cell is a unit cube from (i, j, k) to (i+1, j+1, k+1), using OPM's own corner
    bit convention (bit 0 = i, bit 1 = j, bit 2 = k)."""

    def __init__(self, active, pinched=(), dxdy=(0.0, 0.0)):
        self._active = set(active)
        self._pinched = set(pinched)
        self._dxdy = dxdy

    def active_index(self, i, j, k):
        return 0 if (i, j, k) in self._active else -1

    def xyz_from_ijk(self, i, j, k, apply_mapaxes=False):
        if (i, j, k) in self._pinched:
            return [np.nan] * 8, [np.nan] * 8, [np.nan] * 8

        dx, dy = self._dxdy if apply_mapaxes else (0.0, 0.0)
        xs = [float(i + (c & 1)) + dx for c in range(8)]
        ys = [float(j + ((c >> 1) & 1)) + dy for c in range(8)]
        zs = [float(k + ((c >> 2) & 1)) for c in range(8)]
        return xs, ys, zs


def test_inactive_cells_are_skipped():
    egrid = _StubEGrid(active={(0, 0, 0)})
    face = FaultFace(0, 1, 0, 0, 0, 0, "X")  # i=0 active, i=1 not; slice at k=0 sees both

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.segments.shape == (1, 2, 3)


def test_pinched_out_cells_are_skipped():
    egrid = _StubEGrid(active={(0, 0, 0), (1, 0, 0)}, pinched={(1, 0, 0)})
    face = FaultFace(0, 1, 0, 0, 0, 0, "X")

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.segments.shape == (1, 2, 3)


def test_every_cell_inactive_or_pinched_gives_no_segments():
    egrid = _StubEGrid(active=set())
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_edges(egrid, {"F": [face]}, "k", 0)

    assert result.is_empty()


def test_apply_mapaxes_true_translates_coordinates():
    egrid = _StubEGrid(active={(0, 0, 0)}, dxdy=(1000.0, 2000.0))
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    untranslated = fault_edges(egrid, {"F": [face]}, "k", 0, apply_mapaxes=False)
    translated = fault_edges(egrid, {"F": [face]}, "k", 0, apply_mapaxes=True)

    np.testing.assert_allclose(
        translated.segments[..., 0] - untranslated.segments[..., 0], 1000.0
    )
    np.testing.assert_allclose(
        translated.segments[..., 1] - untranslated.segments[..., 1], 2000.0
    )
