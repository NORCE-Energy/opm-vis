""" Interactive PyVista plotter for OPM simulation results """
from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pyvista as pv
from numpy.typing import NDArray

from opm_vis.pvplot.data import CaseData
from opm_vis.pvplot.labels import axis_titles, scalar_bar_title
from opm_vis.pvplot.mesh import ACTIVE_INDEX, GridMesh
from opm_vis.pvplot.wells import well_paths
from opm_vis.utils.units import Label

# OPM's z axis is depth, increasing downwards, while VTK assumes z points up. Every camera
# therefore needs its view-up vector flipped, or the model renders with its deepest layer at
# the top of the screen.
_DEPTH_UP = (0.0, 0.0, -1.0)

# Camera setup per slice dimension for view_2d. Determined by rendering a single marked cell
# and checking where it lands on screen: the cross-sections need both the negative viewing
# side and the flipped view-up to put depth downwards and easting/northing to the right, while
# the k-slice map view needs neither.
_VIEW_2D = {
    "i": lambda plotter: (
        plotter.view_yz(negative=True),
        plotter.set_viewup(_DEPTH_UP),
    ),
    "j": lambda plotter: (
        plotter.view_xz(negative=True),
        plotter.set_viewup(_DEPTH_UP),
    ),
    "k": lambda plotter: plotter.view_xy(),
}

# Which coordinate axis points at the camera in each 2D view, and so should not be drawn
_OUT_OF_PLANE_AXIS = {"i": "x", "j": "y", "k": "z"}

# The axis names pyvista's own clip() accepts as a `normal`; matches its _NormalsLiteral, kept
# as our own alias since that name is private to pyvista.
_AxisName = Literal["x", "y", "z", "-x", "-y", "-z"]

# Fixed names for the actors pvplot manages itself, so repeated calls replace rather than stack
_TITLE_NAME = "pvplot-title"
_WELLS_OPEN = "pvplot-wells-open"
_WELLS_SHUT = "pvplot-wells-shut"
_WELL_LABELS = "pvplot-well-labels"

# Cell array a vector's components are gathered into before glyphing. Reused across calls
# rather than named after the keywords, since a glyph actor's source mesh may be shared (the
# full grid) with other actors that should not see a per-keyword array appear on it.
_GLYPH_VECTORS = "GLYPH_VECTORS"


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
    carries_scalars: bool = True


