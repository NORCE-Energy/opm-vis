"""Plot summary vectors (time series) with the Matplotlib backend"""
from __future__ import annotations

import csv
import datetime as dt
import io
import math
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from numpy.typing import NDArray

from opm_vis.utils.summary import SummaryReader
from opm_vis.utils.units import summary_unit_label

# What a time series can be plotted against: calendar dates, or elapsed time from the start of
# the simulation in the same units as the TIME and YEARS summary vectors.
X_AXES = ("date", "days", "years")

_X_AXIS_LABELS = {"date": "Date", "days": "Time [days]", "years": "Time [years]"}

# --linestyle's vocabulary, Matplotlib's own named line styles. Unlike --marker (whose valid
# values number in the dozens - every plot marker Matplotlib knows), there are only five of
# these, so they are worth spelling out and validating up front rather than leaving an
# unrecognised one to surface as Matplotlib's own error.
LINE_STYLES = ("solid", "dashed", "dashdot", "dotted", "none")

# Cycled per keyword when several keywords and several cases share one axes: colour then encodes
# the case and the dash pattern the keyword, so a comparison of several runs stays readable.
_LINESTYLES = ("-", "--", "-.", ":")

# Above this many keywords on one axes the y label drops their names and keeps only the shared
# unit: the legend already names them, and a wildcard matching every well would otherwise write
# a label longer than the axis.
_MAX_YLABEL_KEYWORDS = 3

# Keywords spelled out in a generated file name before it starts counting the rest instead. The
# same number as _MAX_YLABEL_KEYWORDS by coincidence, not by dependency - one bounds a label's
# width, the other a file name's.
_MAX_NAME_KEYWORDS = 3

# Legend entries beyond this are spread into further columns rather than one very tall column
_LEGEND_ENTRIES_PER_COLUMN = 12

# Room given to each subplot when no figure size was asked for, and the size the whole figure is
# capped at. Matplotlib's own default is one figure's worth of space however many subplots are
# in it, which a wildcard matching a dozen wells turns into unreadably small axes; the caps stop
# the opposite problem, a figure too large to look at, on an even bigger selection.
_SUBPLOT_WIDTH_IN = 4.0
_SUBPLOT_HEIGHT_IN = 2.8
_MAX_FIG_WIDTH_IN = 16.0
_MAX_FIG_HEIGHT_IN = 11.0

# Date ticks per axes. Unrotated labels are what keeps a grid of subplots readable, so there has
# to be a limit on how many of them share the width of one.
_MAX_DATE_TICKS = 6


def default_figsize(rows: int, cols: int) -> tuple[float, float] | None:
    """
    Figure size for a grid of subplots, when none was asked for

    Parameters
    ----------
    rows : int
        Rows in the grid
    cols : int
        Columns in the grid

    Returns
    -------
    tuple[float, float] | None
        Width and height in inches, or None for a single axes, which keeps Matplotlib's own
        default figure size
    """
    if (rows, cols) == (1, 1):
        return None

    return (
        min(cols * _SUBPLOT_WIDTH_IN, _MAX_FIG_WIDTH_IN),
        min(rows * _SUBPLOT_HEIGHT_IN, _MAX_FIG_HEIGHT_IN),
    )


def subplot_grid(n_axes: int, layout: tuple[int, int] | None = None) -> tuple[int, int]:
    """
    Rows and columns for a grid of subplots

    Parameters
    ----------
    n_axes : int
        Number of subplots the grid has to hold
    layout : tuple[int, int] | None, optional
        Explicit (rows, cols), by default None, which computes a near-square grid

    Returns
    -------
    tuple[int, int]
        (rows, cols), with rows * cols >= n_axes

    Raises
    ------
    ValueError
        If n_axes is not positive, or an explicit layout has no room for every subplot

    Notes
    -----
    The computed grid takes the ceiling of the square root as the number of *columns*, so a
    count that is not a perfect square spreads sideways rather than downwards: 2 -> 1x2,
    3 -> 2x2, 5 -> 2x3, 8 -> 3x3. A time axis is wide, so extra width costs less than extra
    height.
    """
    if n_axes < 1:
        raise ValueError(f"A grid needs at least one subplot; got {n_axes}.")

    if layout is not None:
        rows, cols = layout
        if rows < 1 or cols < 1:
            raise ValueError(f"Subplot layout must be positive; got {rows} {cols}.")
        if rows * cols < n_axes:
            raise ValueError(
                f"Subplot layout {rows} {cols} has room for {rows * cols} subplots, but "
                f"{n_axes} are needed."
            )
        return rows, cols

    cols = math.ceil(math.sqrt(n_axes))

    return math.ceil(n_axes / cols), cols


