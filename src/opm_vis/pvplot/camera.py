""" Camera position as a value that can be printed and parsed back """
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

_Point = tuple[float, float, float]


@dataclass(frozen=True)
class Camera:
    """
    Where the camera is, what it looks at, which way is up, and - with parallel projection -
    how far it is zoomed.

    Coordinates are the scene's own, which pvplot stretches vertically by its z_scale and
    points z up in (see GridMesh), so a camera only reproduces the same view with the same
    z_scale. The window's shape also matters: a camera found in one window size frames a bit
    more or less at the sides in another.
    """

    position: _Point
    focal_point: _Point
    view_up: _Point
    parallel_scale: float | None = None

    def to_text(self) -> str:
        """
        The camera as one shell-safe token, the form --camera takes

        Returns
        -------
        str
            "X,Y,Z/FX,FY,FZ/UX,UY,UZ", with "/SCALE" appended for parallel projection
        """
        parts = [
            ",".join(_number(value) for value in point)
            for point in (self.position, self.focal_point, self.view_up)
        ]
        if self.parallel_scale is not None:
            parts.append(_number(self.parallel_scale))
        return "/".join(parts)

    @classmethod
    def from_text(cls, text: str) -> Camera:
        """
        Parse a camera from the form to_text writes

        Parameters
        ----------
        text : str
            "X,Y,Z/FX,FY,FZ/UX,UY,UZ" or "X,Y,Z/FX,FY,FZ/UX,UY,UZ/SCALE"

        Returns
        -------
        Camera
            The camera, with parallel_scale set only if SCALE was given

        Raises
        ------
        ValueError
            If text is not of that form, or the view-up vector is zero
        """
        parts = text.strip().split("/")
        if len(parts) not in (3, 4):
            raise ValueError(
                f"A camera is X,Y,Z/FX,FY,FZ/UX,UY,UZ with an optional /SCALE, got '{text}'."
            )

        points = [_point(part, text) for part in parts[:3]]
        if not any(points[2]):
            raise ValueError(f"The camera's view-up vector cannot be zero, got '{text}'.")

        scale = None
        if len(parts) == 4:
            scale = _float(parts[3], text)
            if scale <= 0:
                raise ValueError(f"The camera's parallel scale must be positive, got '{text}'.")

        return cls(points[0], points[1], points[2], scale)


class ShownView(NamedTuple):
    """
    The camera and window size an interactive window was closed with, to reproduce its view
    when saving (see GridPlotter.show)
    """

    camera: Camera
    window_size: tuple[int, int]

    def cli_options(self) -> str:
        """
        The opm-vis-pv options that reproduce this view

        Returns
        -------
        str
            e.g. "--camera X,Y,Z/FX,FY,FZ/UX,UY,UZ --window-size 1024 768"
        """
        width, height = self.window_size
        return f"--camera {self.camera.to_text()} --window-size {width} {height}"


def _point(part: str, text: str) -> _Point:
    """
    Parse "X,Y,Z" into a point
    """
    values = part.split(",")
    if len(values) != 3:
        raise ValueError(
            f"Each camera point needs 3 comma-separated numbers, got '{part}' in '{text}'."
        )
    x, y, z = (_float(value, text) for value in values)
    return (x, y, z)


def _float(value: str, text: str) -> float:
    """
    Parse one number of a camera
    """
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"'{value}' in camera '{text}' is not a number.") from exc


def _number(value: float) -> str:
    """
    Format one camera number compactly, but precisely enough for UTM-sized coordinates
    """
    return f"{value:.10g}"


def camera_from_vtk(
    position: Sequence[float],
    focal_point: Sequence[float],
    view_up: Sequence[float],
    parallel_scale: float | None,
) -> Camera:
    """
    Build a Camera from a VTK camera's own values

    Parameters
    ----------
    position, focal_point, view_up : Sequence[float]
        As vtkCamera's GetPosition/GetFocalPoint/GetViewUp return them
    parallel_scale : float | None
        vtkCamera's GetParallelScale, or None if it is not in parallel projection

    Returns
    -------
    Camera
        The same camera, with plain Python floats
    """
    def point(values: Sequence[float]) -> _Point:
        return (float(values[0]), float(values[1]), float(values[2]))

    return Camera(
        point(position),
        point(focal_point),
        point(view_up),
        None if parallel_scale is None else float(parallel_scale),
    )
