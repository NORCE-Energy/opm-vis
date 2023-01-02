""" Grid methods for xyz plots """
import warnings

import numpy as np
from opm.io.ecl import EGrid


# Global indices for slice quadrilateral
_INDICES = {
    "i": [0, 2, 6, 4],
    "j": [0, 1, 5, 4],
    "k": [0, 2, 3, 1],
}

# pylint: disable=unsubscriptable-object,too-many-instance-attributes
# EGrid is a pybind class, so until stubs (.pyi files) are made, pylint unsubscriptable-object
# errors will pop up.
class Grid:
    """
    Grid calculations from OPM EGRID file.
    """

    def __init__(self, path, slice_ind, slice_dim):
        """
        Initialize EGrid class from input path

        Parameters
        ----------
        path : str
            Path to .EGRID file
        grid_slice : str
            'i', 'j, or 'k' slice of 3D grid
        """
        # Internalize input
        self.slice_dim = slice_dim
        self.slice_ind = slice_ind

        # Initialize internal variables
        self.local_cell_ind = None
        self.corn = None
        self.cent = None

        # Instantiate Egrid class
        self.egrid = EGrid(path)

        # Grid dimensions
        if slice_dim == "i":
            self.nx1 = self.egrid.dimension[1]
            self.nx2 = self.egrid.dimension[2]
        elif slice_dim == "j":
            self.nx1 = self.egrid.dimension[0]
            self.nx2 = self.egrid.dimension[2]
        elif slice_dim == "k":
            self.nx1 = self.egrid.dimension[0]
            self.nx2 = self.egrid.dimension[1]

        # Check (i, j, k) coord. system is aligned with (x, y, z) coord. system
        self.aligned_grid = self.is_aligned()

        # Active indices for slice
        self.act = self._active_indices()
        self.nact = len(self.act)

        # Cell corner and centroid calculation
        self._cell_corners()
        self._cell_centers()

    # pylint: disable=too-many-locals
    def is_aligned(self):
        """
        Check if (i, j, k) coordinate system is aligned with (x, y, z) coordinate system

        Notes
        -----
        The grid alignment is based on the sign of the volume a parallelepiped taken out from the
        grid. Volume is calculated with scalar triple product of the vectors making up the
        parallelepiped.
        """
        # Dimension of the grid
        n_x = self.egrid.dimension[0]
        n_y = self.egrid.dimension[1]
        n_z = self.egrid.dimension[2]

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

            # Coordinates by inceasing i-index
            search = 1
            act = self.egrid.active_index(n_x - search, j, k)
            while act < 0:
                search += 1
                act = self.egrid.active_index(n_x - search, j, k)
            x_2, y_2, _ = self.egrid.xyz_from_active_index(act)

            # Coordinates by inceasing j-index
            search = 1
            act = self.egrid.active_index(i, n_y - search, k)
            while act < 0:
                search += 1
                act = self.egrid.active_index(i, n_y - search, k)
            x_3, y_3, _ = self.egrid.xyz_from_active_index(act)

            # Coordinates by inceasing k-index
            search = 1
            act = self.egrid.active_index(i, j, n_z - search)
            while act < 0:
                search += 1
                act = self.egrid.active_index(i, j, n_z - search)
            _, _, z_2 = self.egrid.xyz_from_active_index(act)

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

    def _active_indices(self):
        """
        Get active indices for a slice

        Returns
        -------
        List of active indices for grid slice
        """
        # Initialize active indices list
        act = []

        # Loop over slice grid dimension
        for ind_1 in range(self.nx1):
            for ind_2 in range(self.nx2):
                # Arrange indices input to EGrid according to the slice dimension
                if self.slice_dim == "i":
                    act_index = self.egrid.active_index(self.slice_ind, ind_1, ind_2)
                elif self.slice_dim == "j":
                    act_index = self.egrid.active_index(ind_1, self.slice_ind, ind_2)
                elif self.slice_dim == "k":
                    act_index = self.egrid.active_index(ind_1, ind_2, self.slice_ind)
                else:
                    raise TypeError(
                        f'{self.slice_dim} slice dimension is not valid! Choose "i", "j", or "k"'
                    )

                # Check if active index at (i,j,k) is an active cell, if so add to list
                if act_index >= 0:
                    act.append(act_index)

        return act

    def _cell_corners(self):
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
        ind_nan_x = np.unique(np.where(np.isnan(xcorn))[0])
        ind_nan_y = np.unique(np.where(np.isnan(ycorn))[0])
        ind_nan_z = np.unique(np.where(np.isnan(zcorn))[0])
        ind_nan = np.unique(np.hstack((ind_nan_x, ind_nan_y, ind_nan_z)))

        xcorn = np.delete(xcorn, ind_nan, axis=0)
        ycorn = np.delete(ycorn, ind_nan, axis=0)
        zcorn = np.delete(zcorn, ind_nan, axis=0)

        # Remove cells from list of active indices as well
        self.act = [elem for i, elem in enumerate(self.act) if i not in ind_nan]

        # Gather corner points in array with shape (ncells, 4, 3)
        self.corn = np.stack((xcorn, ycorn, zcorn), axis=-1)

    def _cell_centers(self):
        """
        Calculate cell centers of slice (i.e., cell face centers)
        """
        # Check if corner points have been calculated
        if self.corn is None:
            raise ValueError(
                "Corner points have not been calculated before cell centers for slice!"
            )

        # Use average of cell corners as approximation for cell center
        self.cent = np.mean(self.corn, axis=1)

    def cell_corners(self):
        """Return cell corners"""
        return self.corn

    def cell_centers(self):
        """Return cell centers"""
        return self.cent

    def active_indices(self):
        """Return active indices"""
        return self.act