@dataclass
class _GlyphSpec:
    """
    Recorded settings needed to rebuild a glyph actor's arrows at a new report step.

    Unlike scalar colouring, moving a glyph field to a new report step is not a matter of
    writing new values into the existing dataset: the arrows' positions, directions and
    lengths all come from the vector field itself, so the whole glyph mesh has to be rebuilt
    from scratch. The source mesh (the full grid or one of its slices) is kept so that rebuild
    reads the new values through the same ACTIVE_INDEX mapping the rest of pvplot uses, and the
    scale factor is kept fixed so arrow length stays comparable across report steps.
    """

    source: pv.DataSet
    x_keyword: str
    y_keyword: str
    z_keyword: str
    factor: float
    scale: bool
    geom: pv.PolyData | None


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

        # Set up the render window. pv.Plotter wants window_size as a list rather than a
        # tuple; a tuple is kept in our own signature since it is the immutable, idiomatic
        # choice for a fixed pair of dimensions.
        self.plotter = pv.Plotter(
            off_screen=off_screen,
            window_size=list(window_size) if window_size is not None else None,
        )
        if z_scale != 1.0:
            self.plotter.set_scale(zscale=z_scale)

        # Internal variables. Every dataset added is tracked by name so its scalars can be
        # updated later; see the _MeshActor docstring. Glyph actors are also registered in
        # _actors (so actor_names() and duplicate-name checks see them for free), with their
        # extra bookkeeping kept here under the same name; see _GlyphSpec.
        self._actors: dict[str, _MeshActor] = {}
        self._glyphs: dict[str, _GlyphSpec] = {}

        # What is currently coloured, set by set_scalars, and the current title
        self.keyword = ""
        self.rstep: int | None = None
        self.title = ""
        self._colour_map: tuple[str, bool] | None = None
        self._scalar_bar_title: str | None = None
        self._view_2d_dim: str | None = None
        self._axes_shown = False

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

        # Excluded from set_scalars: a wireframe is context, and colouring it by the same
        # field as the slices in front of it only adds noise.
        # algorithm is passed explicitly because PyVista is in the middle of changing its
        # default, and this is the one that returns the boundary faces
        return self._add(
            self.grid.mesh.extract_surface(algorithm="dataset_surface"),
            name,
            carries_scalars=False,
            **kwargs,
        )

    def add_threshold(
        self,
        keyword: str,
        rstep: int,
        value: float | tuple[float, float],
        *,
        invert: bool = False,
        name: str | None = None,
        **kwargs,
    ) -> str:
        """
        Add only the cells whose value of a keyword passes a threshold

        Parameters
        ----------
        keyword : str
            OPM keyword to threshold on
        rstep : int
            Report step to take the values from
        value : float | tuple[float, float]
            Lower bound, or a (lower, upper) range
        invert : bool, optional
            Keep the cells that fail the threshold instead, by default False
        name : str | None, optional
            Name to register the subset under, by default None, which uses e.g.
            "SGAS-threshold".
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the subset was registered under

        Notes
        -----
        Useful for showing a plume or a swept region on its own. The subset keeps its
        ACTIVE_INDEX array, so set_scalars can still colour it by any keyword and at any report
        step afterwards - the threshold fixes which cells are shown, not what they show.

        threshold() is typed generically over every PyVista dataset, so its declared return
        type is wider than what it can actually produce from an UnstructuredGrid input; the
        cast below reflects that narrower, verified invariant.
        """
        mesh = self.grid.mesh

        # Captured before the assignment: attaching cell data to a mesh with no active scalars
        # makes the new array active by itself
        previous = mesh.active_scalars_name

        mesh.cell_data[keyword] = self.case.read(keyword, rstep)[
            mesh.cell_data[ACTIVE_INDEX]
        ]
        try:
            subset = cast(
                pv.UnstructuredGrid, mesh.threshold(value, scalars=keyword, invert=invert)
            )
        finally:
            # threshold() leaves the array it filtered on selected as the grid's active
            # scalars, which would silently start colouring anything already showing it
            mesh.set_active_scalars(previous)

        return self._add(subset, name or f"{keyword}-threshold", **kwargs)

    def add_clip(
        self,
        normal: _AxisName | tuple[float, float, float] = "z",
        origin: tuple[float, float, float] | None = None,
        *,
        invert: bool = True,
        crinkle: bool = False,
        name: str | None = None,
        **kwargs,
    ) -> str:
        """
        Add the grid cut by a plane

        Parameters
        ----------
        normal : _AxisName | tuple[float, float, float], optional
            Plane normal, either an axis name ("x", "y", "z", "-x", "-y" or "-z") or a vector,
            by default "z"
        origin : tuple[float, float, float] | None, optional
            Point on the plane, by default None, which uses the centre of the grid
        invert : bool, optional
            Keep the side the normal points away from, by default True
        crinkle : bool, optional
            Keep whole cells rather than cutting through them, by default False. Leaves a
            jagged face but every cell keeps its original geometry.
        name : str | None, optional
            Name to register the subset under, by default "clip"
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the subset was registered under

        Notes
        -----
        Cut cells keep the cell data of the cell they came from, ACTIVE_INDEX included, so a
        clipped grid can still be coloured by set_scalars.

        clip() is typed generically over every PyVista dataset (including composite
        MultiBlocks, which do not apply here), so its declared return type is wider than what
        it can actually produce from an UnstructuredGrid input; the cast below reflects that
        narrower, verified invariant.
        """
        subset = cast(
            pv.UnstructuredGrid,
            self.grid.mesh.clip(
                normal=normal,
                origin=origin if origin is not None else self.grid.mesh.center,
                invert=invert,
                crinkle=crinkle,
            ),
        )

        return self._add(subset, name or "clip", **kwargs)

    def add_wells(
        self,
        rstep: int,
        *,
        slice_dim: str | None = None,
        slice_ind: int | None = None,
        labels: bool = True,
        open_color: str = "black",
        shut_color: str = "red",
        line_width: float = 4.0,
        **kwargs,
    ) -> None:
        """
        Draw the wells present at one report step

        Parameters
        ----------
        rstep : int
            Report step
        slice_dim : str | None, optional
            Only draw wells with a completion on this i-, j- or k-slice, by default None,
            which draws every well in the grid
        slice_ind : int | None, optional
            Index of the slice; required together with slice_dim
        labels : bool, optional
            Annotate each well with its name, by default True
        open_color : str, optional
            Colour for open wells, by default "black"
        shut_color : str, optional
            Colour for shut wells, by default "red"
        line_width : float, optional
            Trajectory line width in pixels, by default 4.0
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Notes
        -----
        Trajectories are full 3D paths, drawn in full even when slice_dim/slice_ind is given:
        the slice only decides which wells are included, not how much of one is shown, unlike
        the per-slice truncation opm_vis.plot does. Calling this again for another report step
        replaces what is already there, which is what lets an animation follow wells opening
        and shutting.
        """
        if slice_dim is None:
            if slice_ind is not None:
                raise ValueError("slice_dim is required when slice_ind is given!")
        elif slice_ind is None:
            raise ValueError("slice_ind is required when slice_dim is given!")

        paths = well_paths(
            self.grid.egrid, self.case.wells, rstep, slice_dim=slice_dim, slice_ind=slice_ind
        )

        # Replace whatever a previous call left behind, so report steps do not stack up
        for name in (_WELLS_OPEN, _WELLS_SHUT):
            if name in self._actors:
                self.plotter.remove_actor(self._actors.pop(name).actor)

        for name, mesh, color in (
            (_WELLS_OPEN, paths.open_wells, open_color),
            (_WELLS_SHUT, paths.shut_wells, shut_color),
        ):
            if mesh is None:
                continue
            self._add(
                mesh,
                name,
                carries_scalars=False,
                color=color,
                line_width=line_width,
                **kwargs,
            )

        if labels and len(paths.label_names) > 0:
            self.plotter.add_point_labels(
                paths.label_points,
                paths.label_names,
                name=_WELL_LABELS,
                font_size=10,
                shape=None,
                always_visible=True,
            )

    def add_glyphs(
        self,
        x_keyword: str,
        y_keyword: str,
        z_keyword: str,
        rstep: int,
        *,
        slice_dim: str | None = None,
        slice_ind: int | None = None,
        quads: bool = False,
        scale: bool = True,
        factor: float | None = None,
        geom: pv.PolyData | None = None,
        name: str | None = None,
        **kwargs,
    ) -> str:
        """
        Add vector glyphs (arrows) built from three keyword components

        Parameters
        ----------
        x_keyword : str
            OPM keyword giving the vector's x-component, e.g. "DISPX"
        y_keyword : str
            OPM keyword giving the vector's y-component, e.g. "DISPY"
        z_keyword : str
            OPM keyword giving the vector's z-component, e.g. "DISPZ"
        rstep : int
            Report step to read the components at
        slice_dim : str | None, optional
            Restrict the glyphs to one i-, j- or k-slice, by default None, which places one
            glyph at every active cell of the whole grid
        slice_ind : int | None, optional
            Index of the slice; required together with slice_dim
        quads : bool, optional
            Place glyphs from cell-centre points alone instead of the full hexahedral mesh,
            by default False. Cheaper on a large grid, and never builds the full mesh at all -
            same idea as add_slice's own quads argument, but for a placement point rather than
            a face. Has no effect on where the arrows end up; see the Notes below.
        scale : bool, optional
            Scale each arrow by its own vector's magnitude, by default True. False draws
            every arrow the same length, showing only direction.
        factor : float | None, optional
            Factor the vectors are multiplied by before glyphing, by default None, which
            picks one that draws the largest vector at about the width of one grid cell.
        geom : pv.PolyData | None, optional
            Glyph shape, by default None, which draws PyVista's arrow
        name : str | None, optional
            Name to register the glyphs under, by default None, which uses the three
            keywords (and the slice, if one was given)
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.add_mesh

        Returns
        -------
        str
            Name the glyphs were registered under

        Notes
        -----
        Physical vector fields (e.g. displacement, in metres) are usually many orders of
        magnitude smaller than the grid's own coordinates, which is why the vectors are scaled
        before glyphing rather than drawn at their literal length.

        The factor picked here - or passed explicitly - is reused by every later set_vectors
        call on this actor, so arrow length stays comparable across report steps rather than
        each frame being renormalised to fill the same space. Pass global_glyph_factor(...)
        explicitly if this report step's own largest vector is not representative of the
        whole run.

        quads only changes how a placement point is obtained, not the arrows themselves: a
        glyph only ever needs one point per cell, never that cell's actual volume, so skipping
        the full hexahedral build (and, on a slice, touching only that slice's cells) changes
        nothing about what gets drawn. The one real difference is on a slice: quads places the
        point at the slice face GridSlice3D already exposes, which sits exactly on a
        quads=True add_slice's surface, whereas the default places it at the cell's true
        volumetric centre - inside a solid add_slice actor if that one is not also using
        quads, and invisible there as a result.

        Glyph actors take no part in set_scalars: an arrow's points carry per-glyph, not
        per-cell, data, so there is no ACTIVE_INDEX left to write scalar values through.
        Coloured by magnitude (scalars="GlyphScale") by default; pass color=... for a flat
        colour instead. PyVista colours by scalars whenever they are given regardless of a
        color also being passed, so a caller-given color always takes priority here rather
        than being silently overridden by the magnitude colouring.
        """
        source = self._glyph_source(slice_dim, slice_ind, quads=quads)
        vectors = self._glyph_vectors(source, x_keyword, y_keyword, z_keyword, rstep)

        if factor is None:
            peak = float(np.linalg.norm(vectors, axis=1).max())
            factor = self._auto_glyph_factor(source, peak, scale=scale)

        glyphs = self._build_glyphs(source, vectors, scale=scale, factor=factor, geom=geom)

        default_name = f"{x_keyword}-{y_keyword}-{z_keyword}"
        if slice_dim is not None:
            default_name += f"-{slice_dim}{slice_ind}"

        if "color" in kwargs:
            # An explicit solid colour overrides magnitude colouring. Both cannot simply be
            # passed together: add_mesh colours by scalars whenever they are given at all, so
            # scalars has to be left out entirely rather than relying on color to win.
            kwargs.pop("scalars", None)
        else:
            kwargs.setdefault("scalars", "GlyphScale")

        registered = self._add(glyphs, name or default_name, carries_scalars=False, **kwargs)

        self._glyphs[registered] = _GlyphSpec(
            source=source,
            x_keyword=x_keyword,
            y_keyword=y_keyword,
            z_keyword=z_keyword,
            factor=factor,
            scale=scale,
            geom=geom,
        )
        self.rstep = rstep

        return registered

    def set_scalars(
        self,
        keyword: str,
        rstep: int,
        *,
        clim: tuple[float, float] | None = None,
        cmap: str = "viridis",
        log_scale: bool = False,
        scalar_bar: bool = True,
    ) -> None:
        """
        Colour everything that has been added by one keyword at one report step

        Parameters
        ----------
        keyword : str
            OPM keyword to colour by
        rstep : int
            Report step
        clim : tuple[float, float] | None, optional
            Colour limits, by default None, which takes the range of this report step's data.
            Pass global_clim(...) to keep the colours comparable across report steps.
        cmap : str, optional
            Matplotlib colour map name, by default "viridis"
        log_scale : bool, optional
            Map colours logarithmically, by default False. Useful for permeability.
        scalar_bar : bool, optional
            Show a scalar bar labelled with the keyword and its unit, by default True

        Notes
        -----
        Values are written into the datasets already on screen and the scene is re-rendered.
        Nothing is rebuilt or re-added, which is what makes stepping through report steps
        cheap; opm_vis.plot instead creates a fresh artist per frame and never clears the old
        ones.

        Each dataset is indexed through its own ACTIVE_INDEX array, so slices, the full grid
        and thresholded subsets can all be coloured from one read of the file.

        Every dataset gets the same colour limits, so a single scalar bar is valid for all of
        them. opm_vis.plot has to warn that its colorbar only describes the first slice.
        """
        targets = [entry for entry in self._actors.values() if entry.carries_scalars]
        if not targets:
            raise RuntimeError(
                "Nothing to colour! Call add_slice or add_grid before set_scalars."
            )

        data = self.case.read(keyword, rstep)
        scalar_range = (
            clim if clim is not None else self.case.value_range(keyword, [rstep])
        )

        for entry in targets:
            entry.mesh.cell_data[keyword] = data[entry.mesh.cell_data[ACTIVE_INDEX]]
            entry.mesh.set_active_scalars(keyword)

            mapper = entry.actor.mapper

            # Setting the dataset's active scalars is not enough: the mapper has its own
            # array selection, and without pointing it at the array by name it keeps
            # colouring by whatever it was bound to when the mesh was added. Every array
            # pvplot attaches is cell data, hence the cell field data scalar mode.
            mapper.SetScalarModeToUseCellFieldData()
            mapper.SelectColorArray(keyword)
            mapper.scalar_visibility = True
            mapper.scalar_range = scalar_range

            # Rebuilding the colour map is wasted work when only the report step changed,
            # which is the common case while animating
            if (cmap, log_scale) != self._colour_map:
                mapper.lookup_table.cmap = cmap
                mapper.lookup_table.log_scale = log_scale

        if scalar_bar:
            self._update_scalar_bar(targets[0].actor.mapper, keyword)

        # Record what is currently shown, for the scalar bar and title
        self.keyword = keyword
        self.rstep = rstep
        self._colour_map = (cmap, log_scale)

        # Assigning cell data marks the dataset modified, but only an explicit render puts it
        # on screen: screenshot() on its own reuses the previous frame buffer.
        self.plotter.render()

    def _update_scalar_bar(self, mapper: Any, keyword: str) -> None:
        """
        Show a scalar bar for the keyword, replacing any bar for a different one

        Parameters
        ----------
        mapper : Any
            Mapper of one of the coloured actors. All of them share the same colour limits and
            lookup table, so any one of them describes the whole scene.
        keyword : str
            OPM keyword currently being shown
        """
        title = scalar_bar_title(self.label, keyword)

        # Only the report step usually changes, and the bar already reads correctly then
        if title == self._scalar_bar_title:
            return

        if self._scalar_bar_title is not None:
            self.plotter.remove_scalar_bar(self._scalar_bar_title)

        self.plotter.add_scalar_bar(title=title, mapper=mapper)
        self._scalar_bar_title = title

    def global_clim(
        self, keyword: str, rsteps: Sequence[int] | None = None
    ) -> tuple[float, float]:
        """
        Colour limits covering a keyword's full range over several report steps

        Parameters
        ----------
        keyword : str
            OPM keyword
        rsteps : Sequence[int] | None, optional
            Report steps to cover, by default None, which uses every report step in the case

        Returns
        -------
        tuple[float, float]
            (minimum, maximum) to pass as set_scalars' clim
        """
        if rsteps is None:
            rsteps = self.case.report.report_steps()

        return self.case.value_range(keyword, rsteps)

    def set_vectors(self, rstep: int, *, name: str | None = None) -> None:
        """
        Rebuild glyph actors for a new report step's vector field

        Parameters
        ----------
        rstep : int
            Report step
        name : str | None, optional
            Update only the glyph actor registered under this name, by default None, which
            updates every glyph actor added so far

        Notes
        -----
        A glyph's position, direction and length all come from the vector field itself, so
        unlike set_scalars this cannot write new values into the existing dataset - the
        arrows are rebuilt from scratch and the actor's dataset is swapped for the new one.
        Each actor's scale factor stays whatever add_glyphs picked or was given, so arrow
        length remains comparable across report steps.
        """
        if name is not None:
            if name not in self._glyphs:
                raise KeyError(f"No glyph actor named '{name}' has been added!")
            targets = [name]
        else:
            targets = list(self._glyphs)
            if not targets:
                raise RuntimeError("Nothing to update! Call add_glyphs before set_vectors.")

        for target in targets:
            spec = self._glyphs[target]
            vectors = self._glyph_vectors(
                spec.source, spec.x_keyword, spec.y_keyword, spec.z_keyword, rstep
            )
            glyphs = self._build_glyphs(
                spec.source, vectors, scale=spec.scale, factor=spec.factor, geom=spec.geom
            )

            entry = self._actors[target]
            entry.mesh = glyphs
            entry.actor.mapper.dataset = glyphs

        self.rstep = rstep

        # Swapping the mapper's dataset marks it modified, but only an explicit render puts it
        # on screen, the same as set_scalars.
        self.plotter.render()

    def global_glyph_factor(
        self,
        x_keyword: str,
        y_keyword: str,
        z_keyword: str,
        rsteps: Sequence[int] | None = None,
        *,
        slice_dim: str | None = None,
        slice_ind: int | None = None,
        quads: bool = False,
        scale: bool = True,
    ) -> float:
        """
        Scale factor covering a vector field's largest magnitude over several report steps

        Parameters
        ----------
        x_keyword : str
            OPM keyword giving the vector's x-component
        y_keyword : str
            OPM keyword giving the vector's y-component
        z_keyword : str
            OPM keyword giving the vector's z-component
        rsteps : Sequence[int] | None, optional
            Report steps to cover, by default None, which uses every report step in the case
        slice_dim : str | None, optional
            Match the slice add_glyphs will be restricted to, by default None
        slice_ind : int | None, optional
            Index of the slice; required together with slice_dim
        quads : bool, optional
            Match the quads argument add_glyphs will be called with, by default False. The two
            paths' characteristic lengths differ slightly, so the factor computed here is only
            exactly right for a later add_glyphs call using the same value.
        scale : bool, optional
            Match the scale argument add_glyphs will be called with, by default True

        Returns
        -------
        float
            Factor to pass as add_glyphs' factor, so the same scaling holds at every report
            step covered here rather than a new one being picked for each

        Notes
        -----
        Without this, add_glyphs auto-scales arrows to whatever the given report step's own
        largest vector happens to be - the same physical displacement would then draw at a
        different size depending on the step, the same distortion global_clim exists to
        prevent for colours.
        """
        if rsteps is None:
            rsteps = self.case.report.report_steps()

        source = self._glyph_source(slice_dim, slice_ind, quads=quads)
        peak = 0.0
        for rstep in rsteps:
            vectors = self._glyph_vectors(source, x_keyword, y_keyword, z_keyword, rstep)
            peak = max(peak, float(np.linalg.norm(vectors, axis=1).max()))

        return self._auto_glyph_factor(source, peak, scale=scale)

    def view_2d(self, slice_dim: str) -> None:
        """
        Look straight at an i-, j- or k-slice, with parallel projection

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k', the slice dimension to look down

        Notes
        -----
        Perspective is switched off, so the view is a true projection with no foreshortening -
        the equivalent of the flat 2D axes in opm_vis.plot, but reached with a camera rather
        than a separate class.

        Cross-sections are oriented with depth increasing downwards and easting or northing
        increasing to the right. The k-slice map view is laid out the conventional way, with
        easting to the right and northing up. Note that because OPM's z axis is depth, no
        camera can give a map both northing up and easting right while looking from above; the
        conventional layout is chosen over the literal viewing side.
        """
        if slice_dim not in _VIEW_2D:
            raise TypeError(
                f'{slice_dim} slice dimension is not valid! Choose "i", "j", or "k"'
            )

        _VIEW_2D[slice_dim](self.plotter)
        self.plotter.enable_parallel_projection()
        self.plotter.reset_camera()

        # Remembered so that show_axes_grid can leave out the axis pointing at the camera
        self._view_2d_dim = slice_dim

    def view_3d(self, *, azimuth: float = 30.0, elevation: float = 45.0) -> None:
        """
        Look at the model from above at an angle, with depth increasing downwards

        Parameters
        ----------
        azimuth : float, optional
            Degrees to rotate the camera about the depth axis, by default 30.0
        elevation : float, optional
            Degrees to lift the camera, by default 45.0

        Notes
        -----
        The view-up vector is flipped to -z. PyVista's default assumes z points up, so on
        OPM's depth-positive-down coordinates the isometric view otherwise renders the model
        upside down, with the deepest layer above the shallowest.

        That flip also leaves the camera *below* the model, so an elevation of zero looks up at
        the base of the reservoir. The elevation needed to get above it depends on the vertical
        exaggeration - roughly 15 degrees at z_scale 15, but past 25 at z_scale 1 - and the
        default of 45 clears it either way. Measured by marking the top and bottom layers and
        checking which one is not occluded.
        """
        self.plotter.disable_parallel_projection()
        self.plotter.view_isometric()
        self.plotter.set_viewup(_DEPTH_UP)

        # All three axes are meaningful again, see show_axes_grid
        self._view_2d_dim = None

        if azimuth:
            self.plotter.camera.Azimuth(azimuth)
        if elevation:
            self.plotter.camera.Elevation(elevation)

        self.plotter.reset_camera()

    def set_z_scale(self, z_scale: float) -> None:
        """
        Set the vertical exaggeration

        Parameters
        ----------
        z_scale : float
            Factor to stretch the depth axis by. Reservoirs are far wider than they are thick,
            so a value above 1 is usually needed before layering is visible.
        """
        self.plotter.set_scale(zscale=z_scale)

    def show_axes_grid(self, **kwargs) -> None:
        """
        Show a labelled bounding box around the scene

        Parameters
        ----------
        kwargs : optional
            Optional arguments passed to pyvista.Plotter.show_bounds

        Notes
        -----
        Axis titles carry the case's own length unit, so a field-units case is labelled in
        feet. opm_vis.plot hard-codes metres whatever the case uses.

        Call this after choosing the view. In a 2D view the axis pointing at the camera is
        left out, because drawing it would put a meaningless third axis - and its tick labels -
        across the middle of the picture; the bounding box has no way of knowing it is being
        looked at end-on. That decision is made here, from whichever view is current, so
        changing the view afterwards means calling this again.

        One limitation remains in the 2D cross-sections: VTK draws no ticks along the depth
        axis when it is looked at edge-on, so those views get a horizontal scale but no vertical
        one. The mesh geometry is unaffected.
        """
        xtitle, ytitle, ztitle = axis_titles(self.label)
        kwargs.setdefault("xtitle", xtitle)
        kwargs.setdefault("ytitle", ytitle)
        kwargs.setdefault("ztitle", ztitle)

        if self._view_2d_dim is not None:
            hidden = _OUT_OF_PLANE_AXIS[self._view_2d_dim]
            kwargs.setdefault(f"show_{hidden}axis", False)
            kwargs.setdefault(f"show_{hidden}labels", False)

        # Replace any box a previous call left behind rather than adding a second one
        if self._axes_shown:
            self.plotter.remove_bounds_axes()

        self.plotter.show_bounds(**kwargs)
        self._axes_shown = True

        # Without this the new box does not appear if anything has already been rendered, in
        # the same way that set_scalars needs an explicit render to show new values
        self.plotter.render()

    def set_title(self, text: str | None = None) -> None:
        """
        Put a title above the scene

        Parameters
        ----------
        text : str | None, optional
            Title text, by default None, which uses the report date of whatever set_scalars
            last showed

        Notes
        -----
        Added under a fixed name so that repeated calls replace the title rather than stacking
        text on top of itself, which matters when titling every frame of an animation.
        """
        if text is None:
            if self.rstep is None:
                raise RuntimeError(
                    "No report step has been shown yet, so there is no date to title with! "
                    "Call set_scalars first or pass an explicit text."
                )
            text = self.case.report.report_date(self.rstep).strftime("%d.%m.%Y")

        self.plotter.add_text(text, name=_TITLE_NAME, position="upper_edge", font_size=10)
        self.title = text

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

    def animate(
        self,
        keyword: str,
        filename: str | Path | None = None,
        *,
        rsteps: Sequence[int] | None = None,
        fps: int = 3,
        clim: tuple[float, float] | None = None,
        wells: bool = False,
        wells_slice_dim: str | None = None,
        wells_slice_ind: int | None = None,
        vectors: bool = False,
        title: bool = True,
        **kwargs,
    ) -> None:
        """
        Show or write an animation of one keyword over several report steps

        Parameters
        ----------
        keyword : str
            OPM keyword to colour by
        filename : str | Path | None, optional
            File to write, by default None, which plays the animation in the render window
            instead of writing anything. A ".gif" suffix writes a GIF, anything else a movie
            (e.g. ".mp4").
        rsteps : Sequence[int] | None, optional
            Report steps to animate, by default None, which uses every report step
        fps : int, optional
            Frames per second, by default 3
        clim : tuple[float, float] | None, optional
            Colour limits, by default None, which spans every frame so the colours stay
            comparable throughout
        wells : bool, optional
            Redraw wells each frame, by default False. Worth turning on when wells open or shut
            during the period being animated.
        wells_slice_dim : str | None, optional
            Restrict wells to those with a completion on this i-, j- or k-slice, by default
            None, which draws every well in the grid. Only used when wells is True.
        wells_slice_ind : int | None, optional
            Index of the slice; required together with wells_slice_dim
        vectors : bool, optional
            Update every glyph actor each frame, by default False. Requires add_glyphs to have
            been called first; its scale factor is left untouched, so pass factor or
            global_glyph_factor(...) there if arrow length should stay comparable throughout.
        title : bool, optional
            Title each frame with its report date, by default True
        kwargs : optional
            Optional arguments passed to set_scalars

        Notes
        -----
        Each frame only writes new values into the datasets already on screen, so the geometry
        is built once for the whole animation. Colour limits are computed once up front rather
        than per frame, which is what keeps a frame's colours meaningful next to its
        neighbours'.

        Playing (filename=None) needs an actual on-screen window, so construct the plotter
        with off_screen=False (the default) in that case - there is nothing to show
        interactively otherwise.
        """
        if not self._actors:
            raise RuntimeError(
                "Nothing to animate! Call add_slice or add_grid before animate."
            )

        if rsteps is None:
            rsteps = self.case.report.report_steps()
        if clim is None:
            clim = self.global_clim(keyword, rsteps)

        frame_kwargs = {
            "wells": wells,
            "wells_slice_dim": wells_slice_dim,
            "wells_slice_ind": wells_slice_ind,
            "vectors": vectors,
            "title": title,
            **kwargs,
        }

        if filename is None:
            self._play_frames(keyword, rsteps, fps, clim, **frame_kwargs)
        else:
            self._write_frames(keyword, Path(filename), rsteps, fps, clim, **frame_kwargs)

    def _advance_frame(
        self,
        keyword: str,
        rstep: int,
        clim: tuple[float, float],
        *,
        wells: bool,
        wells_slice_dim: str | None,
        wells_slice_ind: int | None,
        vectors: bool,
        title: bool,
        **kwargs,
    ) -> None:
        """
        Show one report step of an animation

        Parameters
        ----------
        keyword : str
            OPM keyword to colour by
        rstep : int
            Report step
        clim : tuple[float, float]
            Colour limits
        wells : bool
            Redraw wells at this report step
        wells_slice_dim : str | None
            Restrict wells to those with a completion on this slice; see animate()
        wells_slice_ind : int | None
            Index of the slice; required together with wells_slice_dim
        vectors : bool
            Update every glyph actor at this report step
        title : bool
            Title the frame with its report date
        kwargs : optional
            Optional arguments passed to set_scalars

        Notes
        -----
        Shared by animate()'s two ways of stepping through report steps - writing frames to a
        movie file, or playing them in the render window - since advancing to the next report
        step is identical either way; only what happens with the rendered frame differs.
        """
        self.set_scalars(keyword, rstep, clim=clim, **kwargs)
        if wells:
            self.add_wells(rstep, slice_dim=wells_slice_dim, slice_ind=wells_slice_ind)
        if vectors:
            self.set_vectors(rstep)
        if title:
            self.set_title()

    def _write_frames(
        self,
        keyword: str,
        filename: Path,
        rsteps: Sequence[int],
        fps: int,
        clim: tuple[float, float],
        **frame_kwargs,
    ) -> None:
        """
        Write an animation to file; see animate()

        Parameters
        ----------
        keyword : str
            OPM keyword to colour by
        filename : Path
            File to write. A ".gif" suffix writes a GIF, anything else a movie (e.g. ".mp4").
        rsteps : Sequence[int]
            Report steps to animate
        fps : int
            Frames per second
        clim : tuple[float, float]
            Colour limits
        frame_kwargs : optional
            wells/vectors/title and any further kwargs, passed on to _advance_frame
        """
        if filename.suffix.lower() == ".gif":
            self.plotter.open_gif(str(filename), fps=fps)
        else:
            # open_movie names the same argument differently, and forwards an unknown fps
            # straight into imageio where it collides with its own
            self.plotter.open_movie(str(filename), framerate=fps)

        try:
            for rstep in rsteps:
                self._advance_frame(keyword, rstep, clim, **frame_kwargs)
                self.plotter.write_frame()
        finally:
            # The file is only written out when the writer is closed. Closing the writer rather
            # than the plotter leaves the scene usable afterwards. mwriter is set by open_gif
            # or open_movie just above, so it is never actually None here - the guard is only
            # to satisfy its Optional type.
            if self.plotter.mwriter is not None:
                self.plotter.mwriter.close()

    def _play_frames(
        self,
        keyword: str,
        rsteps: Sequence[int],
        fps: int,
        clim: tuple[float, float],
        **frame_kwargs,
    ) -> None:
        """
        Play an animation in the render window; see animate()

        Parameters
        ----------
        keyword : str
            OPM keyword to colour by
        rsteps : Sequence[int]
            Report steps to animate
        fps : int
            Frames per second
        clim : tuple[float, float]
            Colour limits
        frame_kwargs : optional
            wells/vectors/title and any further kwargs, passed on to _advance_frame

        Notes
        -----
        Uses the same pattern PyVista's own streaming-data examples use for a live view:
        show(interactive_update=True) once up front so it returns immediately instead of
        blocking, then update() every frame to render and process window events (letting the
        user rotate or pan mid-animation) rather than a fresh blocking show() call each time.

        A window closed part-way through stops the loop early rather than raising, the same
        way closing a window during a plain show() is not an error. The window is left open
        afterwards - whether the animation ran to completion or was stopped early - so the
        last frame shown stays interactive until the caller closes it.
        """
        delay = 1.0 / fps if fps > 0 else 0.0

        self.plotter.show(auto_close=False, interactive_update=True)

        for rstep in rsteps:
            if self.plotter.iren is None:
                break  # the window was closed by the user

            self._advance_frame(keyword, rstep, clim, **frame_kwargs)

            self.plotter.update()
            time.sleep(delay)

        if self.plotter.iren is not None:
            # Re-enter a blocking show() so the last frame stays interactive (rotate/pan/zoom)
            # until the caller closes the window, instead of it going unresponsive the moment
            # this loop stops polling it.
            self.plotter.show()

    def close(self) -> None:
        """Close the render window and release its resources"""
        self.plotter.close()

    def _glyph_source(
        self, slice_dim: str | None, slice_ind: int | None, *, quads: bool
    ) -> pv.DataSet:
        """
        Resolve the mesh glyphs are placed on, for add_glyphs and global_glyph_factor

        Parameters
        ----------
        slice_dim : str | None
            'i', 'j', or 'k' slice of the 3D grid, or None for the whole active grid
        slice_ind : int | None
            Index of slice; required together with slice_dim
        quads : bool
            Use the cheap cell-centre-only path instead of the full hexahedral mesh; see
            add_glyphs

        Returns
        -------
        pv.DataSet
            The whole active grid, or the requested slice of it - either as hexahedra/the full
            mesh, or as bare cell-centre points when quads is True

        Notes
        -----
        Named to match add_slice's own quads argument, even though what it returns here is
        points rather than quads: glyphing only ever needs a placement point per cell, never
        the cell's actual geometry.
        """
        if slice_dim is None:
            if slice_ind is not None:
                raise ValueError("slice_dim is required when slice_ind is given!")
            return self.grid.cell_centers() if quads else self.grid.mesh

        if slice_ind is None:
            raise ValueError("slice_ind is required when slice_dim is given!")

        if quads:
            return self.grid.slice_cell_centers(slice_dim, slice_ind)

        return self.grid.extract_slice(slice_dim, slice_ind)

    def _glyph_vectors(
        self, source: pv.DataSet, x_keyword: str, y_keyword: str, z_keyword: str, rstep: int
    ) -> NDArray[Any]:
        """
        Read a vector's three components at one report step, aligned to a mesh's cells

        Parameters
        ----------
        source : pv.DataSet
            Mesh to align the components to, via its ACTIVE_INDEX cell array
        x_keyword : str
            OPM keyword giving the vector's x-component
        y_keyword : str
            OPM keyword giving the vector's y-component
        z_keyword : str
            OPM keyword giving the vector's z-component
        rstep : int
            Report step

        Returns
        -------
        NDArray[Any]
            Vectors with shape (source.n_cells, 3)
        """
        active_index = source.cell_data[ACTIVE_INDEX]

        return np.column_stack(
            [
                self.case.read(keyword, rstep)[active_index]
                for keyword in (x_keyword, y_keyword, z_keyword)
            ]
        )

    @staticmethod
    def _auto_glyph_factor(source: pv.DataSet, peak_magnitude: float, *, scale: bool) -> float:
        """
        Pick a factor that draws the largest vector at about the width of one grid cell

        Parameters
        ----------
        source : pv.DataSet
            Mesh the vectors were read onto
        peak_magnitude : float
            Largest vector magnitude the factor has to accommodate
        scale : bool
            Whether add_glyphs will scale each arrow by its own vector's magnitude

        Returns
        -------
        float
            Factor to multiply the vectors by before glyphing them

        Notes
        -----
        The characteristic length is derived from the source mesh's own bounding diagonal and
        cell count, so it is correct whether source is the whole grid or one of its slices,
        without needing to know how many cells span each axis.

        When scale is True, an arrow's length is its vector's magnitude times factor, so the
        peak magnitude has to be divided out to land near the characteristic length. When
        scale is False every arrow is drawn at the same length regardless of magnitude, so the
        factor alone sets that length and dividing by peak_magnitude would blow it up instead
        (a real displacement field is commonly five or six orders of magnitude smaller than
        the grid's own coordinates).
        """
        if source.n_cells == 0:
            raise ValueError("Cannot glyph an empty slice - it has no active cells!")

        char_length = source.length / source.n_cells ** (1 / 3)
        if not scale:
            return 0.8 * char_length

        return 0.8 * char_length / peak_magnitude if peak_magnitude > 0.0 else 1.0

    @staticmethod
    def _build_glyphs(
        source: pv.DataSet,
        vectors: NDArray[Any],
        *,
        scale: bool,
        factor: float,
        geom: pv.PolyData | None,
    ) -> pv.PolyData:
        """
        Build arrow glyphs for a vector field on a mesh's cells

        Parameters
        ----------
        source : pv.DataSet
            Mesh the vectors were read onto; one glyph is placed at each of its cell centres
        vectors : NDArray[Any]
            Vectors with shape (source.n_cells, 3)
        scale : bool
            Scale each arrow by its own vector's magnitude
        factor : float
            Factor the vectors are multiplied by before glyphing
        geom : pv.PolyData | None
            Glyph shape, None for PyVista's default arrow

        Returns
        -------
        pv.PolyData
            One glyph per cell

        Notes
        -----
        glyph() is typed generically over every PyVista dataset, so its declared return type
        is wider than what it can actually produce here; the cast reflects that narrower,
        verified invariant, matching the same pattern used for extract_cells/clean/threshold/
        clip elsewhere in this module.
        """
        source.cell_data[_GLYPH_VECTORS] = vectors
        source.set_active_vectors(_GLYPH_VECTORS, preference="cell")

        return cast(
            pv.PolyData,
            source.glyph(
                orient=_GLYPH_VECTORS,
                scale=_GLYPH_VECTORS if scale else False,
                factor=factor,
                geom=geom,
            ),
        )

    def _add(
        self, mesh: pv.DataSet, name: str, *, carries_scalars: bool = True, **kwargs
    ) -> str:
        """
        Add a dataset to the render window and register it

        Parameters
        ----------
        mesh : pv.DataSet
            Dataset to draw
        name : str
            Name to register it under
        carries_scalars : bool, optional
            Whether set_scalars should colour this dataset, by default True
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

        # set_scalars owns the scalar bar, so an actor never brings its own
        kwargs.setdefault("show_scalar_bar", False)

        actor = self.plotter.add_mesh(mesh, name=name, **kwargs)
        self._actors[name] = _MeshActor(
            mesh=mesh, actor=actor, carries_scalars=carries_scalars
        )

        return name

    def __enter__(self) -> GridPlotter:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
