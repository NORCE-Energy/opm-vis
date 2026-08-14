"""Plot collection of slices"""
from __future__ import annotations

import datetime as dt
import warnings
from collections.abc import Sequence
from functools import partial
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from opm_vis.plot.slice_poly import SlicePoly2D, SlicePoly3D
from opm_vis.utils.calc import calc_label
from opm_vis.utils.diff import diff_label
from opm_vis.utils.restart import Report
from opm_vis.utils.units import Label

# An axis is switched from metres to km once its own span exceeds this, to keep tick labels
# on a wide field readable. opm_vis.plot hard-codes metres for every case regardless of its
# own unit convention (see set_labels below), so unlike opm_vis.pvplot this needs no check of
# what unit the case is actually in.
_KM_AXIS_SPAN_M = 1000.0


def _km_axis_label(name: str, span: float) -> str:
    """
    Axis title, switched to km once its span exceeds _KM_AXIS_SPAN_M

    Parameters
    ----------
    name : str
        Axis name, e.g. "E(x)"
    span : float
        Axis extent in metres (max - min)

    Returns
    -------
    str
        e.g. "E(x) [m]", or "E(x) [km]" once span is wide enough
    """
    return f"{name} [km]" if abs(span) > _KM_AXIS_SPAN_M else f"{name} [m]"


def _km_tick_formatter(value: float, _pos: int) -> str:
    """
    Format one tick value in km, for FuncFormatter

    Parameters
    ----------
    value : float
        Tick value, in the axis' own metres
    _pos : int
        Tick position; part of FuncFormatter's signature, unused here

    Returns
    -------
    str
        value/1000 to three decimals - metre resolution, since a km-scaled axis is often only
        one or two decimals wide otherwise (e.g. a 1200 m span becomes 1.2 - a single decimal
        would round every tick to the same-looking label)
    """
    return f"{value / 1000:.3f}"


def _use_km_ticks_if_wide(axis, span: float) -> None:
    """
    Switch one matplotlib axis to km-scaled tick labels once its span is wide enough

    Parameters
    ----------
    axis : matplotlib.axis.Axis
        Axis to format, e.g. ax_.xaxis
    span : float
        Axis extent in metres (max - min)
    """
    if abs(span) > _KM_AXIS_SPAN_M:
        axis.set_major_formatter(FuncFormatter(_km_tick_formatter))


