""" Read polygons (outlines or 3D polylines) from NumPy, text and GeoJSON files """
from __future__ import annotations

import json
import warnings
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

NUMPY_SUFFIXES = (".npy", ".npz")
TEXT_SUFFIXES = (".txt", ".csv", ".dat", ".xyz")
GEOJSON_SUFFIXES = (".geojson", ".json")
POLYGON_SUFFIXES = NUMPY_SUFFIXES + TEXT_SUFFIXES + GEOJSON_SUFFIXES

# GeoJSON properties tried, in order, for a feature's name
_NAME_PROPERTIES = ("name", "NAME", "Name")


@dataclass
class Polygon:
    """
    One polygon or polyline, in the same coordinates the grid is plotted in.

    name is the label to draw it with, or "" for none. Several polygons can share a name,
    e.g. a GeoJSON polygon's outer ring and its holes; such a name is labelled once. points has
    shape (n, 2) for an x,y outline, or (n, 3) for x,y,z points with z as depth, positive down
    like the grid's own. A closed polygon repeats its first point at the end. source is the
    file it was read from, for messages about it.
    """

    name: str
    points: NDArray[np.float64]
    source: str = ""

    def describe(self) -> str:
        """
        Name this polygon in a message

        Returns
        -------
        str
            e.g. "Licence A (licence.geojson)", or just the file name if it has no label
        """
        source = Path(self.source).name
        if not self.name:
            return source or "unlabelled polygon"
        return f"{self.name} ({source})" if source else self.name

    @property
    def has_depth(self) -> bool:
        """
        Whether the points carry their own depth

        Returns
        -------
        bool
            True for x,y,z points, False for an x,y outline
        """
        return self.points.shape[1] == 3

    def label_point(self) -> NDArray[np.float64]:
        """
        Where to place this polygon's name

        Returns
        -------
        NDArray[np.float64]
            The mean of its vertices for a closed polygon (counting the repeated closing point
            once), or its first point for an open polyline
        """
        if _is_closed(self.points):
            return self.points[:-1].mean(axis=0)
        return self.points[0]


def read_polygons(
    paths: str | Path | Iterable[str | Path], labels: Sequence[str | None] | None = None
) -> list[Polygon]:
    """
    Read every polygon in one or more files

    Parameters
    ----------
    paths : str | Path | Iterable[str | Path]
        File(s) to read. The format follows the extension:

        - .npy: one (n, 2) or (n, 3) array, or a stack of several, shape (m, n, 2|3)
        - .npz: one polygon per array, named by its key
        - .txt, .csv, .dat, .xyz: columns x y [z], separated by whitespace or commas, with a
          blank line between polygons. Lines starting with # are comments, and a header row
          (e.g. "x,y,z") is skipped.
        - .geojson, .json: Polygon, MultiPolygon, LineString and MultiLineString geometries,
          on their own, as Features or in a FeatureCollection. A feature's "name" property
          names it.
    labels : Sequence[str | None] | None, optional
        One label per file, in the same order, replacing the names of every polygon in that
        file; "" leaves that file's polygons unlabelled, and None keeps their own names. By
        default None, which keeps every polygon's own name.

    Returns
    -------
    list[Polygon]
        Every polygon found, in file order. Polygons from NumPy and text files are closed
        (their first point repeated at the end) if they are not already; GeoJSON polygons are
        closed by definition, and its line strings are kept open.

    Raises
    ------
    FileNotFoundError
        If a file does not exist
    ValueError
        If a file's extension is not supported, or its contents are not valid polygons, or
        labels does not have one entry per file
    """
    paths = [Path(paths)] if isinstance(paths, (str, Path)) else [Path(p) for p in paths]
    if labels is None:
        labels = [None] * len(paths)
    elif len(labels) != len(paths):
        raise ValueError(
            f"Got {len(labels)} polygon label(s) for {len(paths)} polygon file(s); give one "
            "label per file."
        )

    polygons: list[Polygon] = []
    for path, label in zip(paths, labels):
        start = len(polygons)
        if not path.is_file():
            raise FileNotFoundError(f"Polygon file {path} not found!")

        suffix = path.suffix.lower()
        if suffix == ".npy":
            polygons.extend(_read_npy(path))
        elif suffix == ".npz":
            polygons.extend(_read_npz(path))
        elif suffix in TEXT_SUFFIXES:
            polygons.extend(_read_text(path))
        elif suffix in GEOJSON_SUFFIXES:
            polygons.extend(_read_geojson(path))
        else:
            raise ValueError(
                f"Unsupported polygon file {path}: expected one of {', '.join(POLYGON_SUFFIXES)}."
            )

        for polygon in polygons[start:]:
            polygon.source = str(path)
            if label is not None:
                polygon.name = label

    return polygons


