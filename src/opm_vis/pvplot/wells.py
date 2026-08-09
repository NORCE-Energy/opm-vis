""" Well trajectories as PyVista polylines """
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pyvista as pv
from numpy.typing import NDArray

from opm_vis.utils.restart import Wells


@dataclass
class WellPaths:
    """
    Well trajectories at one report step, split by whether the well is open.

    Open and shut wells are separate datasets rather than one dataset with a status array,
    so each can simply be given a colour instead of competing with the property field for the
    scalar mapping.
    """

    open_wells: pv.PolyData | None = None
    shut_wells: pv.PolyData | None = None
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
            True if no well had an active completion at this report step
        """
        return self.open_wells is None and self.shut_wells is None


def well_paths(
    egrid: Any,
    wells: Wells,
    rstep: int,
    *,
    slices: Sequence[tuple[str, int]] | None = None,
) -> WellPaths:
    """
    Build well trajectories for one report step

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    wells : Wells
        Well information for every report step
    rstep : int
        Report step
    slices : Sequence[tuple[str, int]] | None, optional
        Only include wells with a completion on at least one of these (dim, index) i-, j- or
        k-slices, by default None, which includes every well in the grid

    Returns
    -------
    WellPaths
        Open and shut trajectories, with a label anchor per well

    Notes
    -----
    Trajectories are full 3D paths through the grid, so unlike opm_vis.plot there is no need
    to truncate a well to the intersecting portion of a slice - slices only decides which
    wells are included, each still drawn in full.

    Wells are still assumed vertical, which is what opm_vis.utils.restart records: the i and j
    indices are the well head's and only the completed k indices vary.
    """
    open_tracks: list[NDArray[np.float64]] = []
    shut_tracks: list[NDArray[np.float64]] = []
    label_points: list[NDArray[np.float64]] = []
    label_names: list[str] = []

    for name, info in wells[rstep].items():
        # Well info is [i, j, k0, ..., kend, status], so anything shorter has no completion
        if len(info) < 4:
            continue

        if slices is not None and not _has_completion_in_any_slice(info, slices):
            continue

        track = _completion_track(egrid, info[0], info[1], info[2:-1])
        if track is None:
            continue

        (open_tracks if info[-1] else shut_tracks).append(track)

        # Label at the shallowest point of the trajectory
        label_points.append(track[0])
        label_names.append(name)

    return WellPaths(
        open_wells=_polylines(open_tracks),
        shut_wells=_polylines(shut_tracks),
        label_points=(
            np.array(label_points)
            if label_points
            else np.empty((0, 3), dtype=np.float64)
        ),
        label_names=label_names,
    )


def _has_completion_in_any_slice(info: list[Any], slices: Sequence[tuple[str, int]]) -> bool:
    """
    Check whether a well has a completion on at least one of several i-, j- or k-slices

    Parameters
    ----------
    info : list[Any]
        Well info as [i, j, k0, ..., kend, status]
    slices : Sequence[tuple[str, int]]
        (dim, index) pairs to check against

    Returns
    -------
    bool
        True if the well's head lies on any i- or j-slice given, or one of its completed
        layers matches any k-slice given

    Notes
    -----
    Wells are assumed vertical (see well_paths), so the head's i and j are the same for every
    completion - an i- or j-slice either includes the whole well or none of it, unlike a
    k-slice which depends on which layers are actually completed.
    """
    i, j, *k_and_status = info
    k_values = k_and_status[:-1]

    for slice_dim, slice_ind in slices:
        if slice_dim == "k":
            if slice_ind in k_values:
                return True
        elif slice_dim == "i":
            if i == slice_ind:
                return True
        elif slice_dim == "j":
            if j == slice_ind:
                return True
        else:
            raise ValueError(
                f'{slice_dim} slice dimension is not valid! Choose "i", "j", or "k"'
            )

    return False


def _completion_track(
    egrid: Any, i: int, j: int, kvalues: list[int]
) -> NDArray[np.float64] | None:
    """
    Trace a well through the cells it is completed in

    Parameters
    ----------
    egrid : Any
        opm.io.ecl.EGrid of the case
    i : int
        Well head i index
    j : int
        Well head j index
    kvalues : list[int]
        Completed k indices

    Returns
    -------
    NDArray[np.float64] | None
        Points along the trajectory with shape (npoints, 3), or None if the well has no active
        completion

    Notes
    -----
    Each completed cell contributes the centre of its top face and of its bottom face, rather
    than one cell centre. Neighbouring cells' faces almost coincide so the path still looks
    continuous, and a well completed in a single cell - the common case in SPE1 - still gets a
    drawable two-point line instead of a degenerate one-point one.
    """
    points = []
    for k in kvalues:
        # Inactive cells have no geometry to trace through
        if egrid.active_index(i, j, k) < 0:
            continue

        corners = np.column_stack(egrid.xyz_from_ijk(i, j, k))

        # OPM's corner index has bit 2 selecting k, so 0-3 is the shallow face and 4-7 the deep
        points.append(corners[:4].mean(axis=0))
        points.append(corners[4:].mean(axis=0))

    return np.array(points) if points else None


def _polylines(tracks: list[NDArray[np.float64]]) -> pv.PolyData | None:
    """
    Gather several trajectories into one dataset of polylines

    Parameters
    ----------
    tracks : list[NDArray[np.float64]]
        One (npoints, 3) array per well

    Returns
    -------
    pv.PolyData | None
        Dataset with one polyline per well, or None if there are no tracks
    """
    if not tracks:
        return None

    # VTK connectivity is a flat [npoints_of_line, point ids...] per line
    lines: list[int] = []
    offset = 0
    for track in tracks:
        npoints = len(track)
        lines.append(npoints)
        lines.extend(range(offset, offset + npoints))
        offset += npoints

    return pv.PolyData(np.vstack(tracks), lines=np.array(lines, dtype=np.int64))
