""" Grid methods for xyz plots """
import warnings
from abc import ABC, abstractmethod
from glob import glob
from typing import Any

import numpy as np
from numpy.typing import NDArray
from opm.io.ecl import EGrid

# Global indices for slice quadrilateral
_INDICES = {
    "i": [0, 2, 6, 4],
    "j": [0, 1, 5, 4],
    "k": [0, 2, 3, 1],
}

# Grid dimension axis (0=x/i, 1=y/j, 2=z/k) corresponding to each slice dimension
_SLICE_AXIS = {"i": 0, "j": 1, "k": 2}

# pylint: disable=unsubscriptable-object,too-many-instance-attributes
# EGrid is a pybind class, so until stubs (.pyi files) are made, pylint unsubscriptable-object
# errors will pop up.
class _GridSlice(ABC):
    """
    Setup grid from OPM EGRID file. Actual calculations in child classes.
    """

    def __init__(self, path: str, slice_dim: str, slice_ind: int) -> None:
        """
        Initialize EGrid class from input path

        Parameters
        ----------
        path : str
            Path to .EGRID file
        slice_dim : str
            'i', 'j, or 'k' slice of 3D grid
        slice_ind : int
            Index of slice
        """
        # Internalize input
        self.slice_dim = slice_dim
        self.slice_ind = slice_ind

        # Internal variables
        self.act = []
        self.corn = np.empty(0)
        self.cent = np.empty(0)

        # Instantiate Egrid class
        egrid_files = glob(path + "*.EGRID")
        if egrid_files:
            if len(egrid_files) > 1:
                warnings.warn(
                    f"Multiple .EGRID files in {path}. Importing {egrid_files[0]}."
                )
            self.egrid = EGrid(egrid_files[0])
        else:
            raise FileNotFoundError(f"No .EGRID file found in {path}!")

        # Grid slice axis indices and dimension
        if slice_dim == "i":
            self.slice_axis = [1, 2]
        elif slice_dim == "j":
            self.slice_axis = [0, 2]
        elif slice_dim == "k":
            self.slice_axis = [0, 1]
        else:
            raise TypeError(
                f'{slice_dim} slice dimension is not valid! Choose "i", "j", or "k"'
            )
        self.nx1 = self.egrid.dimension[self.slice_axis[0]]
        self.nx2 = self.egrid.dimension[self.slice_axis[1]]

        # Check slice_ind is within grid bounds along the slice dimension
        n_slice = self.egrid.dimension[_SLICE_AXIS[slice_dim]]
        if not 0 <= slice_ind < n_slice:
            raise ValueError(
                f"slice_ind={slice_ind} is out of bounds for slice_dim='{slice_dim}'; "
                f"grid has {n_slice} cells along this axis (valid range: 0-{n_slice - 1})"
            )

        # Check (i, j, k) coord. system is aligned with (x, y, z) coord. system
        self.aligned_grid = self.is_aligned()

    def _active_index_from_end(self, i: int, j: int, k: int, axis: int, origin_axis: int) -> int:
        """
        Search for the first active cell along ``axis``, starting from the far end of the grid
        and moving inward towards (but not past) ``origin_axis``.

        Returns
        -------
        int
            Active index of the first active cell found, or -1 if none exists between the far
            end and the origin (inclusive).
        """
        idx = [i, j, k]
        dim_size = self.egrid.dimension[axis]
        for candidate in range(dim_size - 1, origin_axis - 1, -1):
            idx[axis] = candidate
            act = self.egrid.active_index(*idx)
            if act >= 0:
                return act
        return -1

    # pylint: disable=too-many-locals
    def is_aligned(self) -> bool:
        """
        Check if (i, j, k) coordinate system is aligned with (x, y, z) coordinate system

        Notes
        -----
        The grid alignment is based on the sign of the volume a parallelepiped taken out from the
        grid. Volume is calculated with scalar triple product of the vectors making up the
        parallelepiped.
        """
        # Loop until we successful at making a parallelepiped from the grid. At each round of the
        # loop we try to make vectors from origin that are at least larger than one grid cell in
        # each direction. If this is not successful we change the origin to next active cell and
        # start over. It is not possible at all to make parallelepiped within 10 iterations, we
        # assume righthand grid and raise a warning
        success = False
        origin = 0
        max_iteration = 10
        iteration = 1
        aligned = False
        while success is False and iteration < max_iteration:
            # Origin of the parallelepiped in the active grid, since inactive cells can be
            # unpredictable (moved around, squeezed, etc)
            x_1, y_1, z_1 = self.egrid.xyz_from_active_index(origin)
            i, j, k = self.egrid.ijk_from_active_index(origin)

            # Search for an active cell by increasing i-, j-, and k-index, without searching past
            # the origin itself
            act_i = self._active_index_from_end(i, j, k, axis=0, origin_axis=i)
            act_j = self._active_index_from_end(i, j, k, axis=1, origin_axis=j)
            act_k = self._active_index_from_end(i, j, k, axis=2, origin_axis=k)

            # If no active cell was found along one of the axes, this origin cannot be used to
            # build a parallelepiped; move on to the next origin
            if act_i < 0 or act_j < 0 or act_k < 0:
                iteration += 1
                origin += 1
                continue

            x_2, y_2, _ = self.egrid.xyz_from_active_index(act_i)
            x_3, y_3, _ = self.egrid.xyz_from_active_index(act_j)
            _, _, z_2 = self.egrid.xyz_from_active_index(act_k)

            # Vectors making up the parallelepiped
            v_1 = np.array([x_2[0] - x_1[0], y_2[0] - y_1[0], 0])
            v_2 = np.array([x_3[0] - x_1[0], y_3[0] - y_1[0], 0])
            v_3 = np.array([0, 0, z_2[0] - z_1[0]])

            # Check if length of any of the vectors are zero (i.e coordinates are from the same
            # cell)
            if (
                np.linalg.norm(v_1) == 0
                or np.linalg.norm(v_2) == 0
                or np.linalg.norm(v_3) == 0
            ):
                # Increase iteration counter and origin active index
                iteration += 1
                origin += 1

            # Check if grid is aligned by checking sign of parallelepiped volume
            else:
                aligned = np.dot(np.cross(v_1, v_2), v_3) < 0
                success = True

        # If max iterations is reached, raise a warning
        if success is False and iteration >= max_iteration:
            warnings.warn(
                "Testing for grid alignment was not successful. Aligned grid assumed!"
            )

        return aligned

    def _compute_active_indices(self) -> None:
        """
        Get active indices for a slice
        """
        # Loop over slice grid dimension
        for ind_1 in range(self.nx1):
            for ind_2 in range(self.nx2):
                # Arrange indices input to EGrid according to the slice dimension
                if self.slice_dim == "i":
                    act_index = self.egrid.active_index(self.slice_ind, ind_1, ind_2)
                elif self.slice_dim == "j":
                    act_index = self.egrid.active_index(ind_1, self.slice_ind, ind_2)
                else:
                    act_index = self.egrid.active_index(ind_1, ind_2, self.slice_ind)

                # Check if active index at (i,j,k) is an active cell, if so add to list
                if act_index >= 0:
                    self.act.append(act_index)

    def _cell_corners(self) -> None:
        """
        Pick out cell corners for slice from corner point grid
        """
        # Get indices for slice dimension
        local_ind = _INDICES[self.slice_dim]

        # Cell corners stored in 2D array
        xcorn = np.zeros((len(self.act), 4))
        ycorn = np.zeros((len(self.act), 4))
        zcorn = np.zeros((len(self.act), 4))

        # Loop over active cells and get coordinates for slice
        for i, act in enumerate(self.act):
            # All 8 corner coordinates of the cell
            cell_corn_x, cell_corn_y, cell_corn_z = self.egrid.xyz_from_active_index(
                act
            )

            # Pick out local indices relevant for slice
            xcorn[i, :] = [cell_corn_x[ind] for ind in local_ind]
            ycorn[i, :] = [cell_corn_y[ind] for ind in local_ind]
            zcorn[i, :] = [cell_corn_z[ind] for ind in local_ind]

        # If any rows contain np.nan, we remove those rows
        nan_row = (
            np.isnan(xcorn).any(axis=1)
            | np.isnan(ycorn).any(axis=1)
            | np.isnan(zcorn).any(axis=1)
        )
        xcorn = xcorn[~nan_row]
        ycorn = ycorn[~nan_row]
        zcorn = zcorn[~nan_row]

        # Remove cells from list of active indices as well
        self.act = [elem for elem, is_nan in zip(self.act, nan_row) if not is_nan]

        # Gather corner points in array with shape (ncells, 4, 3)
        self.corn = np.stack((xcorn, ycorn, zcorn), axis=-1)

    def _cell_centers(self) -> None:
        """
        Calculate cell centers of slice (i.e., cell face centers)
        """
        # Check if corner points have been calculated
        if self.corn.size == 0:
            raise ValueError(
                "Corner points have not been calculated before cell centers for slice!"
            )

        # Use average of cell corners as approximation for cell center
        self.cent = np.mean(self.corn, axis=1)

    def active_indices(self) -> list[int]:
        """
        Return active indices

        Returns
        -------
        list[int]
            List of active cells for slice
        """
        return self.act

    @abstractmethod
    def cell_corners(self) -> NDArray[Any]:
        """
        Return cell corners of slice

        Returns
        -------
        NDArray[Any]
            Cell corners with shape = (ncells, 4, *) with * = 2 for 2D and 3 for 3D
        """

    @abstractmethod
    def cell_centers(self) -> NDArray[Any]:
        """
        Return cell centers

        Returns
        -------
        NDArray[Any]
            Cell centers with shape = (ncells, *) with * = 2 for 2D and 3 for 3D
        """


