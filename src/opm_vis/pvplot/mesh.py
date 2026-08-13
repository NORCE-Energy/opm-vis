""" Hexahedral PyVista mesh built from an OPM EGRID file """
from __future__ import annotations

import warnings
from collections.abc import Sequence
from glob import glob
from typing import cast

import numpy as np
import pyvista as pv
from numpy.typing import NDArray
from opm.io.ecl import EGrid

from opm_vis.utils.calc import resolve_calc_range
from opm_vis.utils.grid import GridSlice3D, slice_active_indices, slice_range_first_active_indices
from opm_vis.utils.mapaxes import has_mapaxes

# OPM numbers the 8 corners of a cell so that bit 0 of the corner index selects i, bit 1
# selects j and bit 2 selects k, where k (depth) increases downwards. A VTK_HEXAHEDRON
# instead wants the corners of one face in rotational order followed by the opposite face in
# the same order, which is this permutation of the OPM order.
_VTK_HEX_ORDER = np.array([0, 1, 3, 2, 4, 5, 7, 6])

# The same permutation with its two faces swapped, used when the grid's (i, j, k) system is
# mirrored with respect to (x, y, z) and _VTK_HEX_ORDER would give inside-out hexahedra.
_VTK_HEX_ORDER_MIRRORED = _VTK_HEX_ORDER[[4, 5, 6, 7, 0, 1, 2, 3]]

# Cell array mapping every mesh cell back to its EGRID active index. This is the
# authoritative map rather than the cell number itself, because pinched-out cells are
# dropped from the mesh: cell order equals active index order only when the grid has no NaN
# corner points. It survives extract_cells(), so any submesh can still look up cell data
# read from a restart or INIT file.
ACTIVE_INDEX = "ACTIVE_INDEX"

# Grid dimension axis (0=x/i, 1=y/j, 2=z/k) corresponding to each slice dimension
_SLICE_AXIS = {"i": 0, "j": 1, "k": 2}


