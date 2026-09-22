""" Unit tests for opm_vis.pvplot.faults, backed by the SPE1CASE1 test dataset """
import numpy as np
import pytest

pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.pvplot.faults import fault_surfaces  # noqa: E402
from opm_vis.utils.fault import FaultFace  # noqa: E402

# The data_dir fixture comes from conftest.py. SPE1CASE1 is a fully active 10x10x3 grid with
# 1000x1000 ft cells and no NaN corner points - see conftest.py's own docstring - so it is used
# here purely for its real geometry, not for anything fault-specific.


@pytest.fixture(scope="module")
def egrid(data_dir):
    from opm.io.ecl import EGrid

    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


# ---------------------------------------------------------------------------
# fault_surfaces against the real dataset
# ---------------------------------------------------------------------------


def test_single_cell_box_gives_one_quad(egrid):
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    assert result.mesh.n_cells == 1
    assert result.mesh.n_points == 4


def test_x_face_quad_sits_at_the_high_i_side_of_the_cell(egrid):
    # Cell (0, 0, 0) spans x in [0, 1000], z (OPM depth) in [8325, 8345]; the 'X' (high-i) face
    # sits at x=1000. z points up in pvplot (see mesh._read_corners), so depths come back
    # negated.
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    np.testing.assert_allclose(result.mesh.points[:, 0], 1000.0)
    assert sorted(result.mesh.points[:, 2]) == [-8345.0, -8345.0, -8325.0, -8325.0]


def test_multi_cell_box_gives_one_quad_per_cell(egrid):
    # Spans j=0 and j=1 at fixed i=0, k=0: two cells
    face = FaultFace(0, 0, 0, 1, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    assert result.mesh.n_cells == 2
    assert result.mesh.n_points == 8


def test_several_faces_of_the_same_fault_are_concatenated(egrid):
    faces = [FaultFace(0, 0, 0, 0, 0, 0, "X"), FaultFace(5, 5, 5, 5, 1, 1, "Y-")]

    result = fault_surfaces(egrid, {"F": faces})

    assert result.mesh is not None
    assert result.mesh.n_cells == 2


def test_several_faults_are_concatenated(egrid):
    faces_by_name = {
        "F1": [FaultFace(0, 0, 0, 0, 0, 0, "X")],
        "F2": [FaultFace(5, 5, 5, 5, 1, 1, "Y-")],
    }

    result = fault_surfaces(egrid, faces_by_name)

    assert result.mesh is not None
    assert result.mesh.n_cells == 2


def test_no_faces_gives_no_mesh(egrid):
    result = fault_surfaces(egrid, {})

    assert result.mesh is None


def test_a_name_with_an_empty_face_list_gives_no_mesh(egrid):
    result = fault_surfaces(egrid, {"F": []})

    assert result.mesh is None


# ---------------------------------------------------------------------------
# fault_surfaces(slices=...)
# ---------------------------------------------------------------------------


def test_slices_restricts_to_boxes_overlapping_the_slice(egrid):
    face_in = FaultFace(0, 0, 0, 0, 0, 0, "X")  # i range [0, 0]
    face_out = FaultFace(5, 5, 0, 0, 0, 0, "X")  # i range [5, 5]

    result = fault_surfaces(egrid, {"IN": [face_in], "OUT": [face_out]}, slices=[("i", 0)])

    assert result.mesh is not None
    assert result.mesh.n_cells == 1


def test_slices_matches_anywhere_in_the_boxs_own_range(egrid):
    # Box spans k in [0, 2]; slice_ind=1 falls inside even though the face's own direction is
    # X. Once a box overlaps a slice at all, the whole box is drawn - all 3 of its cells, not
    # just the one at k=1.
    face = FaultFace(0, 0, 0, 0, 0, 2, "X")

    result = fault_surfaces(egrid, {"F": [face]}, slices=[("k", 1)])

    assert result.mesh is not None
    assert result.mesh.n_cells == 3


def test_slices_is_a_union_not_an_intersection(egrid):
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]}, slices=[("i", 9), ("i", 0)])

    assert result.mesh is not None
    assert result.mesh.n_cells == 1


def test_slices_excluding_every_face_gives_no_mesh(egrid):
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]}, slices=[("i", 9)])

    assert result.mesh is None


def test_no_slices_includes_every_face(egrid):
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]}, slices=None)

    assert result.mesh is not None
    assert result.mesh.n_cells == 1


def test_slices_rejects_an_invalid_dimension(egrid):
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    with pytest.raises(ValueError, match="not valid"):
        fault_surfaces(egrid, {"F": [face]}, slices=[("x", 0)])


