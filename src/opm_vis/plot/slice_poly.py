"""Module for generating slices for plotting"""
from abc import ABC, abstractmethod
from typing import Any, List, Union

from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from numpy.typing import NDArray

from opm_vis.utils.grid import GridSlice2D, GridSlice3D, _GridSlice
from opm_vis.utils.restart import RestartReader
from opm_vis.utils.static import InitReader


class _SlicePoly(_GridSlice, ABC):
    """
    Class for setting up a slice for 3D or 2D plot.

    Warning
    -------
    Do not instantiate!
    """

    def __init__(self, paths: List[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_dim : str
            Dimension to slice : i, j, or k
        slice_ind : int
            Index of slice
        """
        # Instantiate help classes
        _GridSlice.__init__(self, paths[0], slice_dim, slice_ind)
        self.init = InitReader(paths[0])
        self.restart = RestartReader(paths)

    def generate(
        self, keyword: str, rstep: int, **kwargs
    ) -> Union[PolyCollection, Poly3DCollection]:
        """
        Generate data from keyword at one report step

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step
        kwargs: optional
            Optional arguments passed to Poly3DCollection

        Returns
        -------
        polyc : Poly3DCollection
            Matplotlib polygons with data from keyword
        """
        # Get active indices
        act_ind = self.active_indices()

        # Read keyword
        data = self.restart.read(keyword, rstep, act_ind)

        # Generate 3D polygon collection
        polyc = self.generate_poly(data, **kwargs)

        # Return polygon collection
        return polyc

    @abstractmethod
    def generate_poly(
        self, data: NDArray[Any], **kwargs
    ) -> Union[PolyCollection, Poly3DCollection]:
        """Dummy class. See child class generate_poly methods"""

    def cell_corners_min(self):
        """
        Minimum values for slice

        Returns
        -------
        ndarray
            Min. x-, y-, and z- values
        """
        # Min values for each coordinate in slice
        return self.cell_corners().min(axis=(0, 1))

    def cell_corners_max(self):
        """
        Maximum values for slice

        Returns
        -------
        ndarray
            Max. x-, y-, and z- values
        """
        # Max values for each coordinate in slice
        return self.cell_corners().max(axis=(0, 1))


class SlicePoly3D(_SlicePoly, GridSlice3D):
    """
    Generate slice for 3D plotting. See parent classes for some method docs.
    """

    def __init__(self, paths: List[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes.

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_dim : str
            Dimension to slice : i, j, or k
        slice_ind : int
            Index of slice

        Notes
        -----
        We override GridSlice class in parent SlicePoly class
        """
        # Instantiate help classes
        super().__init__(paths, slice_dim, slice_ind)
        GridSlice3D.__init__(self, paths[0], slice_dim, slice_ind)

    def generate_poly(self, data: NDArray[Any], **kwargs) -> Poly3DCollection:
        """
        Generate 3D polygon collection

        Parameters
        ----------
        data : ndarray
            Face color data

        Returns
        -------
        Poly3DCollection
            Collection of slice polygons to plot
        """
        # Instantiate Poly3DCollection with cell corners and optional arguments
        polyc = Poly3DCollection(self.cell_corners(), **kwargs)

        # Insert data in polygon collection
        polyc.set_array(data)

        return polyc


class SlicePoly2D(_SlicePoly, GridSlice2D):
    """
    Subclass of SlicePoly for setting up a slice plot projected to 2D
    """

    def __init__(self, paths: List[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes.

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_dim : str
            Dimension to slice : i, j, or k
        slice_ind : int
            Index of slice

        Notes
        -----
        We override GridSlice class in parent SlicePoly class
        """
        # Instantiate help classes
        super().__init__(paths, slice_dim, slice_ind)
        GridSlice2D.__init__(self, paths[0], slice_dim, slice_ind)

    def generate_poly(self, data: NDArray[Any], **kwargs) -> PolyCollection:
        """
        Generate 2D polygon collection

        Parameters
        ----------
        data : ndarray
            Face color data

        Returns
        -------
        PolyCollection
            Collection of slice polygons to plot
        """
        # Instantiate PolyCollection with cell corners and optional arguments
        polyc = PolyCollection(self.cell_corners(), **kwargs)

        # Insert data in polygon collection
        polyc.set_array(data)

        return polyc
