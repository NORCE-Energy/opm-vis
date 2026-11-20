""" Polygons as PyVista polylines """
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pyvista as pv
from numpy.typing import NDArray

from opm_vis.pvplot.wells import _polylines
from opm_vis.utils.polygons import Polygon


@dataclass
class PolygonLines:
    """
    Polygons built by polygon_lines(), together with a name label anchor per polygon name
    """

    mesh: pv.PolyData | None
    label_points: NDArray[np.float64] = field(
        default_factory=lambda: np.empty((0, 3), dtype=np.float64)
    )
    label_names: list[str] = field(default_factory=list)
    skipped_outlines: int = 0
    drawn: list[Polygon] = field(default_factory=list)
    tracks: list[NDArray[np.float64]] = field(default_factory=list)


def polygon_lines(
    polygons: Sequence[Polygon], top: float, *, outlines: bool = True
) -> PolygonLines:
    """
    Build polygons as polylines in pvplot's z-up coordinates

    Parameters
    ----------
    polygons : Sequence[Polygon]
        Polygons to draw, e.g. from opm_vis.utils.polygons.read_polygons
    top : float
        z (pvplot's z-up, i.e. minus depth) to place x,y-only outlines at, e.g. the top of the
        grid
    outlines : bool, optional
        Include x,y-only outlines, by default True. Leave them out where a flat outline at the
        top of the grid would only be seen edge-on, e.g. a 2D view of an i- or j-slice.

    Returns
    -------
    PolygonLines
        mesh: one polyline per polygon drawn, or None if there is none. label_points/
        label_names: one anchor per polygon name, at its first polygon's label point; an
        unlabelled polygon (name "") gets none. skipped_outlines: how many x,y-only outlines
        were left out because outlines is False. drawn/tracks: each polygon drawn, with its
        points in pvplot's coordinates.
    """
    drawn: list[Polygon] = []
    tracks: list[NDArray[np.float64]] = []
    label_points: list[NDArray[np.float64]] = []
    label_names: list[str] = []
    skipped = 0

    for polygon in polygons:
        if polygon.has_depth:
            # Depth is positive down; pvplot's z points up (see mesh.GridMesh._read_corners)
            points = polygon.points * np.array([1.0, 1.0, -1.0])
            label = polygon.label_point() * np.array([1.0, 1.0, -1.0])
        elif outlines:
            points = np.column_stack([polygon.points, np.full(len(polygon.points), top)])
            label = np.append(polygon.label_point(), top)
        else:
            skipped += 1
            continue

        drawn.append(polygon)
        tracks.append(points)
        if polygon.name and polygon.name not in label_names:
            label_names.append(polygon.name)
            label_points.append(label)

    return PolygonLines(
        mesh=_polylines(tracks),
        label_points=(
            np.array(label_points) if label_points else np.empty((0, 3), dtype=np.float64)
        ),
        label_names=label_names,
        skipped_outlines=skipped,
        drawn=drawn,
        tracks=tracks,
    )
