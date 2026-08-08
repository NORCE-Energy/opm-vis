""" Interactive PyVista plotter for OPM simulation results """
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyvista as pv
from numpy.typing import NDArray

from opm_vis.pvplot.data import CaseData
from opm_vis.pvplot.mesh import GridMesh
from opm_vis.utils.units import Label


@dataclass
class _MeshActor:
    """
    One dataset shown by the plotter, paired with the actor drawing it.

    Keeping the dataset alongside the actor is what makes updating scalars in place possible:
    the values are written straight into the dataset's cell data and re-rendered, instead of
    building and adding a new actor per report step the way opm_vis.plot does.
    """

    mesh: pv.DataSet
    actor: Any


class GridPlotter:
    """
    Plot simulation results on the corner-point grid with PyVista.

    A single facade for both 2D and 3D views: a 2D view is a camera preset with parallel
    projection, not a separate class. Geometry is added once with the ``add_*`` methods, then
    the scalar field is swapped as often as needed.

    Examples
    --------
    >>> plotter = GridPlotter(["path/to/CASE"])           # doctest: +SKIP
    >>> plotter.add_slice("k", 0)                         # doctest: +SKIP
    >>> plotter.show()                                    # doctest: +SKIP
    """

    def __init__(
        self,
        paths: list[str],
        *,
        off_screen: bool = False,
        window_size: tuple[int, int] | None = None,
        z_scale: float = 1.0,
        weld: bool = True,
    ) -> None:
        """
        Initialize by setting up the render window and instantiating helper classes

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs. Each entry is a filename prefix.
        off_screen : bool, optional
            Render without opening a window, by default False. Needed for screenshots and
            animations on a machine with no display.
        window_size : tuple[int, int] | None, optional
            Render window size in pixels, by default None, which uses the PyVista theme.
        z_scale : float, optional
            Vertical exaggeration, by default 1.0. Reservoirs are far wider than they are
            thick, so a value above 1 is usually needed to see layering.
        weld : bool, optional
            Merge coincident grid corner points, by default True. See GridMesh.
        """
        # Internalize input
        self.paths = paths

        # Instantiate help classes
        self.case = CaseData(paths)
        self.grid = GridMesh(paths[0], weld=weld)
        self.label = Label(self.case.unit_convention())

        # Set up the render window
        self.plotter = pv.Plotter(off_screen=off_screen, window_size=window_size)
        if z_scale != 1.0:
            self.plotter.set_scale(zscale=z_scale)

        # Internal variables. Every dataset added is tracked by name so its scalars can be
        # updated later; see the _actors docstring.
        self._actors: dict[str, _MeshActor] = {}

    def add_slice(
        self,
        slice_dim: str,
        slice_ind: int,
        *,
        quads: bool = False,
        name: str | None = None,
        **kwargs,
    ) -> str:
        """
        Add one i-, j- or k-slice of the grid

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice
        quads : bool, optional
            Add the slice as flat quads instead of hexahedra, by default False. Cheaper on a
            large grid, but cannot be thresholded or clipped afterwards.
        name : str | None, optional
            Name to register the slice under, by default None, which uses e.g. "k0".
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the slice was registered under
        """
        mesh = (
            self.grid.quad_slice(slice_dim, slice_ind)
            if quads
            else self.grid.extract_slice(slice_dim, slice_ind)
        )

        return self._add(mesh, name or f"{slice_dim}{slice_ind}", **kwargs)

    def add_grid(self, *, name: str = "grid", **kwargs) -> str:
        """
        Add the whole active grid

        Parameters
        ----------
        name : str, optional
            Name to register the grid under, by default "grid"
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the grid was registered under
        """
        return self._add(self.grid.mesh, name, **kwargs)

    def add_wireframe(self, *, name: str = "wireframe", **kwargs) -> str:
        """
        Add the outline of the grid, without any data

        Parameters
        ----------
        name : str, optional
            Name to register the wireframe under, by default "wireframe"
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the wireframe was registered under

        Notes
        -----
        Only the outer boundary of the grid is drawn, which is what makes a wireframe of a
        large model readable at all. This is the equivalent of plot_grid in opm_vis.plot.
        """
        kwargs.setdefault("style", "wireframe")
        kwargs.setdefault("color", "grey")

        return self._add(self.grid.mesh.extract_surface(), name, **kwargs)

    def actor_names(self) -> list[str]:
        """
        Names of everything currently added to the plotter

        Returns
        -------
        list[str]
            Registered names, in the order they were added
        """
        return list(self._actors)

    def show(self, **kwargs) -> None:
        """
        Show the render window

        Parameters
        ----------
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.show
        """
        self.plotter.show(**kwargs)

    def screenshot(
        self, filename: str | Path | None = None, **kwargs
    ) -> NDArray[Any]:
        """
        Render to an image

        Parameters
        ----------
        filename : str | Path | None, optional
            File to write the image to, by default None, which only returns the pixels
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.screenshot

        Returns
        -------
        NDArray[Any]
            Rendered image with shape (height, width, 3)
        """
        return self.plotter.screenshot(filename, **kwargs)

    def close(self) -> None:
        """Close the render window and release its resources"""
        self.plotter.close()

    def _add(self, mesh: pv.DataSet, name: str, **kwargs) -> str:
        """
        Add a dataset to the render window and register it

        Parameters
        ----------
        mesh : pv.DataSet
            Dataset to draw
        name : str
            Name to register it under
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the dataset was registered under
        """
        if name in self._actors:
            raise ValueError(
                f"'{name}' has already been added to this plotter! Pass a different name."
            )

        actor = self.plotter.add_mesh(mesh, name=name, **kwargs)
        self._actors[name] = _MeshActor(mesh=mesh, actor=actor)

        return name

    def __enter__(self) -> GridPlotter:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