# pylint: disable=unsubscriptable-object
# EGrid is a pybind class, so until stubs (.pyi files) are made, pylint
# unsubscriptable-object errors will pop up for e.g. self.egrid.dimension[0].
class GridMesh:
    """
    Corner-point grid from an OPM .EGRID file, as a PyVista hexahedral mesh.

    The mesh holds one VTK_HEXAHEDRON per active cell, so unlike the flat quads of
    :mod:`opm_vis.plot` it supports volume rendering, thresholding, clipping and arbitrary
    cuts. Simulation results can be attached directly as cell data, see the ACTIVE_INDEX
    cell array.
    """

    # Overridden in __init__ once the EGRID file has been located; kept as a class default so
    # instances built by bypassing __init__ (test doubles with no MAPAXES) still have it.
    apply_mapaxes = False

    def __init__(self, path: str, *, weld: bool = True) -> None:
        """
        Initialize EGrid class from input path

        Parameters
        ----------
        path : str
            Path to .EGRID file. This is a filename prefix, not a directory.
        weld : bool, optional
            Merge coincident corner points shared between neighbouring cells, by default
            True. See the weld_points note in _build.
        """
        # Instantiate EGrid class
        egrid_files = glob(path + "*.EGRID")
        if egrid_files:
            if len(egrid_files) > 1:
                warnings.warn(
                    f"Multiple .EGRID files in {path}. Importing {egrid_files[0]}."
                )
            self.egrid = EGrid(egrid_files[0])
            self.apply_mapaxes = has_mapaxes(egrid_files[0])
        else:
            raise FileNotFoundError(f"No .EGRID file found in {path}!")

        # Internalize input. The path is kept for quad_slice, which reuses the slice geometry
        # in opm_vis.utils.grid rather than the full mesh.
        self.path = path
        self.weld = weld

        # Internal variables. The mesh is built on first access, see the mesh property.
        self._mesh: pv.UnstructuredGrid | None = None

    @property
    def mesh(self) -> pv.UnstructuredGrid:
        """
        Hexahedral mesh of all active cells

        Returns
        -------
        pv.UnstructuredGrid
            One hexahedron per active cell, carrying the ACTIVE_INDEX, "I", "J" and "K"
            cell arrays

        Notes
        -----
        Built lazily on first access and cached afterwards, since building it costs one
        EGrid call per cell.
        """
        if self._mesh is None:
            self._mesh = self._build()
        return self._mesh

    @property
    def dimension(self) -> tuple[int, int, int]:
        """
        Grid dimensions

        Returns
        -------
        tuple[int, int, int]
            Number of cells along i, j and k
        """
        return tuple(self.egrid.dimension)

    @property
    def ijk(self) -> NDArray[np.int32]:
        """
        Grid indices of every mesh cell

        Returns
        -------
        NDArray[np.int32]
            (i, j, k) indices with shape (n_cells, 3)
        """
        return np.column_stack(
            [self.mesh.cell_data[name] for name in ("I", "J", "K")]
        )

    def slice_mask(self, slice_dim: str, slice_ind: int) -> NDArray[np.bool_]:
        r"""
        Boolean mask selecting the mesh cells that lie on one i-, j- or k-slice

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        NDArray[np.bool\_]
            Mask with shape (n_cells,)
        """
        axis = self._validate_slice(slice_dim, slice_ind)

        return self.ijk[:, axis] == slice_ind

    def extract_slice(self, slice_dim: str, slice_ind: int) -> pv.UnstructuredGrid:
        """
        Extract one i-, j- or k-slice as its own mesh

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        pv.UnstructuredGrid
            The cells of the slice, still as hexahedra

        Notes
        -----
        Cell data comes along, so the extracted mesh keeps its own ACTIVE_INDEX array and can
        be given property values without consulting the parent mesh.

        If the whole-grid mesh has already been built (e.g. add_grid() was also called, or
        this is a second slice), its corners are already in memory and reused here via
        extract_cells() - cheap, and avoids reading the file twice for the same cells.
        Otherwise, only this slice's own cells are read from the file at all: the whole grid
        is never built just to throw most of it away, unlike going through .mesh would.

        extract_cells() is typed generically over every PyVista dataset, so its declared
        return type is wider than what it can actually produce from a mesh that is already an
        UnstructuredGrid. The cast below reflects that narrower, verified invariant rather than
        working around a real ambiguity.
        """
        self._validate_slice(slice_dim, slice_ind)

        if self._mesh is not None:
            return cast(
                pv.UnstructuredGrid,
                self.mesh.extract_cells(self.slice_mask(slice_dim, slice_ind)),
            )

        active_indices = slice_active_indices(self.egrid, slice_dim, slice_ind)
        return self._mesh_from_corners(*self._read_corners(active_indices))

    def extract_range_slice(
        self, slice_dim: str, slice_ind: int, calc_count: int | None = None
    ) -> pv.UnstructuredGrid:
        """
        Extract a --calculator surface "slice" as its own mesh, as hexahedra

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice - the range this scans for each lateral position's first active
            cell always starts here
        calc_count : int | None, optional
            Value of --calc-count, by default None (continue to the grid's last layer); see
            opm_vis.utils.calc.resolve_calc_range

        Returns
        -------
        pv.UnstructuredGrid
            The cells picked out by slice_range_first_active_indices, still as hexahedra - one
            per lateral position that has at least one active cell in the range, each keeping
            its own real (possibly different-depth) geometry

        Notes
        -----
        Otherwise identical to extract_slice; see its own notes. The two are kept as separate
        methods, rather than one with an optional range, so that the plain (single-layer) path
        never pays for resolve_calc_range/slice_range_first_active_indices at all.
        """
        self._validate_slice(slice_dim, slice_ind)
        n_slice = self.egrid.dimension[_SLICE_AXIS[slice_dim]]
        _, end_ind = resolve_calc_range(slice_ind, n_slice, calc_count)
        active_indices = slice_range_first_active_indices(self.egrid, slice_dim, slice_ind, end_ind)

        if self._mesh is not None:
            mask = np.isin(self.mesh.cell_data[ACTIVE_INDEX], active_indices)
            return cast(pv.UnstructuredGrid, self.mesh.extract_cells(mask))

        return self._mesh_from_corners(*self._read_corners(active_indices))

    def quad_slice(
        self,
        slice_dim: str,
        slice_ind: int,
        *,
        surface: bool = False,
        calc_count: int | None = None,
    ) -> pv.PolyData:
        """
        Build one i-, j- or k-slice as flat quads, without building the full mesh

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice - the range surface=True scans for each lateral position's first
            active cell always starts here
        surface : bool, optional
            --calculator surface, by default False. When True, each lateral position's quad
            comes from its own first active cell scanning from slice_ind onwards (or
            calc_count further layers) instead of slice_ind's own layer, so quads can sit at
            different depths from one lateral position to the next - a "draped" surface rather
            than a flat one. See GridSlice3D.
        calc_count : int | None, optional
            Value of --calc-count, by default None (continue to the grid's last layer). Only
            used when surface is True; see opm_vis.utils.calc.resolve_calc_range.

        Returns
        -------
        pv.PolyData
            One quad per slice cell (or, with surface=True, per lateral position with at least
            one active cell in the range), carrying an ACTIVE_INDEX cell array

        Notes
        -----
        This is the cheap path for large grids: it touches only the cells on the slice rather
        than materialising every hexahedron in the model. The cost is that a quad has no
        volume, so thresholding, clipping and volume rendering need extract_slice instead.

        Reuses GridSlice3D from opm_vis.utils.grid, which already picks the four corners of
        the slice face out of the corner-point grid and drops pinched-out cells - and, with
        surface=True, drapes them over each lateral position's own first active layer instead
        of slice_ind's.
        """
        self._validate_slice(slice_dim, slice_ind)
        slc = GridSlice3D(self.path, slice_dim, slice_ind, calc_count=calc_count, surface=surface)

        # (ncells, 4, 3) corner points, with the matching list of active indices. GridSlice3D
        # keeps OPM's own depth-positive-down z, unlike the rest of GridMesh - see the note in
        # _read_corners - so it is negated here to match.
        corners = slc.cell_corners().copy()
        corners[:, :, 2] *= -1
        ncells = corners.shape[0]

        # VTK connectivity is a flat [npoints_of_face, point ids...] per face
        faces = np.hstack(
            (
                np.full((ncells, 1), 4, dtype=np.int64),
                np.arange(4 * ncells, dtype=np.int64).reshape(ncells, 4),
            )
        ).ravel()
        quads = pv.PolyData(corners.reshape(-1, 3), faces=faces)
        quads.cell_data[ACTIVE_INDEX] = np.asarray(slc.active_indices(), dtype=np.int64)

        # See the note in _build: ACTIVE_INDEX must not end up as the active scalars
        quads.set_active_scalars(None)

        return quads

    def cell_centers(self) -> pv.PolyData:
        """
        Cell centre points for every active cell, without building the hexahedral mesh

        Returns
        -------
        pv.PolyData
            One point per active cell, carrying an ACTIVE_INDEX cell array

        Notes
        -----
        Placing something at a cell's centre - a vector glyph, for instance - does not need
        the cell's actual volume, only a point. This skips hexahedron assembly and point
        welding entirely, reading just the mean of each cell's 8 corners, which is cheaper
        than .mesh and gives identical points: welding only merges coincident corners, it does
        not move them, so the mean of the 8 corners is the same whether or not they have been
        deduplicated into shared points first.
        """
        corners, _, active_index = self._read_corners()
        points = pv.PolyData(corners.mean(axis=1))
        points.cell_data[ACTIVE_INDEX] = active_index

        # See the note in _build: ACTIVE_INDEX must not end up as the active scalars
        points.set_active_scalars(None)

        return points

    def slice_cell_centers(self, slice_dim: str, slice_ind: int) -> pv.PolyData:
        """
        Cell centre points for one i-, j- or k-slice, without building the hexahedral mesh

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        pv.PolyData
            One point per slice cell, carrying an ACTIVE_INDEX cell array

        Notes
        -----
        Reuses GridSlice3D exactly as quad_slice does, so only the cells on the slice are ever
        read from the file - not the whole grid.

        The point placed for each cell is the centre of the slice face GridSlice3D already
        computes, not the true cell-volume centroid: the two coincide in the slice's own
        plane and differ only along its thickness. Keeping to the face is what places a glyph
        exactly on a quad_slice's surface instead of at the cell's mid-depth, buried inside it.
        """
        self._validate_slice(slice_dim, slice_ind)

        slc = GridSlice3D(self.path, slice_dim, slice_ind)
        centers = slc.cell_centers().copy()
        centers[:, 2] *= -1  # GridSlice3D keeps OPM's depth-positive-down z; see _read_corners
        points = pv.PolyData(centers)
        points.cell_data[ACTIVE_INDEX] = np.asarray(slc.active_indices(), dtype=np.int64)

        # See the note in _build: ACTIVE_INDEX must not end up as the active scalars
        points.set_active_scalars(None)

        return points

    def _validate_slice(self, slice_dim: str, slice_ind: int) -> int:
        """
        Check a slice dimension and index against the grid

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        int
            Grid dimension axis the slice dimension refers to
        """
        if slice_dim not in _SLICE_AXIS:
            raise TypeError(
                f'{slice_dim} slice dimension is not valid! Choose "i", "j", or "k"'
            )

        # Check slice_ind is within grid bounds along the slice dimension
        axis = _SLICE_AXIS[slice_dim]
        n_slice = self.egrid.dimension[axis]
        if not 0 <= slice_ind < n_slice:
            raise ValueError(
                f"slice_ind={slice_ind} is out of bounds for slice_dim='{slice_dim}'; "
                f"grid has {n_slice} cells along this axis (valid range: 0-{n_slice - 1})"
            )

        return axis

    def _read_corners(
        self, active_indices: Sequence[int] | None = None
    ) -> tuple[NDArray[np.float64], NDArray[np.int32], NDArray[np.int64]]:
        """
        Read the 8 corner points and grid indices of a set of active cells

        Parameters
        ----------
        active_indices : Sequence[int] | None, optional
            Active cells to read, by default None, which reads every active cell in the grid

        Returns
        -------
        corners : NDArray[np.float64]
            Corner coordinates in OPM corner order, with shape (ncells, 8, 3)
        ijk : NDArray[np.int32]
            Grid indices with shape (ncells, 3)
        active_index : NDArray[np.int64]
            The active_indices entry each surviving row came from (or, when active_indices is
            None, equivalently its own position in the whole grid's active-cell order)

        Notes
        -----
        Cells with a non-finite corner coordinate are dropped, since OPM reports pinched-out
        cells as NaN. This mirrors what opm_vis.utils.grid does for slices.

        float64 is deliberate rather than float32: field models are commonly in UTM
        coordinates, where float32 would resolve a northing of ~6.7e6 m to only half a metre
        and break exact-match point welding.

        OPM reports z as depth, increasing downwards, but VTK's own convention (and every
        camera pyvista sets up) assumes z points up. Negating z here, once, is what lets the
        rest of pvplot use pyvista's defaults instead of compensating for depth-down data at
        every camera and view. Axis labels put the sign back, see labels.axis_titles and
        GridPlotter.show_axes_grid.
        """
        indices = (
            range(self.egrid.active_cells) if active_indices is None else active_indices
        )
        ncells = len(indices)
        corners = np.empty((ncells, 8, 3), dtype=np.float64)
        ijk = np.empty((ncells, 3), dtype=np.int32)

        # EGrid exposes no bulk corner export, so this is one call per cell. Measured at a
        # few microseconds per cell, i.e. seconds for a million-cell model - which is exactly
        # why a caller wanting only a slice's cells should pass active_indices rather than
        # leave this reading (and discarding) the rest of the grid.
        for row, act in enumerate(indices):
            (
                corners[row, :, 0],
                corners[row, :, 1],
                corners[row, :, 2],
            ) = self.egrid.xyz_from_active_index(act, self.apply_mapaxes)
            ijk[row, :] = self.egrid.ijk_from_active_index(act)

        corners[:, :, 2] *= -1

        # Drop pinched-out cells, keeping the active index of everything that survives
        keep = np.isfinite(corners).all(axis=(1, 2))
        return corners[keep], ijk[keep], np.asarray(indices, dtype=np.int64)[keep]

    def _build(self) -> pv.UnstructuredGrid:
        """
        Build the hexahedral mesh of every active cell in the grid

        Returns
        -------
        pv.UnstructuredGrid
            Mesh with the ACTIVE_INDEX, "I", "J" and "K" cell arrays attached
        """
        return self._mesh_from_corners(*self._read_corners())

    def _mesh_from_corners(
        self,
        corners: NDArray[np.float64],
        ijk: NDArray[np.int32],
        active_index: NDArray[np.int64],
    ) -> pv.UnstructuredGrid:
        """
        Assemble a (optionally welded) hexahedral mesh from per-cell corner data

        Parameters
        ----------
        corners : NDArray[np.float64]
            Corner coordinates in OPM corner order, with shape (ncells, 8, 3), as returned by
            _read_corners
        ijk : NDArray[np.int32]
            Grid indices with shape (ncells, 3), as returned by _read_corners
        active_index : NDArray[np.int64]
            Active index of each cell, as returned by _read_corners

        Returns
        -------
        pv.UnstructuredGrid
            Mesh with the ACTIVE_INDEX, "I", "J" and "K" cell arrays attached

        Notes
        -----
        Shared by _build() (every active cell) and extract_slice()'s own fast path (one
        slice's cells only), so welding/cell-array bookkeeping stays identical either way.

        Welding merges the coincident corner points that neighbouring cells share, cutting
        the point count by roughly a factor of eight. The tolerance is exactly zero on
        purpose: corner-point grids are genuinely discontinuous across faults, and only
        bit-identical coordinates should ever be merged. Cell order is unaffected.
        """
        # Pick the corner permutation that gives outward-facing hexahedra for this grid
        order = _VTK_HEX_ORDER_MIRRORED if self._is_mirrored(corners) else _VTK_HEX_ORDER
        mesh = self._hexahedra(corners, order)

        # Cell arrays. ACTIVE_INDEX is what property data is looked up through; I/J/K make
        # slicing and thresholding on grid indices possible, and both survive extraction.
        # Attached before welding so they follow the cells regardless of what clean() does.
        mesh.cell_data[ACTIVE_INDEX] = active_index
        mesh.cell_data["I"] = ijk[:, 0]
        mesh.cell_data["J"] = ijk[:, 1]
        mesh.cell_data["K"] = ijk[:, 2]

        if self.weld:
            # clean() is typed generically over every PyVista dataset, so its declared return
            # type is wider than what it can actually produce here; see the note on
            # extract_slice for why the cast is safe. tolerance is int-typed upstream (its
            # unannotated default of 0 is what pyright infers from), so 0 rather than 0.0.
            mesh = cast(
                pv.UnstructuredGrid,
                mesh.clean(tolerance=0, produce_merge_map=False, average_point_data=False),
            )

        # Attaching cell data makes the first array active, which would leave PyVista
        # colouring the grid by ACTIVE_INDEX the moment it is added to a plotter. These are
        # bookkeeping arrays, never something to look at.
        mesh.set_active_scalars(None)

        return mesh

    @staticmethod
    def _is_mirrored(corners: NDArray[np.float64]) -> bool:
        """
        Check whether (i, j, k) is mirrored with respect to (x, y, z)

        Parameters
        ----------
        corners : NDArray[np.float64]
            Corner coordinates in OPM corner order, with shape (ncells, 8, 3)

        Returns
        -------
        bool
            True if _VTK_HEX_ORDER_MIRRORED should be used instead of _VTK_HEX_ORDER

        Notes
        -----
        Uses the sign of the scalar triple product of the i-, j- and k-edge vectors leaving
        corner 0, which is the signed volume of the cell taken as a parallelepiped. That sign
        is positive exactly when _VTK_HEX_ORDER yields outward-facing hexahedra, verified
        against a standard OPM grid with corners already carrying pvplot's z, which points up
        (see _read_corners), rather than OPM's own depth-positive-down z.

        A majority vote over all cells is used so that degenerate, zero-volume cells cannot
        decide the answer on their own.
        """
        edge_i = corners[:, 1] - corners[:, 0]
        edge_j = corners[:, 2] - corners[:, 0]
        edge_k = corners[:, 4] - corners[:, 0]
        triple = np.einsum("ij,ij->i", np.cross(edge_i, edge_j), edge_k)

        return bool(np.sign(triple).sum() < 0)

    @staticmethod
    def _hexahedra(
        corners: NDArray[np.float64], order: NDArray[np.int_]
    ) -> pv.UnstructuredGrid:
        """
        Assemble hexahedral cells from per-cell corner points

        Parameters
        ----------
        corners : NDArray[np.float64]
            Corner coordinates in OPM corner order, with shape (ncells, 8, 3)
        order : NDArray[np.int_]
            Permutation taking OPM corner order to VTK_HEXAHEDRON order

        Returns
        -------
        pv.UnstructuredGrid
            Mesh with ncells hexahedra and no cell data

        Notes
        -----
        Points are left duplicated, 8 per cell, so that cell c owns points 8c to 8c+7 and
        cell order follows the order of `corners` exactly. Welding them is a separate step.
        """
        ncells = corners.shape[0]
        points = corners[:, order, :].reshape(-1, 3)

        # VTK connectivity is a flat [npoints_of_cell, point ids...] per cell
        connectivity = np.hstack(
            (
                np.full((ncells, 1), 8, dtype=np.int64),
                np.arange(8 * ncells, dtype=np.int64).reshape(ncells, 8),
            )
        ).ravel()
        cell_types = np.full(ncells, pv.CellType.HEXAHEDRON, dtype=np.uint8)

        return pv.UnstructuredGrid(connectivity, cell_types, points)