def warn_outside(
    polygons: Sequence[Polygon],
    points: Sequence[NDArray[np.float64]],
    low: NDArray[np.float64],
    high: NDArray[np.float64],
) -> None:
    """
    Warn about polygons lying entirely outside what is plotted, and so never visible

    Parameters
    ----------
    polygons : Sequence[Polygon]
        Polygons being drawn
    points : Sequence[NDArray[np.float64]]
        Each polygon's points as drawn, shape (n, d), in the same coordinates as low/high
    low, high : NDArray[np.float64]
        Lower and upper corner of what is plotted, shape (d,)

    Notes
    -----
    Compares bounding boxes, so a polygon is only reported when its box misses the plotted
    region altogether - typically a file in other units (e.g. km rather than m) or another
    coordinate system.
    """
    outside: list[str] = []
    for polygon, pts in zip(polygons, points):
        if (pts.max(axis=0) < low).any() or (pts.min(axis=0) > high).any():
            description = polygon.describe()
            if description not in outside:
                outside.append(description)

    if outside:
        warnings.warn(
            f"{len(outside)} polygon(s) lie entirely outside the plotted grid and are not "
            f"visible: {', '.join(outside)}. Check that their coordinates are in the grid's own "
            "units and coordinate system (e.g. metres, with MAPAXES applied if the grid has it)."
        )


def _read_npy(path: Path) -> list[Polygon]:
    """
    Polygons from a .npy file: one (n, 2|3) array, or a stack of them, shape (m, n, 2|3)
    """
    array = _load_numpy(path)
    if array.ndim == 3:
        return [
            Polygon(name, _closed(_points(arr, f"{path} [{i}]")))
            for i, (name, arr) in enumerate(zip(_numbered(path.stem, len(array)), array))
        ]
    return [Polygon(path.stem, _closed(_points(array, str(path))))]


def _read_npz(path: Path) -> list[Polygon]:
    """
    Polygons from a .npz file, one per array, named by its key
    """
    with _load_numpy(path) as archive:
        if not archive.files:
            raise ValueError(f"No arrays in {path}!")
        return [
            Polygon(key, _closed(_points(archive[key], f"{path} [{key}]")))
            for key in archive.files
        ]


def _load_numpy(path: Path) -> Any:
    """
    np.load a .npy or .npz file, without pickled objects, as a clean error if it is not one
    """
    try:
        return np.load(path, allow_pickle=False)
    except (ValueError, OSError, EOFError, zipfile.BadZipFile) as exc:
        raise ValueError(f"{path} is not a valid NumPy {path.suffix} file: {exc}") from exc