def x_axis_values(
    reader: SummaryReader, x_axis: str
) -> list[dt.datetime] | NDArray[np.float64]:
    """
    Values to plot a time series against

    Parameters
    ----------
    reader : SummaryReader
        Reader for the case
    x_axis : str
        One of X_AXES

    Returns
    -------
    list[dt.datetime] | NDArray[np.float64]
        Report dates, or elapsed days/years, one per timestep

    Raises
    ------
    ValueError
        If x_axis is not one of X_AXES
    """
    if x_axis == "date":
        return reader.summary_dates()
    if x_axis == "days":
        return reader.elapsed_days()
    if x_axis == "years":
        return reader.elapsed_years()

    raise ValueError(f"x_axis must be one of {X_AXES}; got '{x_axis}'.")


def unique_case_labels(readers: Sequence[SummaryReader]) -> list[str]:
    """
    Short, distinguishable names for the cases being plotted

    Parameters
    ----------
    readers : Sequence[SummaryReader]
        One reader per case

    Returns
    -------
    list[str]
        One label per reader, in the same order

    Notes
    -----
    Named after the .SMSPEC file each reader actually found, not the path prefix it was given,
    which can be "./" and say nothing about which case it is. Runs are conventionally kept in
    one directory each under the same case name, so plain file names would collide - when they
    do, every label (not only the colliding ones) gains its directory, so the legend stays
    internally consistent.
    """
    stems = [
        Path(reader.smry_paths[0]).stem if reader.smry_paths else "?" for reader in readers
    ]
    if len(set(stems)) == len(stems):
        return stems

    labels = [
        f"{Path(reader.smry_paths[0]).parent.name}/{stem}" if reader.smry_paths else stem
        for reader, stem in zip(readers, stems)
    ]
    if len(set(labels)) == len(labels):
        return labels

    # Still ambiguous (the same case name two directory levels apart) - fall back to numbering
    return [f"{label} #{i}" for i, label in enumerate(labels)]


def curve_label(
    keyword: str, case: str, *, multi_keyword: bool, multi_case: bool
) -> str:
    """
    Legend entry for one curve

    Parameters
    ----------
    keyword : str
        Summary mnemonic the curve shows
    case : str
        Case the curve comes from, as unique_case_labels() names it
    multi_keyword : bool
        Whether the axes holds more than one keyword
    multi_case : bool
        Whether more than one case is being plotted

    Returns
    -------
    str
        Legend entry naming whatever actually varies inside the axes: the keyword, the case, or
        both
    """
    if multi_keyword and multi_case:
        return f"{case} - {keyword}"
    if multi_case:
        return case

    return keyword


def resolve_curve_option(
    values: str | Sequence[str] | None, keywords: Sequence[str]
) -> dict[str, str | None]:
    """
    Map a linestyle/marker value - or one value per keyword - onto every keyword

    Parameters
    ----------
    values : str | Sequence[str] | None
        None (nothing given), a single value applied to every keyword, or one value per
        keyword, in the same order as keywords
    keywords : Sequence[str]
        Keywords being plotted

    Returns
    -------
    dict[str, str | None]
        One entry per keyword; every value is None if values was None or empty

    Raises
    ------
    ValueError
        If more than one value was given and the count does not match the number of keywords

    Notes
    -----
    A single value broadcasts to every keyword, which is what lets --linestyle/--marker work
    the same way whether one vector or several are being plotted; passing one value per keyword
    instead gives each its own. Used identically by SummaryPlot.plot() and by the CLI's own
    pre-validation (see cli.common.check_curve_option_count), so the two never disagree about
    what a given count of values means.
    """
    if values is None:
        return {keyword: None for keyword in keywords}
    if isinstance(values, str):
        return {keyword: values for keyword in keywords}

    values = list(values)
    if not values:
        return {keyword: None for keyword in keywords}
    if len(values) == 1:
        return {keyword: values[0] for keyword in keywords}
    if len(values) == len(keywords):
        return dict(zip(keywords, values))

    raise ValueError(
        f"Got {len(values)} values, but {len(keywords)} keyword(s) are being plotted "
        f"({', '.join(keywords)}); give one value to use for all of them, or exactly "
        f"{len(keywords)}, one per keyword in that order."
    )


