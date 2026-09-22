""" Fault surfaces as PyVista quads """
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pyvista as pv
from numpy.typing import NDArray

from opm_vis.utils.fault import FaultFace

# OPM's corner index has bit 0 selecting i, bit 1 selecting j and bit 2 selecting k (see
# pvplot.mesh._VTK_HEX_ORDER); these are the four corners of each fault face direction, already
# listed in rotational order around the quad.
_FACE_CORNERS = {
    "X": [1, 3, 7, 5],
    "X-": [0, 2, 6, 4],
    "Y": [2, 3, 7, 6],
    "Y-": [0, 1, 5, 4],
    "Z": [4, 5, 7, 6],
    "Z-": [0, 1, 3, 2],
}


@dataclass
class FaultSurfaces:
    """
    Fault quads built by fault_surfaces(), together with a name label anchor per fault.

    Bundled the same way well_paths bundles well trajectories with their own label anchors:
    the mesh and its per-fault labels are built from the same pass over the grid, so a label
    anchor never costs a second read of the file's corner geometry.
    """

    mesh: pv.PolyData | None
    label_points: NDArray[np.float64] = field(
        default_factory=lambda: np.empty((0, 3), dtype=np.float64)
    )
    label_names: list[str] = field(default_factory=list)


def fault_surfaces(
    egrid: Any,
    faces_by_name: Mapping[str, Sequence[FaultFace]],
    *,
    slices: Sequence[tuple[str, int]] | None = None,
    apply_mapaxes: bool = False,
) -> FaultSurfaces:
    """
    Build the cell faces making up one or more faults as flat quads

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    faces_by_name : Mapping[str, Sequence[FaultFace]]
        Fault face boxes, grouped by fault name, e.g. {name: FaultReader.faces(name) for name
        in reader.names()}
    slices : Sequence[tuple[str, int]] | None, optional
        Only include a face box if its index range overlaps at least one of these (dim, index)
        i-, j- or k-slices, by default None, which includes every face box given
    apply_mapaxes : bool, optional
        Have OPM apply the grid's MAPAXES transform to the corner coordinates, by default
        False. Should match whatever the rest of the scene was built with, e.g.
        GridMesh.apply_mapaxes.

    Returns
    -------
    FaultSurfaces
        mesh: one quad per active cell in every face box that survives slice filtering, or
        None if nothing did - either because no box overlapped any of the given slices, or
        every cell the surviving boxes cover is inactive or pinched-out. label_points/
        label_names: one anchor per fault name that has at least one surviving face box,
        placed at the shallowest corner among that fault's own quads (largest z, since z
        points up - see mesh._read_corners), so a name sits near the top of its fault plane
        rather than the middle of a long wall.

    Notes
    -----
    A face box commonly spans several cells - e.g. a fault plane running the length of a
    layer - so each box expands into one quad per cell it covers, not one quad per box.
    Inactive and pinched-out cells within a box are skipped, the same as well_paths skips them
    for a completion.
    """
    quads: list[NDArray[np.float64]] = []
    label_points: list[NDArray[np.float64]] = []
    label_names: list[str] = []

    for name, faces in faces_by_name.items():
        name_quads: list[NDArray[np.float64]] = []
        for face in faces:
            if slices is not None and not _face_in_any_slice(face, slices):
                continue
            name_quads.extend(_face_quads(egrid, face, apply_mapaxes=apply_mapaxes))

        if not name_quads:
            continue

        quads.extend(name_quads)
        name_points = np.vstack(name_quads)
        label_points.append(name_points[np.argmax(name_points[:, 2])])
        label_names.append(name)

    mesh = None
    if quads:
        ncells = len(quads)
        # VTK connectivity is a flat [npoints_of_face, point ids...] per face
        connectivity = np.hstack(
            (
                np.full((ncells, 1), 4, dtype=np.int64),
                np.arange(4 * ncells, dtype=np.int64).reshape(ncells, 4),
            )
        ).ravel()
        mesh = pv.PolyData(np.vstack(quads), faces=connectivity)

    return FaultSurfaces(
        mesh=mesh,
        label_points=(
            np.array(label_points) if label_points else np.empty((0, 3), dtype=np.float64)
        ),
        label_names=label_names,
    )


def _face_in_any_slice(face: FaultFace, slices: Sequence[tuple[str, int]]) -> bool:
    """
    Check whether a face box's index range overlaps at least one of several i-, j- or k-slices

    Parameters
    ----------
    face : FaultFace
        Fault face box to check
    slices : Sequence[tuple[str, int]]
        (dim, index) pairs to check against

    Returns
    -------
    bool
        True if slice_ind falls within the box's own range along slice_dim, for at least one
        (slice_dim, slice_ind) pair - regardless of the box's own face direction, since a
        fault's surface can be visible on any slice its box spans

    Raises
    ------
    ValueError
        If a slice_dim is not "i", "j" or "k"
    """
    ranges = {"i": (face.i1, face.i2), "j": (face.j1, face.j2), "k": (face.k1, face.k2)}

    for slice_dim, slice_ind in slices:
        if slice_dim not in ranges:
            raise ValueError(f'{slice_dim} slice dimension is not valid! Choose "i", "j", or "k"')

        low, high = ranges[slice_dim]
        if low <= slice_ind <= high:
            return True

    return False


def _face_quads(
    egrid: Any, face: FaultFace, *, apply_mapaxes: bool
) -> list[NDArray[np.float64]]:
    """
    One quad per active, non-pinched-out cell in a face box

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    face : FaultFace
        Fault face box
    apply_mapaxes : bool
        Have OPM apply the grid's MAPAXES transform to the corner coordinates

    Returns
    -------
    list[NDArray[np.float64]]
        One (4, 3) array of corner points per surviving cell in the box, in rotational order
        around the quad
    """
    corner_order = _FACE_CORNERS[face.face]
    quads = []
    for i in range(face.i1, face.i2 + 1):
        for j in range(face.j1, face.j2 + 1):
            for k in range(face.k1, face.k2 + 1):
                if egrid.active_index(i, j, k) < 0:
                    continue

                corners = np.column_stack(egrid.xyz_from_ijk(i, j, k, apply_mapaxes))
                # OPM's z is depth, increasing downwards; negated here to match GridMesh's own
                # corners, which point z up to match pyvista's convention (see
                # mesh._read_corners)
                corners[:, 2] *= -1

                quad = corners[corner_order]
                if not np.isfinite(quad).all():
                    continue  # pinched-out cell

                quads.append(quad)

    return quads