class GridSlice3D(_GridSlice):
    """
    Grid calculations for slice with 3D coordinates.
    """

    def __init__(self, path: str, slice_dim: str, slice_ind: int) -> None:
        super().__init__(path, slice_dim, slice_ind)
        # Active indices for slice
        self._compute_active_indices()

        # Cell corner and centroid calculation
        self._cell_corners()
        self._cell_centers()

    def cell_corners(self) -> NDArray[Any]:
        """
        Return cell corners of slice

        Returns
        -------
        NDArray[Any]
            Cell corners with shape = (ncells, 4, 3)
        """
        return self.corn

    def cell_centers(self) -> NDArray[Any]:
        """
        Return cell centers

        Returns
        -------
        NDArray[Any]
            Cell centers with shape = (ncells, 3)
        """
        return self.cent


class GridSlice2D(GridSlice3D):
    """
    Subclass of GridSlice3D for 2D projection of slice down to the slice dimension. In practice,
    this means that ignore slice dimension from the 3D slice. Useful for, e.g., plotting 2D view of
    slice (similar to pcolor or pcolormesh in Matplotlib).
    """

    def cell_corners(self) -> NDArray[Any]:
        """
        Return cell corners of slice

        Returns
        -------
        NDArray[Any]
            Cell corners with shape = (ncells, 4, 2)
        """
        delete_axis = [ind for ind in [0, 1, 2] if ind not in self.slice_axis][0]
        return np.delete(self.corn, delete_axis, axis=2)

    def cell_centers(self) -> NDArray[Any]:
        """
        Return cell centers

        Returns
        -------
        NDArray[Any]
            Cell centers with shape = (ncells, 2)
        """
        delete_axis = [ind for ind in [0, 1, 2] if ind not in self.slice_axis][0]
        return np.delete(self.cent, delete_axis, axis=1)