# ---------------------------------------------------------------------------
# fault_surfaces label anchors
# ---------------------------------------------------------------------------


def test_label_names_match_the_faults_that_survived(egrid):
    faces_by_name = {
        "F1": [FaultFace(0, 0, 0, 0, 0, 0, "X")],
        "F2": [FaultFace(5, 5, 5, 5, 1, 1, "Y-")],
    }

    result = fault_surfaces(egrid, faces_by_name)

    assert result.label_names == ["F1", "F2"]
    assert result.label_points.shape == (2, 3)


def test_label_point_is_the_shallowest_corner_of_its_own_fault(egrid):
    # Cell (0, 0, 0) spans z (OPM depth) 8325-8345; z points up here (see mesh._read_corners),
    # so the shallowest corner is the largest z, i.e. -8325.
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.label_names == ["F"]
    np.testing.assert_allclose(result.label_points[0, 2], -8325.0)


def test_label_excludes_a_fault_with_no_surviving_face_box(egrid):
    face_in = FaultFace(0, 0, 0, 0, 0, 0, "X")
    face_out = FaultFace(5, 5, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"IN": [face_in], "OUT": [face_out]}, slices=[("i", 0)])

    assert result.label_names == ["IN"]


def test_no_mesh_gives_empty_labels(egrid):
    result = fault_surfaces(egrid, {})

    assert result.label_names == []
    assert result.label_points.shape == (0, 3)


# ---------------------------------------------------------------------------
# fault_surfaces edge cases (stub EGrid: inactive/pinched-out cells, MAPAXES)
# ---------------------------------------------------------------------------


class _StubEGrid:
    """Minimal stand-in exposing exactly what fault_surfaces needs: active_index and
    xyz_from_ijk. Each active cell is a unit cube from (i, j, k) to (i+1, j+1, k+1), using
    OPM's own corner bit convention (bit 0 = i, bit 1 = j, bit 2 = k)."""

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


def test_inactive_cells_in_a_box_are_skipped():
    egrid = _StubEGrid(active={(0, 0, 0)})
    face = FaultFace(0, 1, 0, 0, 0, 0, "X")  # i=0 active, i=1 not

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    assert result.mesh.n_cells == 1


def test_pinched_out_cells_are_skipped():
    egrid = _StubEGrid(active={(0, 0, 0), (1, 0, 0)}, pinched={(1, 0, 0)})
    face = FaultFace(0, 1, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    assert result.mesh.n_cells == 1


def test_every_cell_inactive_or_pinched_gives_no_mesh():
    egrid = _StubEGrid(active=set())
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is None


def test_apply_mapaxes_false_leaves_coordinates_untranslated():
    egrid = _StubEGrid(active={(0, 0, 0)}, dxdy=(1000.0, 2000.0))
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    result = fault_surfaces(egrid, {"F": [face]}, apply_mapaxes=False)

    assert result.mesh is not None
    np.testing.assert_allclose(result.mesh.points[:, 0], 1.0)


def test_apply_mapaxes_true_translates_coordinates():
    egrid = _StubEGrid(active={(0, 0, 0)}, dxdy=(1000.0, 2000.0))
    face = FaultFace(0, 0, 0, 0, 0, 0, "X")

    untranslated = fault_surfaces(egrid, {"F": [face]}, apply_mapaxes=False)
    translated = fault_surfaces(egrid, {"F": [face]}, apply_mapaxes=True)

    assert untranslated.mesh is not None and translated.mesh is not None
    np.testing.assert_allclose(
        translated.mesh.points[:, 0] - untranslated.mesh.points[:, 0], 1000.0
    )
    np.testing.assert_allclose(
        translated.mesh.points[:, 1] - untranslated.mesh.points[:, 1], 2000.0
    )


# ---------------------------------------------------------------------------
# Every face direction produces a valid (non-degenerate) quad
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("direction", ["X", "X-", "Y", "Y-", "Z", "Z-"])
def test_every_face_direction_gives_a_planar_quad(egrid, direction):
    face = FaultFace(1, 1, 1, 1, 1, 1, direction)

    result = fault_surfaces(egrid, {"F": [face]})

    assert result.mesh is not None
    assert result.mesh.n_cells == 1
    assert result.mesh.n_points == 4
    # Every corner of a cell face shares one coordinate (the axis the face is normal to)
    axis = {"X": 0, "Y": 1, "Z": 2}[direction[0]]
    assert len(set(np.round(result.mesh.points[:, axis], 6))) == 1
