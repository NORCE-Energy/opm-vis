"""Module for plotting/gif-generation of slices"""
from functools import partial
from typing import List

from matplotlib import animation
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from opm_vis.utils.grid import Grid
from opm_vis.utils.restart import Report, RestartReader, Wells
from opm_vis.utils.static import InitReader


class Slice3DCollection:
    """
    Class for setting up a figure/axes, gathering collections of 3D slices, and the actual
    plotting/gif generation
    """

    def __init__(self, slice_coll: List["Slice3D"]):
        """
        Initialize class by setting up figure/axes.

        Parameters
        ----------
        slice_coll : Slice3D
            List of Slice3D objects
        """
        # Initialize matplotlib figure
        self.fig = plt.figure()
        self.ax_ = self.fig.add_subplot(projection="3d")

        # Internalize input
        self.slice_coll = slice_coll

        # Internal variables
        self.anim = None

    def set_labels(self):
        """Set labels to Easting, Northing, and depth"""
        # Set defaults
        self.ax_.set_xlabel("E(x) [m]")
        self.ax_.set_ylabel("N(y) [m]")
        self.ax_.set_zlabel("Depth(z) [m]")

    def add_collection(self, polyc):
        """
        Alias to axes.add_collection in matplotlib

        Parameters
        ----------
        polyc : Poly3DCollection
            Collection of polygons for a slice
        """
        # Check if input is correct type
        if not isinstance(polyc, Poly3DCollection):
            raise TypeError(
                f"polyc is not a Matplotlib Poly3DCollection, but has type {type(polyc)}"
            )

        # Add polygon collection to matplotlib axes
        self.ax_.add_collection(polyc)

    def set_lims(self, min_coll, max_coll):
        """
        Set x-, y-, and z-limits such that all slices are visible

        Parameters
        ----------
        min_coll : ndarray
            Minimum coordinates for each slice
        max_coll : ndarray
            Minimum coordinates for each slice
        """
        # Use matplotlib autoscaling
        self.ax_.set_xlim(min_coll[:, 0].min(), max_coll[:, 0].max())
        self.ax_.set_ylim(min_coll[:, 1].min(), max_coll[:, 1].max())
        self.ax_.set_zlim(min_coll[:, 2].min(), max_coll[:, 2].max())

    def plot(self, rstep, keyword, **kwargs):
        """
        Plot keyword at one report step.

        Parameters
        ----------
        rstep : int
            Report step
        keyword : str
            OPM keyword to plot

        Notes
        -----
        Use show or save_plot to show plot on screen or save to file.
        """
        # Generate data for each slice and add to axes collection
        min_coll = np.zeros((len(self.slice_coll), 3))
        max_coll = np.zeros((len(self.slice_coll), 3))
        for i, slc in enumerate(self.slice_coll):
            # Generated data comes in form of a Matplotlib Poly3DCollection
            polyc = slc.generate(keyword, rstep, **kwargs)

            # Add polyc to axes collection
            self.add_collection(polyc)

            # Find min/max coordinates for slices
            min_coll[i, :] = slc.min()
            max_coll[i, :] = slc.max()

        # Set labels
        self.set_labels()

        # Set limits
        self.set_lims(min_coll, max_coll)

        # Invert z-axis
        self.ax_.invert_zaxis()

    def gif(self, keyword, **kwargs):
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
        rsteps = self.slice_coll[0].report.report_steps()

        # Setup plot function to fit with FuncAnimation
        plot_func = partial(self.plot, keyword=keyword, **kwargs)

        # Set up Matplotlib animation
        self.anim = animation.FuncAnimation(self.fig, plot_func, frames=rsteps)

    def show(self):
        """Show figure on screen"""
        plt.show()
        plt.close("all")


class Slice3D:
    """
    Class for setting up a slice for 3D plot.
    """

    def __init__(self, path, slice_dim, slice_ind, restart_paths=None):
        """
        Initialize slice by instantiating all helper classes

        Parameters
        ----------
        path : str
            Main folder
        slice_dim : str
            Dimension to slice
        slice_ind : int
            Index to slice through
        restart_paths : list, optional
            Folder with files from restart runs, by default None
        """
        # Instantiate static parameters help classes
        self.grid = Grid(path, slice_ind, slice_dim)
        self.init = InitReader(path)

        # Instantiate restart file help classes
        if restart_paths is not None:
            paths = [path] + restart_paths
        else:
            paths = [path]
        self.restart = RestartReader(paths)
        self.report = Report(paths)
        self.wells = Wells(paths)

    def generate(self, keyword, rstep, **kwargs):
        """
        Generate data from keyword at one report step

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step

        Returns
        -------
        polyc : Poly3DCollection
            Matplotlib polygons with data from keyword
        """
        # Get active indices
        act_ind = self.grid.active_indices()

        # Read keyword
        data = self.restart.read(keyword, rstep, act_ind)

        # Generate 3D polygon collection
        polyc = Poly3DCollection(self.grid.cell_corners(), **kwargs)

        # Insert data in polygon collection
        polyc.set_array(data)

        # Return polygon collection
        return polyc

    def min(self):
        """
        Minimum values for slice

        Returns
        -------
        ndarray
            Min. x-, y-, and z- values
        """
        # Min values for each coordinate in slice
        return self.grid.cell_corners().min(axis=(0, 1))

    def max(self):
        """
        Maximum values for slice

        Returns
        -------
        ndarray
            Max. x-, y-, and z- values
        """
        # Max values for each coordinate in slice
        return self.grid.cell_corners().max(axis=(0, 1))
