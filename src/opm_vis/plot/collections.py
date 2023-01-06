"""Plot collection of slices"""
from functools import partial
from typing import List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from opm_vis.plot.slice_poly import SlicePoly2D, SlicePoly3D
from opm_vis.utils.restart import Report, Wells


class _SlicePolyCollection:
    """
    Parent class for setting up a figure/axes, gathering collections of slices, and the actual
    plotting/gif generation
    """

    def __init__(
        self,
        paths: List[str],
        fig: Figure,
        ax_: plt.Axes,
        slice_coll: Union[List[SlicePoly3D], List[SlicePoly2D]],
    ) -> None:
        """
        Initialize class by setting up figure and instantiate helper classes.

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        """
        # Internalize input
        self.fig = fig
        self.ax_ = ax_
        self.slice_coll = slice_coll

        # Instantiate report and well classes
        self.report = Report(paths)
        self.wells = Wells(paths)

        # Internal variables
        self.anim = None

    def set_title(self, rstep: int, addition: Optional[str] = None) -> None:
        """
        Add title to figure

        Parameters
        ----------
        rstep : int
            Report step
        addition : Optional[str], optional
            Adding string to end of title, by default None
        """
        # Report date for title
        rdate = self.report.report_date(rstep)

        # Title
        title = rdate.strftime("%d.%m.%Y")

        # Add string to end
        if addition is not None:
            title += addition

        # Add title to figure
        self.fig.suptitle(title)

    def add_collection(self, polyc: Union[Poly3DCollection, PolyCollection]) -> None:
        """
        Alias to axes.add_collection in matplotlib

        Parameters
        ----------
        polyc : Poly3DCollection
            Collection of polygons for a slice
        """
        # Check if input is correct type
        if not isinstance(polyc, Poly3DCollection) and not isinstance(
            polyc, PolyCollection
        ):
            raise TypeError(
                f"polyc is not a Matplotlib Poly3DCollection nor PolyCollection,"
                f" but has type {type(polyc)}"
            )

        # Add polygon collection to matplotlib axes
        self.ax_.add_collection(polyc)

    def plot(self, rstep: int, keyword: str, **kwargs) -> None:
        """
        Plot keyword at one report step.

        Parameters
        ----------
        rstep : int
            Report step
        keyword : str
            OPM keyword to plot
        kwargs: optional
            Optional arguments passed to Poly3DCollection

        Notes
        -----
        Use show or save_plot to show plot on screen or save to file.
        """
        # Generate data for each slice and add to axes collection
        for slc in self.slice_coll:
            # Generated data comes in form of a Matplotlib Poly3DCollection
            polyc = slc.generate(keyword, rstep, **kwargs)

            # Add polyc to axes collection
            self.add_collection(polyc)

        # Set title
        self.set_title(rstep)

    def gif(self, keyword: str, **kwargs) -> None:
        """
        Generate gif

        Parameters
        ----------
        keyword : str
            OPM keyword to plot

        Notes
        -----
        Use show or save_gif to show gif on screen or save to file.
        """
        # All report steps
        rsteps = self.report.report_steps()

        # Setup plot function to fit with FuncAnimation
        plot_func = partial(self.plot, keyword=keyword, **kwargs)

        # Set up Matplotlib animation
        self.anim = animation.FuncAnimation(self.fig, plot_func, frames=rsteps)

    def show(self) -> None:
        """Show figure on screen"""
        plt.show()
        plt.close("all")


class SlicePoly3DCollection(_SlicePolyCollection):
    """
    Class for plotting collection of slices in 3D view
    """

    def __init__(self, paths: List[str], slice_info: List[Tuple[str, int]]) -> None:
        """
        Initialize class by setting up figure/axes.

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_info : List[Tuple[str, int]]
            Info to generate slices: [(dimension=i, j, or k, index)]
        """
        # Generate collection of slices
        slice_coll = [SlicePoly3D(paths, dim, ind) for dim, ind in slice_info]

        # Setup matplotlib figure
        fig = plt.figure()
        ax_ = fig.add_subplot(projection="3d")
        ax_.view_init(elev=30, azim=60)

        # Init parent class
        super().__init__(paths, fig, ax_, slice_coll)

        # Set labels
        self.set_labels()

        # Set limits
        self.set_lims()

        # Invert z-axis
        self.ax_.invert_zaxis()

    def set_labels(self) -> None:
        """Set labels to Easting, Northing, and depth"""
        # Set labels
        self.ax_.set_xlabel("E(x) [m]")
        self.ax_.set_ylabel("N(y) [m]")
        self.ax_.set_zlabel("Depth(z) [m]")

    def set_lims(self) -> None:
        """
        Set x-, y-, and z-limits such that all slices are visible
        """
        # Find min/max values over all slices
        min_coll = np.zeros((len(self.slice_coll), 3))
        max_coll = np.zeros((len(self.slice_coll), 3))
        for i, slc in enumerate(self.slice_coll):
            min_coll[i, :] = slc.cell_corners_min()
            max_coll[i, :] = slc.cell_corners_max()

        # Set limits
        self.ax_.set_xlim(min_coll[:, 0].min(), max_coll[:, 0].max())
        self.ax_.set_ylim(min_coll[:, 1].min(), max_coll[:, 1].max())
        self.ax_.set_zlim(min_coll[:, 2].min(), max_coll[:, 2].max())


class SlicePoly2DCollection(_SlicePolyCollection):
    """
    Class for plotting slice in 2D view thus, not a collection per se
    """

    def __init__(self, paths: List[str], slice_dim: str, slice_ind: int) -> None:
        """
        Initialize class by setting up figure/axes.

        Parameters
        ----------
        paths : List[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_info : List[Tuple[str, int]]
            Info to generate slices: [(dimension=i, j, or k, index)]
        """
        # Generate 2D slice and put in a list to conform with parent class methods
        slice_coll = [SlicePoly2D(paths, slice_dim, slice_ind)]

        # Setup matplotlib figure
        fig = plt.figure()
        ax_ = fig.add_subplot()

        # Init parent class
        super().__init__(paths, fig, ax_, slice_coll)

        # Set labels
        self.set_labels()

        # Set limits
        self.set_lims()

        # Invert axis as needed
        if self.slice_coll[0].slice_dim in ["i", "j"]:
            self.ax_.invert_yaxis()

    def set_labels(self) -> None:
        """Set labels according to slice dimension"""
        if self.slice_coll[0].slice_dim == "i":
            xlabel = "N(y) [m]"
            ylabel = "Depth [m]"
        elif self.slice_coll[0].slice_dim == "j":
            xlabel = "E(x) [m]"
            ylabel = "Depth [m]"
        else:
            xlabel = "E(x) [m]"
            ylabel = "N(y) [m]"

        # Set labels
        self.ax_.set_xlabel(xlabel)
        self.ax_.set_ylabel(ylabel)

    def set_lims(self) -> None:
        """
        Set x- and y-limits such that slice is covered
        """
        self.ax_.set_xlim(
            self.slice_coll[0].cell_corners_min()[0],
            self.slice_coll[0].cell_corners_max()[0],
        )
        self.ax_.set_ylim(
            self.slice_coll[0].cell_corners_min()[1],
            self.slice_coll[0].cell_corners_max()[1],
        )