def axes_ylabel(keywords: Sequence[str], units: Sequence[str]) -> str:
    """
    Y axis label for one axes

    Parameters
    ----------
    keywords : Sequence[str]
        Summary mnemonics drawn in the axes
    units : Sequence[str]
        Raw unit string of each of them, as SummaryReader.unit() returns them

    Returns
    -------
    str
        e.g. "FOPR [stb/day]" for one keyword, "[stb/day]" for many sharing a unit, or the
        units joined for keywords that do not share one

    Warns
    -----
    UserWarning
        If the keywords do not share a unit, since the axis then measures more than one thing
    """
    labels = [summary_unit_label(unit) for unit in units]
    distinct = list(dict.fromkeys(labels))

    if len(distinct) > 1:
        # No conversion and no second y axis: giving each keyword its own subplot is the
        # supported answer, and is what opm-vis-sum's --subplots does.
        warnings.warn(
            "Keywords with different units share one axes ("
            + ", ".join(f"{k} [{u}]" for k, u in zip(keywords, labels))
            + "); the y axis cannot be labelled meaningfully. Give each keyword its own "
            "subplot instead."
        )
        return " / ".join(distinct)

    if len(keywords) <= _MAX_YLABEL_KEYWORDS:
        return f"{', '.join(keywords)} [{distinct[0]}]"

    return f"[{distinct[0]}]"