# pylint: disable=too-many-instance-attributes
class _SlicePolyCollection:
    """
    Parent class for setting up a figure/axes, gathering collections of slices, and the actual
    plotting/animation generation
    """

    def __init__(
        self,
        paths: list[str],
        fig: Figure,
        ax_: plt.Axes,
        slice_coll: list[SlicePoly3D] | list[SlicePoly2D],
    ) -> None:
        """
        Initialize class by setting up figure and instantiate helper classes.

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        fig : plt.Figure
            Figure object
        ax_ : plt.Axes
            Axes insert slices in
        silce_coll : list
            List of SlicePoly3D/SlicePoly2D objects to use in plotting
        """
        # Internalize input
        self.fig = fig
        self.ax_ = ax_
        self.slice_coll = slice_coll
        self.paths = paths

        # Instantiate Report class
        self.report = Report(paths)

        # Instantiate Label class with correct unit_convention
        unit_convention = self.slice_coll[0].restart.unit_convention()
        self.label = Label(unit_convention)

        # Internal variables
        self.anim = None
        self.rdates: list[dt.datetime] = []
        self.keyword = ""

    def set_title(self, rdate: dt.datetime, addition: str | None = None) -> None:
        """
        Add title to figure based on report date and additional text if inputted.

        Parameters
        ----------
        rstep : dt.datetime
            Report date
        addition : str | None, optional
            Adding string to end of title, by default None
        """
        # Title
        title = rdate.strftime("%d.%m.%Y")

        # Add string to end
        if addition is not None:
            title += addition

        # Add title to figure
        self.fig.suptitle(title)

    def add_collection(self, polyc: Poly3DCollection | PolyCollection) -> None:
        """
        Alias to axes.add_collection in matplotlib

        Parameters
        ----------
        polyc : Poly3DCollection/PolyCollection
            Collection of polygons for one slice
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

    def plot_wells(self, rstep: int) -> None:
        """
        Plot wells in slices (if any) for a report step

        Parameters
        ----------
        rstep : int
            Report step
        """
        # Loop over slices
        for slc in self.slice_coll:
            # Loop over all wells in slice and plot
            for name, well in slc.wells[rstep].items():
                if well:
                    # Cell center coordinates of well
                    wcent = np.array(
                        [
                            slc.cell_centers()[slc.active_indices().index(ind)]
                            for ind in well[:-1]
                        ]
                    )

                    # Plot options. k-slices in 2D view is essentially a scatter plot; else for
                    # other slices in 2D/3D we plot wells as a line.
                    color = "k" if well[-1] else "r"
                    if isinstance(slc, SlicePoly2D) and slc.slice_dim == "k":
                        well_kwargs = {
                            "marker": ".",
                            "markersize": 10,
                            "markeredgecolor": color,
                            "markerfacecolor": color,
                        }
                    else:
                        well_kwargs = {
                            "linewidth": 2,
                            "color": color,
                        }

                    # Use Axes/Axes3D plot method to display wells with name
                    if isinstance(slc, SlicePoly2D):
                        self.ax_.plot(wcent[:, 0], wcent[:, 1], **well_kwargs)
                        self.ax_.annotate(
                            name, (wcent[0, 0], wcent[0, 1]), c=color, ha="center"
                        )
                    else:
                        self.ax_.plot(
                            wcent[:, 0], wcent[:, 1], wcent[:, 2], **well_kwargs
                        )
                        self.ax_.text(
                            wcent[0, 0], wcent[0, 1], wcent[0, 2], name, color=color
                        )

    # pylint: disable=too-many-arguments
    def plot(
        self,
        rstep: int,
        keyword: str,
        colorbar: bool = True,
        equal_clim: bool = True,
        polyc_dict: dict[int, list[Poly3DCollection] | list[PolyCollection]]
        | None = None,
        *,
        diff_rstep: int | None = None,
        diff_kind: str = "plain",
        calc_kind: str | None = None,
        calc_count: int | None = None,
        **kwargs,
    ) -> None:
        """
        Plot keyword at one report step.

        Parameters
        ----------
        rstep : int
            Report step
        keyword : str
            OPM keyword to plot
        colorbar : bool
            Insert colorbar, by default True
        equal_clim : bool
            Equal colormap range for all slices, by default True
        polyc_dict : dict, optional
            Pre-generated slices (list of Poly3DCollection/PolyCollection), by default None.
        diff_rstep : int | None, optional
            Plot the difference from this report step instead of keyword's own values, by
            default None (the values themselves). Ignored when polyc_dict is given, since its
            data was already generated (see animate()).
        diff_kind : str, optional
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given, by
            default "plain"
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS: reduce keyword across a range of layers
            along each slice's own dimension instead of using its own values, by default None.
            Ignored when polyc_dict is given, since its data was already generated (see
            animate()). Combines with diff_rstep: see SlicePoly.generate()'s notes.
        calc_count : int | None, optional
            Limit calc_kind's layer range to this many further layers after each slice's own
            index, which is always included itself, by default None (continue to the grid's
            last layer). Only used when calc_kind is given.
        kwargs: optional
            Optional arguments passed to Poly3DCollection/PolyCollection

        Notes
        -----
        Use show or save_plot to show plot on screen or save to file.
        """
        # If pre-generated polyc data have been inputted, we just add the correct one(s) for the
        # current report step
        if polyc_dict is not None:
            polyc_rstep = polyc_dict[rstep]

        # Else, generate data for each slice and add to axes collection
        else:
            polyc_rstep = [
                slc.generate(
                    keyword,
                    rstep,
                    diff_rstep=diff_rstep,
                    diff_kind=diff_kind,
                    calc_kind=calc_kind,
                    calc_count=calc_count,
                    **kwargs,
                )
                for slc in self.slice_coll
            ]

        # Set equal color range if there are more than one slice.
        if "clim" not in kwargs and equal_clim is True and len(polyc_rstep) > 1:
            # First we need min/max across all slices
            min_polyc = 0
            max_polyc = 0
            for polyc in polyc_rstep:
                min_polyc = np.minimum(min_polyc, polyc.get_array().min())
                max_polyc = np.maximum(max_polyc, polyc.get_array().max())

            # Second, we set clim
            for polyc in polyc_rstep:
                polyc.set_clim(min_polyc, max_polyc)

        # Add all polyc to axes collection
        for polyc in polyc_rstep:
            self.add_collection(polyc)

        # Plot wells
        self.plot_wells(rstep)

        # Add report date to plot list
        rdate = self.report.report_date(rstep)
        self.rdates.append(rdate)

        # Save keyword, for save_plot's filename; see _keyword_tag
        self.keyword = self._keyword_tag(keyword, diff_rstep, diff_kind, calc_kind)

        # Set title
        self.set_title(rdate)

        # Set colorbar
        if colorbar is True:
            # Warn user if equal_clim is False, since colobar will be set according to first slice
            if "clim" not in kwargs and equal_clim is False and len(polyc_rstep) > 1:
                warnings.warn(
                    "Multiple slices will be plotted, but colorbar is only valid for slice "
                    f"({self.slice_coll[0].slice_dim}, {self.slice_coll[0].slice_ind})! "
                    "Set equal_clim == True or a 'clim' to make the colorbar valid for all slices!"
                )

            # Following above warning, we only need to use the first slice
            clabel = self._colorbar_label(keyword, diff_rstep, diff_kind, calc_kind)
            self.fig.colorbar(polyc_rstep[0], ax=self.ax_, label=clabel)

    def _colorbar_label(
        self,
        keyword: str,
        diff_rstep: int | None,
        diff_kind: str,
        calc_kind: str | None = None,
    ) -> str:
        """
        Colour bar label for one keyword, or its difference/calculator result

        Parameters
        ----------
        keyword : str
            OPM keyword
        diff_rstep : int | None
            Report step being differenced against, or None for keyword's own values
        diff_kind : str
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS, or None for keyword's own values, by default
            None

        Returns
        -------
        str
            e.g. "PRESSURE [barsa]", "ΔPRESSURE [barsa]"/"ΔSGAS [%]" for a diff, or
            "mean(PRESSURE) [barsa]"/"mean(ΔPRESSURE) [barsa]" with a calculator - the delta
            sits inside the parentheses, matching SlicePoly.generate()'s own "diff first, then
            aggregate" order
        """
        name = keyword if diff_rstep is None else diff_label(keyword, diff_kind)
        name = name if calc_kind is None else calc_label(name, calc_kind)

        if diff_rstep is not None and diff_kind == "relative":
            return f"{name} [%]"
        return name + " [" + self.label(keyword) + "]"

    def plot_grid(self, **kwargs) -> None:
        """
        Plot grid slice without any data

        Parameters
        ----------
        kwargs: optional
            Optional arguments passed to PolyCollection/Poly3DCollection
        """
        # Generate PolyCollection/Poly3DCollection with just the cell corners
        polyc_grid = [slc.generate_poly(**kwargs) for slc in self.slice_coll]

        # Add all polyc to axes collection
        for polyc in polyc_grid:
            self.add_collection(polyc)

    def animate(
        self,
        keyword: str,
        rsteps: list[int] | None = None,
        *,
        rstep_list: Sequence[int] | None = None,
        diff_rstep: int | None = None,
        diff_kind: str = "plain",
        calc_kind: str | None = None,
        calc_count: int | None = None,
        **kwargs,
    ) -> None:
        """
        Generate an animation over report steps

        Parameters
        ----------
        keyword : str
            OPM keyword to plot
        rsteps : list[int] | None, optional
            [start, end] inclusive range of report steps. If None and rstep_list is also None,
            every report step is included in the animation.
        rstep_list : Sequence[int] | None, optional
            Explicit report steps to animate, in order, by default None. Takes priority over
            rsteps: use this instead of rsteps when the steps to include are not a contiguous
            range, e.g. every 5th report step, since rsteps assumes every integer between start
            and end is a real report step.
        diff_rstep : int | None, optional
            Animate the difference from this (fixed) report step instead of keyword's own
            values, by default None (the values themselves)
        diff_kind : str, optional
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given, by
            default "plain"
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS: reduce keyword across a range of layers
            along each slice's own dimension instead of using its own values, by default None.
            Combines with diff_rstep: see SlicePoly.generate()'s notes.
        calc_count : int | None, optional
            Limit calc_kind's layer range to this many further layers after each slice's own
            index, which is always included itself, by default None (continue to the grid's
            last layer). Only used when calc_kind is given.
        kwargs: optional
            Optional arguments passed to Poly3DCollection/PolyCollection

        Notes
        -----
        Use show or save_gif to show the animation on screen or save it to file. save_gif is
        named for what it writes, not this method: this backend can only ever animate to a
        GIF, unlike opm_vis.pvplot's GridPlotter.animate which can also write a movie file.
        """
        # Which report steps and dates to include in the animation
        if rstep_list is not None:
            anim_rsteps = list(rstep_list)
            self.rdates = [self.report.report_date(rstep) for rstep in anim_rsteps]
        elif rsteps is None:
            # All report steps
            anim_rsteps = self.report.report_steps()
            self.rdates = self.report.report_dates()
        else:
            all_rsteps = self.report.report_steps()
            all_rdates = self.report.report_dates()
            anim_rsteps = list(range(rsteps[0], rsteps[1] + 1))
            self.rdates = [all_rdates[all_rsteps.index(i)] for i in anim_rsteps]

        # Save keyword, for save_gif's filename; see _keyword_tag
        self.keyword = self._keyword_tag(keyword, diff_rstep, diff_kind, calc_kind)

        # Generate slices for all report dates to be able to set one colorbar for the whole
        # animation
        polyc_dict = self._data_for_animation(
            anim_rsteps,
            keyword,
            diff_rstep=diff_rstep,
            diff_kind=diff_kind,
            calc_kind=calc_kind,
            calc_count=calc_count,
            **kwargs,
        )

        # Set colorbar for the whole animation
        clabel = self._colorbar_label(keyword, diff_rstep, diff_kind, calc_kind)
        self.fig.colorbar(polyc_dict[anim_rsteps[0]][0], ax=self.ax_, label=clabel)

        # Setup plot function to fit with FuncAnimation. diff_rstep/diff_kind/calc_kind/
        # calc_count are not passed through here: polyc_dict already carries the (possibly
        # diff'd/aggregated) data, and plot() ignores its own diff_rstep/diff_kind/calc_kind/
        # calc_count whenever polyc_dict is given.
        plot_func = partial(
            self.plot,
            keyword=keyword,
            colorbar=False,
            equal_clim=False,
            polyc_dict=polyc_dict,
            **kwargs,
        )

        # Set up Matplotlib animation
        self.anim = animation.FuncAnimation(self.fig, plot_func, frames=anim_rsteps)

    def _data_for_animation(
        self,
        rsteps: list[int],
        keyword: str,
        *,
        diff_rstep: int | None = None,
        diff_kind: str = "plain",
        calc_kind: str | None = None,
        calc_count: int | None = None,
        **kwargs,
    ) -> dict[int, list[Poly3DCollection] | list[PolyCollection]]:
        """
        Pre-generate data for report steps.

        Parameters
        ----------
        rsteps : list[int]
            List of report steps to generate plot data
        keyword : str
            OPM keyword to plot
        diff_rstep : int | None, optional
            Generate the difference from this report step instead of keyword's own values,
            by default None (the values themselves)
        diff_kind : str, optional
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given, by
            default "plain"
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS: reduce keyword across a range of layers
            along each slice's own dimension instead of using its own values, by default None
        calc_count : int | None, optional
            Limit calc_kind's layer range to this many further layers after each slice's own
            index, which is always included itself, by default None (continue to the grid's
            last layer). Only used when calc_kind is given.

        Returns
        -------
        dict[int, list[Poly3DCollection] | list[PolyCollection]]
            Dictionary of slice Poly3DCollection/PolyCollection with keyword data at report steps
            (dictionary key)
        """
        # Initialize dict output
        polyc_dict = {k: [] for k in rsteps}

        # Generate data for each slice at each report step
        for rstep in rsteps:
            polyc_dict[rstep] = [
                slc.generate(
                    keyword,
                    rstep,
                    diff_rstep=diff_rstep,
                    diff_kind=diff_kind,
                    calc_kind=calc_kind,
                    calc_count=calc_count,
                    **kwargs,
                )
                for slc in self.slice_coll
            ]

        # If clim have not been set in kwargs, we must loop over all polyc and set clim to min/max
        # for all data
        if "clim" not in kwargs:
            # First loop round to get min/max for all slices in all report steps
            min_polyc = 0
            max_polyc = 0
            for rstep in rsteps:
                for polyc in polyc_dict[rstep]:
                    min_polyc = np.minimum(min_polyc, polyc.get_array().min())
                    max_polyc = np.maximum(max_polyc, polyc.get_array().max())

            # Second loop round to set uniform clim for all slices in all report steps
            for rstep in rsteps:
                for polyc in polyc_dict[rstep]:
                    polyc.set_clim(min_polyc, max_polyc)

        return polyc_dict

    def show(self) -> None:
        """Show figure on screen"""
        plt.show()
        plt.close("all")

    def save_plot(self, filename: str | Path | None = None, file_format: str = "png") -> None:
        """
        Save plot to file.

        Parameters
        ----------
        filename : str | Path | None, optional
            File to write the image to, by default None, which combines the input path, report
            date, OPM keyword and slice info into a name next to the input case.
        file_format : str, optional
            File format for save file. Must be a valid Matplotlib file format (see savefig
            documentation), by default 'png'. Ignored if filename is given.
        """
        # Check if any plot has been made
        if not self.ax_.collections:
            raise RuntimeError("No plot to save! Run plot() method first.")

        if filename is None:
            # Report date of plot
            rdate_str = self.rdates[-1].strftime("%d-%m-%Y")

            filename = (
                f"{self.paths[0]}{self.keyword}_{rdate_str}_{self._slice_info()}."
                f"{file_format}"
            )

        # Save file
        self.fig.savefig(filename)
        plt.close("all")

    def save_grid_plot(
        self, filename: str | Path | None = None, file_format: str = "png"
    ) -> None:
        """
        Save plot of just the grid (no data)

        Parameters
        ----------
        filename : str | Path | None, optional
            File to write the image to, by default None, which combines the input path and
            slice info into a name next to the input case.
        file_format : str, optional
            File format for save file. Must be a valid Matplotlib file format (see savefig
            documentation), by default 'png'. Ignored if filename is given.
        """
        if filename is None:
            filename = f"{self.paths[0]}GRID_{self._slice_info()}.{file_format}"

        # Save file
        self.fig.savefig(filename)
        plt.close("all")

    def save_gif(self, filename: str | Path | None = None, fps: int = 3) -> None:
        """
        Save plot movie to gif.

        Parameters
        ----------
        filename : str | Path | None, optional
            File to write the gif to, by default None, which combines the input path, date
            span, OPM keyword and slice info into a name next to the input case.
        fps : int, optional
            Frames per second, by default 3
        """
        # Check if any animation have been made
        if self.anim is None:
            raise RuntimeError("No gif to save! Run animate() method first.")

        if filename is None:
            # Date span included in gif
            date_span = (
                f"{self.rdates[0].strftime('%d-%m-%Y')}_"
                f"{self.rdates[-1].strftime('%d-%m-%Y')}"
            )
            filename = (
                f"{self.paths[0]}{self.keyword}_{date_span}_{self._slice_info()}.gif"
            )

        # Save gif
        self.anim.save(filename, writer=animation.PillowWriter(fps=fps))

    def _slice_info(self) -> str:
        """
        Slice dimension/index of every slice, joined for use in a filename

        Returns
        -------
        str
            e.g. "k0" for one slice, "k0_j5" for several
        """
        return "_".join(f"{slc.slice_dim}{slc.slice_ind}" for slc in self.slice_coll)

    @staticmethod
    def _keyword_tag(
        keyword: str,
        diff_rstep: int | None,
        diff_kind: str,
        calc_kind: str | None = None,
    ) -> str:
        """
        Keyword string used in auto-generated filenames, reflecting diff/calculator mode if
        active

        Parameters
        ----------
        keyword : str
            OPM keyword
        diff_rstep : int | None
            Report step being differenced against, or None for keyword's own values
        diff_kind : str
            One of opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given
        calc_kind : str | None, optional
            One of opm_vis.utils.calc.CALC_KINDS, or None for keyword's own values, by default
            None

        Returns
        -------
        str
            keyword unchanged, or e.g. "SGAS-mean-diff0-relative" with a calculator and a diff
        """
        tag = keyword if calc_kind is None else f"{keyword}-{calc_kind}"

        if diff_rstep is None:
            return tag

        tag += f"-diff{diff_rstep}"
        return tag if diff_kind == "plain" else f"{tag}-{diff_kind}"


class SlicePoly3DCollection(_SlicePolyCollection):
    """
    Class for plotting collection of slices in 3D view
    """

    def __init__(
        self,
        paths: list[str],
        slice_info: list[tuple[str, int]],
        calc_count: int | None = None,
        surface: bool = False,
    ) -> None:
        """
        Initialize class by setting up figure/axes.

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_info : list[tuple[str, int]]
            Info to generate slices: [(dimension=i, j, or k, index)]
        calc_count : int | None, optional
            Value of --calc-count, by default None. Only used when surface is True; passed to
            every slice in slice_info, though --calculator (and so surface) only ever applies
            to a single one in practice - see resolve_calculator.
        surface : bool, optional
            --calculator surface, by default False. See SlicePoly3D/_GridSlice for what this
            changes about a slice's own geometry/active cells.
        """
        # Generate collection of slices
        slice_coll = [
            SlicePoly3D(paths, dim, ind, calc_count, surface) for dim, ind in slice_info
        ]

        # Setup matplotlib figure
        fig = plt.figure()
        ax_ = fig.add_subplot(projection="3d")
        ax_.view_init(elev=30, azim=60)

        # Init parent class
        super().__init__(paths, fig, ax_, slice_coll)

        # Set limits first, since set_labels needs them to decide which axes go to km
        self.set_lims()

        # Set labels
        self.set_labels()

        # Invert z-axis
        self.ax_.invert_zaxis()

    def set_labels(self) -> None:
        """
        Set labels to Easting, Northing, and depth

        Notes
        -----
        Also switches an axis to km-scaled tick labels once its own span (set by set_lims,
        which must run first) exceeds _KM_AXIS_SPAN_M metres - see that constant.
        """
        x_min, x_max = self.ax_.get_xlim()
        y_min, y_max = self.ax_.get_ylim()
        z_min, z_max = self.ax_.get_zlim()

        self.ax_.set_xlabel(_km_axis_label("E(x)", x_max - x_min))
        self.ax_.set_ylabel(_km_axis_label("N(y)", y_max - y_min))
        self.ax_.set_zlabel(_km_axis_label("Depth(z)", z_max - z_min))

        _use_km_ticks_if_wide(self.ax_.xaxis, x_max - x_min)
        _use_km_ticks_if_wide(self.ax_.yaxis, y_max - y_min)
        _use_km_ticks_if_wide(self.ax_.zaxis, z_max - z_min)

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

    def __init__(
        self,
        paths: list[str],
        slice_dim: str,
        slice_ind: int,
        calc_count: int | None = None,
        surface: bool = False,
    ) -> None:
        """
        Initialize class by setting up figure/axes.

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs.
        slice_dim : str
            Dimension to slice : i, j, or k
        slice_ind : int
            Index of slice
        calc_count : int | None, optional
            Value of --calc-count, by default None. Only used when surface is True; see
            SlicePoly2D/_GridSlice.
        surface : bool, optional
            --calculator surface, by default False. See SlicePoly2D/_GridSlice for what this
            changes about the slice's own geometry/active cells.
        """
        # Generate 2D slice and put in a list to conform with parent class methods
        slice_coll = [SlicePoly2D(paths, slice_dim, slice_ind, calc_count, surface)]

        # Setup matplotlib figure
        fig = plt.figure()
        ax_ = fig.add_subplot()

        # Init parent class
        super().__init__(paths, fig, ax_, slice_coll)

        # Set limits first, since set_labels needs them to decide which axes go to km
        self.set_lims()

        # Set labels
        self.set_labels()

        # Invert axis as needed
        if self.slice_coll[0].slice_dim in ["i", "j"]:
            self.ax_.invert_yaxis()

    def set_labels(self) -> None:
        """
        Set labels according to slice dimension

        Notes
        -----
        Also switches an axis to km-scaled tick labels once its own span (set by set_lims,
        which must run first) exceeds _KM_AXIS_SPAN_M metres - see that constant.
        """
        if self.slice_coll[0].slice_dim == "i":
            xname, yname = "N(y)", "Depth"
        elif self.slice_coll[0].slice_dim == "j":
            xname, yname = "E(x)", "Depth"
        else:
            xname, yname = "E(x)", "N(y)"

        x_min, x_max = self.ax_.get_xlim()
        y_min, y_max = self.ax_.get_ylim()

        # Set labels
        self.ax_.set_xlabel(_km_axis_label(xname, x_max - x_min))
        self.ax_.set_ylabel(_km_axis_label(yname, y_max - y_min))

        _use_km_ticks_if_wide(self.ax_.xaxis, x_max - x_min)
        _use_km_ticks_if_wide(self.ax_.yaxis, y_max - y_min)

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
