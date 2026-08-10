""" Unit tests for opm_vis.utils.mapaxes and its use in opm_vis.utils.grid """
import numpy as np
import pytest
from opm.io.ecl import EGrid

from opm_vis.utils.grid import GridSlice3D
from opm_vis.utils.mapaxes import has_mapaxes

# The mapaxes_case/case1 fixtures come from conftest.py. MAPAXES.EGRID's MAPAXES keyword is a
# pure translation (no rotation or shear) from a local (x, y) origin at (0, 0) to a UTM-like
# origin - checked once in _origin_offset and then relied on by the tests below.


@pytest.fixture(scope="module")
def mapaxes_egrid(mapaxes_case):
    return EGrid(mapaxes_case + ".EGRID")


def _origin_offset(egrid):
    """The (dx, dy) MAPAXES.EGRID's MAPAXES keyword translates every coordinate by."""
    x1, y1, x2, y2, x3, y3 = egrid.export_mapaxes()
    assert (x3 - x2, y3 - y2) == pytest.approx((821.375, 0.0))
    assert (x1 - x2, y1 - y2) == pytest.approx((0.0, 1473.0))
    return x2, y2


def test_has_mapaxes_true_for_mapaxes_file(mapaxes_case):
    assert has_mapaxes(mapaxes_case + ".EGRID") is True


def test_has_mapaxes_false_for_plain_file(case1):
    assert has_mapaxes(case1 + ".EGRID") is False


def test_xyz_from_active_index_translates_by_mapaxes_origin(mapaxes_egrid):
    dx, dy = _origin_offset(mapaxes_egrid)

    raw_x, raw_y, raw_z = mapaxes_egrid.xyz_from_active_index(0, False)
    mapped_x, mapped_y, mapped_z = mapaxes_egrid.xyz_from_active_index(0, True)

    np.testing.assert_allclose(mapped_x, np.array(raw_x) + dx)
    np.testing.assert_allclose(mapped_y, np.array(raw_y) + dy)
    np.testing.assert_allclose(mapped_z, raw_z)  # MAPAXES never touches z/depth


def test_xyz_from_ijk_translates_by_mapaxes_origin(mapaxes_egrid):
    dx, dy = _origin_offset(mapaxes_egrid)

    raw_x, raw_y, raw_z = mapaxes_egrid.xyz_from_ijk(0, 0, 0, False)
    mapped_x, mapped_y, mapped_z = mapaxes_egrid.xyz_from_ijk(0, 0, 0, True)

    np.testing.assert_allclose(mapped_x, np.array(raw_x) + dx)
    np.testing.assert_allclose(mapped_y, np.array(raw_y) + dy)
    np.testing.assert_allclose(mapped_z, raw_z)


# ---------------------------------------------------------------------------
# GridSlice3D picking up MAPAXES automatically
# ---------------------------------------------------------------------------


def test_grid_slice_detects_mapaxes(mapaxes_case):
    slc = GridSlice3D(mapaxes_case, "k", 0)

    assert slc.apply_mapaxes is True


def test_grid_slice_corners_are_translated(mapaxes_case, mapaxes_egrid):
    dx, dy = _origin_offset(mapaxes_egrid)

    slc = GridSlice3D(mapaxes_case, "k", 0)
    corners = slc.cell_corners()

    # Cell (i=0, j=0) sits at the grid's local (x, y) origin, so its corners' minimum should
    # land exactly on the MAPAXES origin once translated.
    assert corners[..., 0].min() == pytest.approx(dx)
    assert corners[..., 1].min() == pytest.approx(dy)


def test_grid_slice_without_mapaxes_is_unaffected(case1):
    slc = GridSlice3D(case1, "k", 1)

    assert slc.apply_mapaxes is False
