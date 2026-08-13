"""Module for generating slices for plotting"""
from __future__ import annotations

from abc import ABC, abstractmethod
from copy import copy

import numpy as np
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from opm_vis.utils.calc import apply_slice_calc, resolve_calc_range
from opm_vis.utils.diff import compute_diff
from opm_vis.utils.grid import _SLICE_AXIS, GridSlice2D, GridSlice3D, _GridSlice, slice_range_layer_grid
from opm_vis.utils.restart import RestartReader, Wells
from opm_vis.utils.static import InitReader


class _SlicePoly(_GridSlice, ABC):
    """
    Class for setting up a slice for 3D or 2D plot.

    Warning
    -------
    Do not instantiate!
    """

    def __init__(self, paths: list[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_dim : str
            Dimension to slice : i, j, or k
        slice_ind : int
            Index of slice
        """
        # Instantiate help classes
        _GridSlice.__init__(self, paths[0], slice_dim, slice_ind)
        self.static = InitReader(paths[0])
        self.restart = RestartReader(paths)

        # Internal variables
        self.wells = []  # see Wells class

    def generate(
        self,
        keyword: str,
        rstep: int,
        *,
        diff_rstep: int | None = None,
        diff_kind: str = "plain",
        calc_kind: str | None = None,
        calc_count: int | None = None,
        **kwargs,
    ) -> PolyCollection | Poly3DCollection:
        """
        Generate data from keyword at one report step

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step
        diff_rstep : int | None, optional
            Use the difference from this report step instead of keyword's own values, by
            default None (the values themselves)
        diff_kind : str, optional
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given, by
            default "plain"
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS: aggregate keyword across a range of layers
            along this slice's own dimension, from slice_ind to the grid's last layer (or
            calc_count layers), instead of using this slice's own values, by default None
        calc_count : int | None, optional
            Limit calc_kind's aggregation to this many layers starting at slice_ind, by default
            None (continue to the grid's last layer). Only used when calc_kind is given.
        kwargs: optional
            Optional arguments passed to Poly3DCollection/PolyCollection

        Returns
        -------
        polyc : PolyCollection | Poly3DCollection
            Matplotlib polygons with data from keyword

        Notes
        -----
        calc_kind and diff_rstep combine: the calculator's aggregate is computed separately at
        rstep and at diff_rstep, and diff_rstep differences the two aggregates - "how much did
        the mean/sum change between these two report steps", not the mean/sum of the per-cell
        differences.
        """
        act_ind = self.active_indices()
        if calc_kind is not None:
            data = self._read_calc(keyword, rstep, calc_kind, calc_count)
            if diff_rstep is not None:
                reference = self._read_calc(keyword, diff_rstep, calc_kind, calc_count)
                data = compute_diff(data, reference, diff_kind)
        else:
            data = self._read_keyword(keyword, rstep, act_ind)
            if diff_rstep is not None:
                reference = self._read_keyword(keyword, diff_rstep, act_ind)
                data = compute_diff(data, reference, diff_kind)

        # Generate polygon collection
        polyc = self.generate_poly(**kwargs)

        # Insert data in polygon collection
        polyc.set_array(data)

        # Return polygon collection
        return polyc

    def _read_calc(self, keyword: str, rstep: int, kind: str, count: int | None):
        """
        Aggregate keyword across a range of layers along this slice's own dimension

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step
        kind : str
            One of opm_vis.utils.calc.CALC_KINDS
        count : int | None
            Limit the range to this many layers starting at slice_ind, or None to continue to
            the grid's last layer

        Returns
        -------
        ndarray
            One aggregated value per entry in active_indices(), in the same order

        Notes
        -----
        Only the active cells actually spanned by the layer range are read (one combined call
        to _read_keyword), not the whole grid.
        """
        n_slice = self.egrid.dimension[_SLICE_AXIS[self.slice_dim]]
        start, end = resolve_calc_range(self.slice_ind, n_slice, count)
        layer_grid = slice_range_layer_grid(self.egrid, self.slice_dim, start, end)

        flat = layer_grid.reshape(layer_grid.shape[0], -1)
        valid = np.unique(flat[flat >= 0])
        values = self._read_keyword(keyword, rstep, valid.tolist())
        lookup = np.full(self.egrid.active_cells, np.nan)
        lookup[valid] = values

        aggregated_full = apply_slice_calc(lookup, layer_grid, kind)
        return aggregated_full[self.act]

    def _read_keyword(self, keyword: str, rstep: int, act_ind: list[int]):
        """
        Read one keyword at one report step, restart files taking priority over .INIT

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step
        act_ind : list[int]
            Active indices to read, as returned by active_indices()

        Returns
        -------
        ndarray
            One value per entry in act_ind
        """
        if keyword in self.restart.available_keywords(rstep):
            return self.restart.read(keyword, rstep, act_ind)
        if keyword in [
            key
            for key in self.static.available_keywords()
            if key not in self.restart.available_keywords(rstep)
        ]:
            return self.static.read(keyword, act_ind)

        raise KeyError(f"{keyword} not in restart files or .INIT file!")

    def _filter_wells(self, paths: list[str]) -> None:
        """
        Filter wells that are present on slice; rest will be empty lists

        Parameters
        ----------
        paths : list[str]
            Path to restart files (passed to Wells initialization)
        """
        # Instantiate Wells class
        self.wells = Wells(paths)

        # Initialize new wells dictionary, with info that just exist on this slice. Slight change in
        # well info list compared to list in Wells; we change from i,j,k to active indices:
        # well_info = [act_ind_0, act_ind_1, ..., act_ind_end, status]
        for well in self.wells:
            for name, info in well.items():
                well_info = []
                # Append active cells if wells are present
                if self.slice_dim == "k" and self.slice_ind in info[2:-1]:
                    if (
                        self.egrid.active_index(info[0], info[1], self.slice_ind)
                        in self.active_indices()
                    ):
                        well_info.append(
                            self.egrid.active_index(info[0], info[1], self.slice_ind)
                        )
                elif (self.slice_dim == "i" and info[0] == self.slice_ind) or (
                    self.slice_dim == "j" and info[1] == self.slice_ind
                ):
                    for k in info[2:-1]:
                        if (
                            self.egrid.active_index(info[0], info[1], k)
                            in self.active_indices()
                        ):
                            well_info.append(
                                self.egrid.active_index(info[0], info[1], k)
                            )
                # If well info have been added to well_info list (meaning well exist in slice), we
                # add the well status (open/shut bool) as well
                if well_info:
                    well_info.append(info[-1])

                # Overwrite list for well with new info (or empty list if it's not present).
                well[name] = copy(well_info)

    @abstractmethod
    def generate_poly(self, **kwargs) -> PolyCollection | Poly3DCollection:
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

    def __init__(self, paths: list[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes.

        Parameters
        ----------
        paths : list[str]
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

        # Setup wells
        self._filter_wells(paths)

    def generate_poly(self, **kwargs) -> Poly3DCollection:
        """
        Generate 3D polygon collection

        Parameters
        ----------
        kwargs: optional
            Optional arguments passed to Poly3DCollection


        Returns
        -------
        Poly3DCollection
            Collection of slice polygons to plot
        """
        # Instantiate Poly3DCollection with cell corners and optional arguments
        return Poly3DCollection(self.cell_corners(), **kwargs)


class SlicePoly2D(_SlicePoly, GridSlice2D):
    """
    Subclass of SlicePoly for setting up a slice plot projected to 2D
    """

    def __init__(self, paths: list[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize slice by instantiating all helper classes.

        Parameters
        ----------
        paths : list[str]
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

        # Setup wells
        self._filter_wells(paths)

    def generate_poly(self, **kwargs) -> PolyCollection:
        """
        Generate 2D polygon collection

        Parameters
        ----------
        kwargs: optional
            Optional arguments passed to PolyCollection

        Returns
        -------
        PolyCollection
            Collection of slice polygons to plot
        """
        # Instantiate PolyCollection with cell corners and optional arguments
        return PolyCollection(self.cell_corners(), **kwargs)
