""" Hexahedral PyVista mesh built from an OPM EGRID file """
from __future__ import annotations

import warnings
from glob import glob
from typing import cast

import numpy as np
import pyvista as pv
from numpy.typing import NDArray
from opm.io.ecl import EGrid

from opm_vis.utils.grid import GridSlice3D

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
        """
        Boolean mask selecting the mesh cells that lie on one i-, j- or k-slice

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        NDArray[np.bool_]
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

        extract_cells() is typed generically over every PyVista dataset, so its declared
        return type is wider than what it can actually produce from a mesh that is already an
        UnstructuredGrid. The cast below reflects that narrower, verified invariant rather than
        working around a real ambiguity.
        """
        return cast(
            pv.UnstructuredGrid,
            self.mesh.extract_cells(self.slice_mask(slice_dim, slice_ind)),
        )

    def quad_slice(self, slice_dim: str, slice_ind: int) -> pv.PolyData:
        """
        Build one i-, j- or k-slice as flat quads, without building the full mesh

        Parameters
        ----------
        slice_dim : str
            'i', 'j', or 'k' slice of the 3D grid
        slice_ind : int
            Index of slice

        Returns
        -------
        pv.PolyData
            One quad per slice cell, carrying an ACTIVE_INDEX cell array

        Notes
        -----
        This is the cheap path for large grids: it touches only the cells on the slice rather
        than materialising every hexahedron in the model. The cost is that a quad has no
        volume, so thresholding, clipping and volume rendering need extract_slice instead.

        Reuses GridSlice3D from opm_vis.utils.grid, which already picks the four corners of
        the slice face out of the corner-point grid and drops pinched-out cells.
        """
        self._validate_slice(slice_dim, slice_ind)

        # (ncells, 4, 3) corner points, with the matching list of active indices
        slc = GridSlice3D(self.path, slice_dim, slice_ind)
        corners = slc.cell_corners()
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
        self,
    ) -> tuple[NDArray[np.float64], NDArray[np.int32], NDArray[np.int64]]:
        """
        Read the 8 corner points and grid indices of every active cell

        Returns
        -------
        corners : NDArray[np.float64]
            Corner coordinates in OPM corner order, with shape (ncells, 8, 3)
        ijk : NDArray[np.int32]
            Grid indices with shape (ncells, 3)
        active_index : NDArray[np.int64]
            Active index of each cell that was kept

        Notes
        -----
        Cells with a non-finite corner coordinate are dropped, since OPM reports pinched-out
        cells as NaN. This mirrors what opm_vis.utils.grid does for slices.

        float64 is deliberate rather than float32: field models are commonly in UTM
        coordinates, where float32 would resolve a northing of ~6.7e6 m to only half a metre
        and break exact-match point welding.
        """
        ncells = self.egrid.active_cells
        corners = np.empty((ncells, 8, 3), dtype=np.float64)
        ijk = np.empty((ncells, 3), dtype=np.int32)

        # EGrid exposes no bulk corner export, so this is one call per cell. Measured at a
        # few microseconds per cell, i.e. seconds for a million-cell model.
        for act in range(ncells):
            (
                corners[act, :, 0],
                corners[act, :, 1],
                corners[act, :, 2],
            ) = self.egrid.xyz_from_active_index(act)
            ijk[act, :] = self.egrid.ijk_from_active_index(act)

        # Drop pinched-out cells, keeping the active index of everything that survives
        keep = np.isfinite(corners).all(axis=(1, 2))
        return corners[keep], ijk[keep], np.flatnonzero(keep)

    def _build(self) -> pv.UnstructuredGrid:
        """
        Build the hexahedral mesh

        Returns
        -------
        pv.UnstructuredGrid
            Mesh with the ACTIVE_INDEX, "I", "J" and "K" cell arrays attached

        Notes
        -----
        Welding merges the coincident corner points that neighbouring cells share, cutting
        the point count by roughly a factor of eight. The tolerance is exactly zero on
        purpose: corner-point grids are genuinely discontinuous across faults, and only
        bit-identical coordinates should ever be merged. Cell order is unaffected.
        """
        corners, ijk, active_index = self._read_corners()

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
        against a standard OPM grid with z as depth increasing downwards.

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
