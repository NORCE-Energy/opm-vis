""" Fault traces as line segments for the Matplotlib backend """
from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from opm_vis.utils.fault import FaultFace

# Raw OPM 8-corner convention: bit 0 selects i, bit 1 selects j, bit 2 selects k - the same
# convention opm_vis.utils.grid._INDICES and opm_vis.pvplot.faults._FACE_CORNERS use.
# _SLICE_FOOTPRINT_CORNERS is _INDICES itself: the 4 corners GridSlice2D/GridSlice3D already
# pick out as a cell's own footprint on a slice, so a fault edge built from the same 4 points
# lines up exactly with the cell boundaries drawn around it.
_SLICE_FOOTPRINT_CORNERS = {"i": [0, 2, 6, 4], "j": [0, 1, 5, 4], "k": [0, 2, 3, 1]}

# Which pair of a slice's own 4 footprint corners (indices into _SLICE_FOOTPRINT_CORNERS's own
# 0..3 order) forms the edge for each fault direction that is actually visible as a line on
# that slice_dim. A fault whose own direction matches the slice's axis (e.g. an X/X- fault on
# an i-slice) is coincident with the whole slice rather than a line on it, and has no entry
# here - see fault_edges' notes.
_EDGE_CORNERS = {
    "k": {"X": (2, 3), "X-": (0, 1), "Y": (1, 2), "Y-": (3, 0)},
    "j": {"X": (1, 2), "X-": (3, 0), "Z": (2, 3), "Z-": (0, 1)},
    "i": {"Y": (1, 2), "Y-": (3, 0), "Z": (2, 3), "Z-": (0, 1)},
}


@dataclass
class FaultEdges:
    """
    Fault trace segments built by fault_edges(), together with a name label anchor per fault.
    """

    segments: NDArray[np.float64] = field(
        default_factory=lambda: np.empty((0, 2, 3), dtype=np.float64)
    )
    label_points: NDArray[np.float64] = field(
        default_factory=lambda: np.empty((0, 3), dtype=np.float64)
    )
    label_names: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """
        Check whether there is anything to draw

        Returns
        -------
        bool
            True if no fault had a segment on this slice
        """
        return self.segments.shape[0] == 0


def fault_edges(
    egrid: Any,
    faces_by_name: Mapping[str, Sequence[FaultFace]],
    slice_dim: str,
    slice_ind: int,
    *,
    apply_mapaxes: bool = False,
) -> FaultEdges:
    """
    Build one i-, j- or k-slice's fault traces as line segments, with a name label anchor

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    faces_by_name : Mapping[str, Sequence[FaultFace]]
        Fault face boxes, grouped by fault name, e.g. {name: FaultReader.faces(name) for name
        in reader.names()}
    slice_dim : str
        'i', 'j', or 'k' slice of the 3D grid
    slice_ind : int
        Index of slice
    apply_mapaxes : bool, optional
        Have OPM apply the grid's MAPAXES transform to the corner coordinates, by default
        False. Should match whatever the slice's own geometry was built with (e.g.
        GridSlice3D.apply_mapaxes).

    Returns
    -------
    FaultEdges
        segments: one 2-point line per active, non-pinched-out cell whose face lies on this
        slice - shape (n, 2, 3), real-world (x, y, z) endpoints in OPM's own depth-positive-
        down z (no sign flip, unlike opm_vis.pvplot.faults). label_points/label_names: one
        anchor per fault name that contributed at least one segment, at its own shallowest
        point (smallest z).

    Notes
    -----
    A fault face is only visible as a line on a slice when its own direction differs from the
    slice's axis (an X/X- fault on a j- or k-slice, a Y/Y- fault on an i- or k-slice, a Z/Z-
    fault on an i- or j-slice); a fault whose direction *matches* the slice's own axis (e.g. an
    X/X- fault on an i-slice) lies flush in the slice's own plane rather than crossing it as a
    line, and contributes nothing here - see _EDGE_CORNERS.

    Segment endpoints are picked from the same 4 footprint corners (_SLICE_FOOTPRINT_CORNERS,
    i.e. opm_vis.utils.grid._INDICES) that GridSlice2D/GridSlice3D already draw each cell's own
    outline from, so a fault trace lines up exactly with the plotted cell boundaries rather
    than needing its own separate projection.
    """
    edge_corners = _EDGE_CORNERS[slice_dim]

    segments: list[NDArray[np.float64]] = []
    label_points: list[NDArray[np.float64]] = []
    label_names: list[str] = []

    for name, faces in faces_by_name.items():
        name_segments: list[NDArray[np.float64]] = []
        for face in faces:
            corner_pair = edge_corners.get(face.face)
            if corner_pair is None:
                continue  # coincident with this slice's own plane, not a line on it

            name_segments.extend(
                _face_edges(egrid, face, slice_dim, slice_ind, corner_pair, apply_mapaxes)
            )

        if not name_segments:
            continue

        segments.extend(name_segments)
        points = np.vstack(name_segments)
        label_points.append(points[np.argmin(points[:, 2])])  # shallowest = smallest depth
        label_names.append(name)

    return FaultEdges(
        segments=np.array(segments) if segments else np.empty((0, 2, 3), dtype=np.float64),
        label_points=(
            np.array(label_points) if label_points else np.empty((0, 3), dtype=np.float64)
        ),
        label_names=label_names,
    )


def _face_edges(
    egrid: Any,
    face: FaultFace,
    slice_dim: str,
    slice_ind: int,
    corner_pair: tuple[int, int],
    apply_mapaxes: bool,
) -> list[NDArray[np.float64]]:
    """
    One 2-point line segment per active, non-pinched-out cell of a face box that lies on a slice

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    face : FaultFace
        Fault face box
    slice_dim : str
        'i', 'j', or 'k' slice of the 3D grid
    slice_ind : int
        Index of slice
    corner_pair : tuple[int, int]
        Which pair of the slice's own 4 footprint corners forms this face's edge; see
        _EDGE_CORNERS
    apply_mapaxes : bool
        Have OPM apply the grid's MAPAXES transform to the corner coordinates

    Returns
    -------
    list[NDArray[np.float64]]
        One (2, 3) array of segment endpoints per surviving cell in the box that lies on the
        slice - empty if slice_ind is outside the box's own range along slice_dim
    """
    ranges = {"i": (face.i1, face.i2), "j": (face.j1, face.j2), "k": (face.k1, face.k2)}
    low, high = ranges[slice_dim]
    if not low <= slice_ind <= high:
        return []

    i_range = [slice_ind] if slice_dim == "i" else range(face.i1, face.i2 + 1)
    j_range = [slice_ind] if slice_dim == "j" else range(face.j1, face.j2 + 1)
    k_range = [slice_ind] if slice_dim == "k" else range(face.k1, face.k2 + 1)

    footprint = _SLICE_FOOTPRINT_CORNERS[slice_dim]
    corner_a, corner_b = corner_pair

    segments = []
    for i, j, k in itertools.product(i_range, j_range, k_range):
        if egrid.active_index(i, j, k) < 0:
            continue

        corners = np.column_stack(egrid.xyz_from_ijk(i, j, k, apply_mapaxes))
        footprint_corners = corners[footprint]
        if not np.isfinite(footprint_corners).all():
            continue  # pinched-out cell

        segments.append(footprint_corners[[corner_a, corner_b]])

    return segments