# pylint: disable=too-many-instance-attributes
class SummaryPlot:
    """
    Line plots of summary vectors, for one or several keywords and one or several cases
    """

    def __init__(
        self,
        paths: list[str],
        *,
        compare: bool = False,
        figsize: tuple[float, float] | None = None,
    ) -> None:
        """
        Init. class by opening the summary files of every case to plot

        Parameters
        ----------
        paths : list[str]
            Paths with .SMSPEC files, as filename prefixes. Without compare, the first is the
            main run and the rest are its restart runs; with compare, each is a case of its own.
        compare : bool, optional
            Whether to read each path as a separate case, by default False
        figsize : tuple[float, float] | None, optional
            Figure size in inches, by default None, which keeps Matplotlib's own default for a
            single axes and scales with the grid for several (see default_figsize)

        Raises
        ------
        ValueError
            If no paths were given, or one of them has no .SMSPEC file

        Notes
        -----
        Only the summary files are opened here; the figure is built by plot(), which is where
        the number of keywords - and therefore the shape of the grid - is known.
        """
        if not paths:
            raise ValueError("No paths given; nothing to plot!")

        self.paths = paths
        self.figsize = figsize

        # The one place the PATHS convention forks: by default a single reader stitches the
        # whole restart chain into one series, exactly as every other opm_vis program treats
        # PATHS, while compare makes each path a case in its own right.
        self.readers = (
            [SummaryReader([path]) for path in paths] if compare else [SummaryReader(paths)]
        )

        # SummaryReader only warns when a path holds no .SMSPEC, which is right for a restart
        # chain - a missing restart still leaves the main run to plot - but leaves a mistyped
        # case silently absent from a comparison. Name it here, while the path it came from is
        # still known.
        if compare:
            for path, reader in zip(paths, self.readers):
                if not reader.smry:
                    raise ValueError(f"No .SMSPEC file was found in {path}; cannot plot it!")
        elif not self.readers[0].smry:
            raise ValueError("No .SMSPEC file was found; cannot plot summary data!")

        self.case_labels = unique_case_labels(self.readers)

        self.fig: Figure | None = None
        self.axes: list[Axes] = []
        self.axes_keywords: list[list[str]] = []
        self.x_axis = "date"
        self.lines: list[Line2D] = []
        self._bottom: list[Axes] = []

    def available_keywords(self) -> list[str]:
        """
        Return the summary keywords available in any of the cases

        Returns
        -------
        list[str]
            Union of every case's keywords, sorted

        Raises
        ------
        ValueError
            If no .SMSPEC file was found at all

        Notes
        -----
        A union rather than an intersection: cases being compared need not have identical
        SUMMARY sections, and a keyword one of them lacks simply contributes no line there.
        """
        keywords: set[str] = set()
        for reader in self.readers:
            keywords.update(reader.available_keywords())

        return sorted(keywords)

    def export_csv(self, keywords: Sequence[str], *, x_axis: str = "date") -> str:
        """
        Render the selected summary vectors as CSV

        Parameters
        ----------
        keywords : Sequence[str]
            Summary mnemonics to export, in the order they should appear as columns
        x_axis : str, optional
            One of X_AXES, by default "date". Becomes the first column.

        Returns
        -------
        str
            Header row followed by one row per timestep, without a trailing newline. One
            column per case and keyword (just the keyword when there is only one case); a case
            missing a keyword leaves that column blank at every row rather than failing outright,
            the same as a curve that plot() finds missing under --compare.

        Raises
        ------
        ValueError
            If no keywords were given, x_axis is unknown, or none of the keywords exists in any
            of the cases

        Notes
        -----
        Rows are the union of every case's own x axis values, sorted, since cases being compared
        need not share a report frequency or even a start date. With a single case - the common,
        non-compare use - every keyword shares the same rows, so this reduces to a plain
        per-timestep table.

        Dates are ISO-8601, matching the CSV export opm-vis-rdates already offers. Numbers are
        rounded to 6 significant digits: this is meant to accompany a plot, not to be the
        authoritative record of a run, and the export would otherwise carry more digits than the
        plot itself is read to.
        """
        if not keywords:
            raise ValueError("No keywords given; nothing to export!")
        if x_axis not in X_AXES:
            raise ValueError(f"x_axis must be one of {X_AXES}; got '{x_axis}'.")

        multi_case = len(self.readers) > 1
        columns: list[tuple[str, dict[Any, Any]]] = []
        for reader, case in zip(self.readers, self.case_labels):
            keys = list(x_axis_values(reader, x_axis))
            for keyword in keywords:
                if not reader.has_keyword(keyword):
                    continue
                header = f"{case}:{keyword}" if multi_case else keyword
                columns.append((header, dict(zip(keys, reader.read(keyword)))))

        if not columns:
            raise ValueError("No curves could be exported for the selected keywords!")

        all_keys = sorted({key for _, column in columns for key in column})

        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow([x_axis] + [header for header, _ in columns])
        for key in all_keys:
            row = [key.isoformat() if x_axis == "date" else f"{key:.6g}"]
            for _, column in columns:
                value = column.get(key)
                row.append("" if value is None else f"{float(value):.6g}")
            writer.writerow(row)

        return buffer.getvalue().rstrip("\n")

    def _unit(self, keyword: str) -> str:
        """
        Unit of a keyword, from the first case that has it

        Parameters
        ----------
        keyword : str
            Summary mnemonic

        Returns
        -------
        str
            Raw unit string, or "" if no case has the keyword
        """
        for reader in self.readers:
            if reader.has_keyword(keyword):
                return reader.unit(keyword)

        return ""

    def _make_figure(self, layout: tuple[int, int] | None) -> None:
        """
        Create the figure and its axes

        Parameters
        ----------
        layout : tuple[int, int] | None
            Explicit (rows, cols) for the grid, or None for a near-square one
        """
        rows, cols = subplot_grid(len(self.axes_keywords), layout)
        figsize = self.figsize if self.figsize is not None else default_figsize(rows, cols)

        # constrained layout rather than autofmt_xdate(), which fights it: date tick labels and
        # a grid of subplots both need the spacing solved for them.
        self.fig, grid = plt.subplots(
            rows,
            cols,
            sharex=True,
            squeeze=False,
            figsize=figsize,
            layout="constrained",
        )

        flat = list(grid.flat)
        self.axes = flat[: len(self.axes_keywords)]

        # A grid that is not exactly filled (5 keywords in a 2x3) would otherwise leave empty
        # framed boxes on the figure
        for extra in flat[len(self.axes_keywords) :]:
            self.fig.delaxes(extra)

        # sharex hid the tick labels of every axes with another one below it, on the assumption
        # that the grid is full. Where a column ends early, the axes now visually at the bottom
        # of it is one of those, so its labels have to be switched back on.
        self._bottom = []
        for col in range(cols):
            in_column = list(range(col, len(self.axes), cols))
            if in_column:
                self._bottom.append(self.axes[in_column[-1]])
        for ax_ in self._bottom:
            ax_.tick_params(labelbottom=True)

    def _format_x_axis(self) -> None:
        """Set date tick locators and formatters, for the date x axis only"""
        if self.x_axis != "date":
            return

        for ax_ in self.axes:
            # A locator binds to the axis it is set on, so every axes needs its own instance.
            # ConciseDateFormatter keeps the labels short enough not to need rotating, which is
            # what makes a grid of subplots readable; maxticks then keeps a decade from putting
            # ten of them side by side on a subplot only a few inches wide.
            locator = mdates.AutoDateLocator(maxticks=_MAX_DATE_TICKS)
            ax_.xaxis.set_major_locator(locator)
            ax_.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    def _curve_style(
        self, keyword_ind: int, case_ind: int, multi_keyword: bool, multi_case: bool
    ) -> dict:
        """
        Colour and dash pattern for one curve

        Parameters
        ----------
        keyword_ind : int
            Index of the keyword within its axes
        case_ind : int
            Index of the case
        multi_keyword : bool
            Whether the axes holds more than one keyword
        multi_case : bool
            Whether more than one case is being plotted

        Returns
        -------
        dict
            Keyword arguments for Axes.plot

        Notes
        -----
        Set explicitly rather than left to Matplotlib's property cycle, which restarts on every
        axes: a case has to keep one colour across all subplots for the legend of the first to
        mean anything in the rest.
        """
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

        if multi_case:
            # Colour identifies the case, dashes the keyword
            return {
                "color": colors[case_ind % len(colors)],
                "linestyle": _LINESTYLES[keyword_ind % len(_LINESTYLES)]
                if multi_keyword
                else "-",
            }

        return {"color": colors[keyword_ind % len(colors)], "linestyle": "-"}

    # pylint: disable=too-many-arguments,too-many-locals
    def plot(
        self,
        keywords: Sequence[str],
        *,
        x_axis: str = "date",
        subplots: bool = False,
        layout: tuple[int, int] | None = None,
        log_y: bool = False,
        xlim: tuple[Any, Any] | None = None,
        ylim: tuple[float, float] | None = None,
        title: str | None = None,
        grid: bool = True,
        legend: bool = True,
        linewidth: float | None = None,
        linestyle: str | Sequence[str] | None = None,
        marker: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Draw the selected summary vectors

        Parameters
        ----------
        keywords : Sequence[str]
            Summary mnemonics to plot, in the order they should appear
        x_axis : str, optional
            One of X_AXES, by default "date"
        subplots : bool, optional
            Whether to give each keyword its own subplot instead of drawing them all in one
            axes, by default False
        layout : tuple[int, int] | None, optional
            Explicit (rows, cols) for the subplot grid, by default None. Only used with
            subplots.
        log_y : bool, optional
            Whether to use a logarithmic y axis, by default False
        xlim : tuple[Any, Any] | None, optional
            X axis limits, by default None (the span of the data). Datetimes with x_axis
            "date", numbers otherwise.
        ylim : tuple[float, float] | None, optional
            Y axis limits, by default None (the range of the data)
        title : str | None, optional
            Figure title, by default None, which names the case when there is only one
        grid : bool, optional
            Whether to draw grid lines, by default True
        legend : bool, optional
            Whether to label the curves, by default True
        linewidth : float | None, optional
            Line width of every curve, by default None, which keeps Matplotlib's own default
        linestyle : str | Sequence[str] | None, optional
            One of LINE_STYLES, applied to every keyword; or one per keyword, in the same
            order as `keywords`. By default None, which draws a solid line - or, with several
            keywords sharing one axes under --compare, the per-keyword dash pattern that tells
            them apart from one case to the next. Given together with marker for a keyword,
            both are drawn; given alone with marker, it defaults to "none" for that keyword so
            the marker replaces the line instead of joining it.
        marker : str | Sequence[str] | None, optional
            Matplotlib marker for every data point (e.g. "o", "s", "^"), applied to every
            keyword or one per keyword, in the same order as `keywords`. By default None (no
            marker). See Matplotlib's marker reference for the full set.
        **kwargs
            Passed on to Axes.plot, overriding the computed colour and dash pattern, and
            linewidth/linestyle/marker if given there too

        Raises
        ------
        ValueError
            If no keywords were given, x_axis or a linestyle is unknown, linewidth is not
            positive, linestyle or marker was given as a sequence whose length matches
            neither 1 nor the number of keywords, a keyword's linestyle is "none" with no
            marker for it (nothing would be drawn), the layout has no room for every keyword,
            or none of the keywords exists in any of the cases

        Warns
        -----
        UserWarning
            If a case does not have one of the keywords, which is legal when comparing runs
            with different SUMMARY sections
        """
        if not keywords:
            raise ValueError("No keywords given; nothing to plot!")
        if x_axis not in X_AXES:
            raise ValueError(f"x_axis must be one of {X_AXES}; got '{x_axis}'.")
        if linewidth is not None and linewidth <= 0:
            raise ValueError(f"linewidth must be positive; got {linewidth}.")

        linestyles = resolve_curve_option(linestyle, keywords)
        markers = resolve_curve_option(marker, keywords)
        for keyword in keywords:
            keyword_linestyle = linestyles[keyword]
            if keyword_linestyle is not None and keyword_linestyle not in LINE_STYLES:
                raise ValueError(
                    f"linestyle must be one of {LINE_STYLES}; got '{keyword_linestyle}'."
                )
            if keyword_linestyle == "none" and markers[keyword] is None:
                raise ValueError(
                    f"{keyword}: linestyle='none' with no marker draws nothing; pass marker "
                    "to plot markers instead of a line."
                )
            # A marker with no explicit linestyle replaces the line rather than joining it -
            # the per-keyword dash pattern a bare curve gets otherwise is not what "give me
            # markers" implies.
            if keyword_linestyle is None and markers[keyword] is not None:
                linestyles[keyword] = "none"

        self.x_axis = x_axis
        self.axes_keywords = (
            [[keyword] for keyword in keywords] if subplots else [list(keywords)]
        )
        self.lines = []

        self._make_figure(layout)
        self._format_x_axis()

        multi_case = len(self.readers) > 1
        for ax_, axes_keywords in zip(self.axes, self.axes_keywords):
            multi_keyword = len(axes_keywords) > 1
            for keyword_ind, keyword in enumerate(axes_keywords):
                for case_ind, (reader, case) in enumerate(
                    zip(self.readers, self.case_labels)
                ):
                    # Cases being compared need not share a SUMMARY section; one without this
                    # vector contributes no line, rather than failing the whole plot
                    if not reader.has_keyword(keyword):
                        warnings.warn(
                            f"{keyword} is not in case {case}; skipping that curve."
                        )
                        continue

                    style = self._curve_style(
                        keyword_ind, case_ind, multi_keyword, multi_case
                    )
                    if linewidth is not None:
                        style["linewidth"] = linewidth
                    if linestyles[keyword] is not None:
                        style["linestyle"] = linestyles[keyword]
                    if markers[keyword] is not None:
                        style["marker"] = markers[keyword]
                    (line,) = ax_.plot(
                        x_axis_values(reader, x_axis),
                        reader.read(keyword),
                        label=curve_label(
                            keyword,
                            case,
                            multi_keyword=multi_keyword,
                            multi_case=multi_case,
                        ),
                        **{**style, **kwargs},
                    )
                    self.lines.append(line)

        if not self.lines:
            raise ValueError("No curves could be plotted for the selected keywords!")

        self.set_labels()
        self.set_title(title)
        self.set_grid(grid)
        self.set_legend(legend)
        self.set_log_y(log_y)
        self.set_lims(xlim, ylim)

    def set_labels(self) -> None:
        """
        Label the axes

        Notes
        -----
        The x axis is labelled on the bottom row only: with a shared x axis, labelling every
        axes repeats the same text down each column.
        """
        for ax_, axes_keywords in zip(self.axes, self.axes_keywords):
            ax_.set_ylabel(
                axes_ylabel(
                    axes_keywords, [self._unit(keyword) for keyword in axes_keywords]
                )
            )

        for ax_ in self._bottom:
            ax_.set_xlabel(_X_AXIS_LABELS[self.x_axis])

    def set_title(self, title: str | None = None) -> None:
        """
        Set the figure title

        Parameters
        ----------
        title : str | None, optional
            Title text, by default None, which names the case when only one is plotted and
            leaves the figure untitled otherwise, where the legend already names the cases
        """
        if self.fig is None:
            return

        if title is None:
            if len(self.readers) > 1:
                return
            title = self.case_labels[0]

        self.fig.suptitle(title)

    def set_legend(self, legend: bool = True, **kwargs) -> None:
        """
        Label the curves

        Parameters
        ----------
        legend : bool, optional
            Whether to draw a legend at all, by default True
        **kwargs
            Passed on to Axes.legend

        Notes
        -----
        An axes with a single curve gets none: its y label already names what it shows, so a
        legend would only repeat it.
        """
        for ax_ in self.axes:
            lines = ax_.get_lines()
            if not legend or len(lines) < 2:
                continue

            ncols = math.ceil(len(lines) / _LEGEND_ENTRIES_PER_COLUMN)
            ax_.legend(ncols=ncols, fontsize="small", **kwargs)

    def set_log_y(self, log_y: bool = True) -> None:
        """
        Switch the y axis to a logarithmic scale

        Parameters
        ----------
        log_y : bool, optional
            Whether to use a logarithmic y axis, by default True

        Warns
        -----
        UserWarning
            If a curve has no positive value at all, since Matplotlib drops non-positive points
            on a logarithmic axis and the curve would simply be missing
        """
        if not log_y:
            return

        for line in self.lines:
            values = line.get_ydata()
            # Only an entirely non-positive curve is worth warning about: a rate that is zero
            # until its well opens is ordinary, and its later values still plot
            if len(values) and not np.any(np.asarray(values) > 0):
                warnings.warn(
                    f"{line.get_label()} has no positive values; it cannot be drawn on a "
                    "logarithmic y axis."
                )

        for ax_ in self.axes:
            ax_.set_yscale("log")

    def set_lims(
        self,
        xlim: tuple[Any, Any] | None = None,
        ylim: tuple[float, float] | None = None,
    ) -> None:
        """
        Set axis limits

        Parameters
        ----------
        xlim : tuple[Any, Any] | None, optional
            X axis limits, by default None (leave them to Matplotlib). Datetimes on a date
            axis, numbers otherwise.
        ylim : tuple[float, float] | None, optional
            Y axis limits, by default None (leave them to Matplotlib)

        Notes
        -----
        Applied to every axes. With one keyword per subplot that means subplots measuring
        different things share a y range, which is rarely wanted but is what was asked for.
        """
        for ax_ in self.axes:
            if xlim is not None:
                ax_.set_xlim(xlim)
            if ylim is not None:
                ax_.set_ylim(ylim)

    def set_grid(self, grid: bool = True) -> None:
        """
        Draw grid lines behind the curves

        Parameters
        ----------
        grid : bool, optional
            Whether to draw them, by default True

        Notes
        -----
        The line properties are only passed when the grid is being turned on: Axes.grid() takes
        any of them as a sign that the grid is wanted after all, and switches it back on.
        """
        for ax_ in self.axes:
            if grid:
                ax_.grid(True, alpha=0.4)
            else:
                ax_.grid(False)

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
            File to write the image to, by default None, which combines the input path and the
            plotted keywords into a name next to the input case.
        file_format : str, optional
            File format for save file. Must be a valid Matplotlib file format (see savefig
            documentation), by default 'png'. Ignored if filename is given.

        Raises
        ------
        RuntimeError
            If nothing has been plotted yet
        """
        if self.fig is None or not self.lines:
            raise RuntimeError("No plot to save! Run plot() method first.")

        if filename is None:
            filename = f"{self.paths[0]}{self._keyword_tag()}.{file_format}"

        self.fig.savefig(filename)
        plt.close("all")

    def _keyword_tag(self) -> str:
        """
        Return the plotted keywords as a file name fragment

        Returns
        -------
        str
            e.g. "FOPR_FGOR", or "FOPR_FGOR_WBHP-PROD_and17more" for a long selection

        Notes
        -----
        ":" and "," are ordinary characters in a summary mnemonic (WBHP:PROD, BPR:1,1,1) but
        poor ones in a file name, and ":" is outright invalid on Windows.
        """
        keywords = [keyword for axes_keywords in self.axes_keywords for keyword in axes_keywords]
        tags = [
            keyword.replace(":", "-").replace(",", "-")
            for keyword in keywords[:_MAX_NAME_KEYWORDS]
        ]
        extra = len(keywords) - len(tags)
        if extra:
            tags.append(f"and{extra}more")

        return "_".join(tags)
