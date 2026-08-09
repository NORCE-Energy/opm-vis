""" Unit tests for opm_vis.pvplot.wells, backed by the SPE1CASE1 test dataset """
import numpy as np
import pytest

pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.pvplot.wells import well_paths  # noqa: E402
from opm_vis.utils.restart import Wells  # noqa: E402

# The case1 fixture comes from conftest.py. SPE1CASE1 has exactly two wells, PROD at
# (i, j) = (9, 9) completed in k=2 and INJ at (0, 0) completed in k=0, both open for the whole
# run. Both are completed in a single cell, so this dataset covers the case that a naive
# cell-centre trajectory would collapse to a single undrawable point. Shut wells and multi-cell
# completions are not in the data, so they use synthetic stand-ins.


@pytest.fixture(scope="module")
def egrid(data_dir):
    from opm.io.ecl import EGrid

    return EGrid(str(data_dir / "SPE1CASE1.EGRID"))


@pytest.fixture(scope="module")
def wells(case1):
    return Wells([case1])


class _StubWells:
    """Stands in for Wells, which can only report what the restart files happen to contain."""

    def __init__(self, info):
        self._info = info

    def __getitem__(self, rstep):
        del rstep
        return self._info


# ---------------------------------------------------------------------------
# well_paths against the real dataset
# ---------------------------------------------------------------------------


def test_both_spe1_wells_are_found_and_open(egrid, wells):
    paths = well_paths(egrid, wells, 60)

    assert sorted(paths.label_names) == ["INJ", "PROD"]
    assert paths.open_wells is not None
    assert paths.shut_wells is None
    assert paths.is_empty() is False


def test_single_cell_completion_still_gives_a_drawable_line(egrid, wells):
    paths = well_paths(egrid, wells, 60)

    # Two wells, each completed in one cell, traced top face to bottom face
    assert paths.open_wells.n_points == 4
    assert paths.open_wells.n_cells == 2
    assert paths.open_wells.length > 0


def test_trajectory_spans_the_thickness_of_its_completed_cell(egrid, wells):
    paths = well_paths(egrid, wells, 60)

    # SPE1CASE1's layers are 20, 30 and 50 ft thick from 8325 ft, so INJ in k=0 spans
    # 8325-8345 and PROD in k=2 spans 8375-8425
    depths = sorted(paths.open_wells.points[:, 2])
    np.testing.assert_allclose(depths, [8325.0, 8345.0, 8375.0, 8425.0])


def test_labels_are_anchored_at_the_top_of_their_own_trajectory(egrid, wells):
    paths = well_paths(egrid, wells, 60)

    anchors = dict(zip(paths.label_names, paths.label_points[:, 2]))

    # Not the shallowest point in the scene: each label sits on top of its own well
    assert anchors == {"INJ": 8325.0, "PROD": 8375.0}


def test_label_points_line_up_with_label_names(egrid, wells):
    paths = well_paths(egrid, wells, 60)

    assert paths.label_points.shape == (len(paths.label_names), 3)


# ---------------------------------------------------------------------------
# well_paths(slices=...) - restricting to one or several slices
# ---------------------------------------------------------------------------


def test_slices_restricts_to_wells_completed_there(egrid, wells):
    # INJ is completed at k=0 only, PROD at k=2 only
    paths = well_paths(egrid, wells, 60, slices=[("k", 0)])

    assert paths.label_names == ["INJ"]


def test_slices_is_a_union_not_an_intersection(egrid, wells):
    paths = well_paths(egrid, wells, 60, slices=[("k", 0), ("k", 2)])

    assert sorted(paths.label_names) == ["INJ", "PROD"]


def test_slices_on_an_i_or_j_slice_matches_the_well_head(egrid, wells):
    # PROD's head is at (i, j) = (9, 9)
    paths = well_paths(egrid, wells, 60, slices=[("i", 9)])

    assert paths.label_names == ["PROD"]

    paths = well_paths(egrid, wells, 60, slices=[("j", 9)])

    assert paths.label_names == ["PROD"]


def test_slices_excluding_every_well_gives_an_empty_result(egrid, wells):
    paths = well_paths(egrid, wells, 60, slices=[("k", 1)])

    assert paths.is_empty() is True


def test_no_slices_includes_every_well(egrid, wells):
    paths = well_paths(egrid, wells, 60, slices=None)

    assert sorted(paths.label_names) == ["INJ", "PROD"]


def test_slices_rejects_an_invalid_dimension(egrid, wells):
    with pytest.raises(ValueError, match="not valid"):
        well_paths(egrid, wells, 60, slices=[("x", 0)])


# ---------------------------------------------------------------------------
# well_paths edge cases (synthetic well info)
# ---------------------------------------------------------------------------


def test_shut_wells_are_kept_separate_from_open_ones(egrid):
    stub = _StubWells({"OPENW": [0, 0, 0, True], "SHUTW": [1, 1, 0, False]})

    paths = well_paths(egrid, stub, 0)

    assert paths.open_wells.n_cells == 1
    assert paths.shut_wells.n_cells == 1
    assert sorted(paths.label_names) == ["OPENW", "SHUTW"]


def test_multi_cell_completion_is_one_polyline(egrid):
    stub = _StubWells({"DEEP": [0, 0, 0, 1, 2, True]})

    paths = well_paths(egrid, stub, 0)

    assert paths.open_wells.n_cells == 1  # one well, one polyline
    assert paths.open_wells.n_points == 6  # 3 cells, top and bottom face of each
    # Anchored at the shallowest point of the whole path, not of the first cell alone
    assert paths.label_points[0][2] == paths.open_wells.points[:, 2].min()


def test_well_without_any_completion_is_skipped(egrid):
    stub = _StubWells({"NOCOMP": [0, 0, True]})

    paths = well_paths(egrid, stub, 0)

    assert paths.is_empty() is True
    assert paths.label_names == []


def test_no_wells_at_all_gives_an_empty_result(egrid):
    paths = well_paths(egrid, _StubWells({}), 0)

    assert paths.is_empty() is True
    assert paths.label_points.shape == (0, 3)