def _read_text(path: Path) -> list[Polygon]:
    """
    Polygons from a text file: x y [z] columns, with a blank line between polygons
    """
    blocks: list[list[list[float]]] = []
    current: list[list[float]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue

        fields = line.replace(",", " ").split()
        try:
            current.append([float(value) for value in fields])
        except ValueError as exc:
            # A header row (e.g. "x,y,z") is only allowed before the first point
            if not blocks and not current:
                continue
            raise ValueError(
                f"{path}, line {line_number}: expected numbers, got {raw.strip()!r}."
            ) from exc
    if current:
        blocks.append(current)

    if not blocks:
        raise ValueError(f"No points in {path}!")

    polygons = []
    for name, block in zip(_numbered(path.stem, len(blocks)), blocks):
        widths = {len(row) for row in block}
        if len(widths) != 1:
            raise ValueError(
                f"{path}: polygon {name} mixes rows of {sorted(widths)} columns; every row of a "
                "polygon needs the same x y or x y z columns."
            )
        polygons.append(Polygon(name, _closed(_points(np.array(block), f"{path} ({name})"))))

    return polygons


def _read_geojson(path: Path) -> list[Polygon]:
    """
    Polygons from a GeoJSON file
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    named = list(_geojson_lines(data))
    if not named:
        raise ValueError(
            f"No Polygon, MultiPolygon, LineString or MultiLineString geometry in {path}!"
        )

    # Unnamed features are numbered after the file, the same way text files' polygons are
    unnamed = [i for i, (name, _) in enumerate(named) if name is None]
    fallback = dict(zip(unnamed, _numbered(path.stem, len(unnamed))))

    return [
        Polygon(name if name is not None else fallback[i], _points(np.array(coords), str(path)))
        for i, (name, coords) in enumerate(named)
    ]


def _geojson_lines(data: Any) -> Iterator[tuple[str | None, Any]]:
    """
    Every ring or line string in a GeoJSON object, with its feature's name (None if unnamed)
    """
    kind = data.get("type") if isinstance(data, dict) else None
    if kind == "FeatureCollection":
        for feature in data.get("features", []):
            yield from _geojson_lines(feature)
    elif kind == "Feature":
        properties = data.get("properties") or {}
        name = next(
            (str(properties[key]) for key in _NAME_PROPERTIES if properties.get(key)), None
        )
        for coords in _geometry_lines(data.get("geometry")):
            yield name, coords
    else:
        for coords in _geometry_lines(data):
            yield None, coords


def _geometry_lines(geometry: Any) -> Iterator[Any]:
    """
    Every ring or line string in one GeoJSON geometry; Points and the like are skipped
    """
    if not isinstance(geometry, dict):
        return
    kind = geometry.get("type")
    coords: Any = geometry.get("coordinates") or []
    if kind == "LineString":
        yield coords
    elif kind in ("Polygon", "MultiLineString"):
        yield from coords
    elif kind == "MultiPolygon":
        for polygon in coords:
            yield from polygon
    elif kind == "GeometryCollection":
        for part in geometry.get("geometries", []):
            yield from _geometry_lines(part)


def _points(array: Any, source: str) -> NDArray[np.float64]:
    """
    Validate one polygon's points: a finite (n, 2) or (n, 3) array of at least 2 points
    """
    try:
        points = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: polygon points must be numbers.") from exc

    if points.ndim != 2 or points.shape[1] not in (2, 3):
        raise ValueError(
            f"{source}: polygon points must have shape (n, 2) for x,y or (n, 3) for x,y,z, "
            f"got {points.shape}."
        )
    if len(points) < 2:
        raise ValueError(f"{source}: a polygon needs at least 2 points, got {len(points)}.")
    if not np.isfinite(points).all():
        raise ValueError(f"{source}: polygon points must be finite (no NaN or inf).")

    return points


def _closed(points: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    Repeat the first point at the end, unless already there or there are only 2 points
    """
    if len(points) < 3 or _is_closed(points):
        return points
    return np.vstack([points, points[:1]])


def _is_closed(points: NDArray[np.float64]) -> bool:
    """
    Whether a polygon's last point repeats its first, making it a closed ring
    """
    return len(points) > 3 and bool(np.array_equal(points[0], points[-1]))


def _numbered(stem: str, count: int) -> Sequence[str]:
    """
    Names for count polygons from one file: the file stem alone if there is just one
    """
    if count == 1:
        return [stem]
    return [f"{stem}_{i}" for i in range(1, count + 1)]
