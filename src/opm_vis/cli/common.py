"""Click options and helpers shared by the opm-vis command line programs"""
from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable, Sequence
from functools import wraps
from pathlib import Path
from typing import Any, Literal, overload

import click

from opm_vis.utils.calc import CALC_KINDS
from opm_vis.utils.cases import find_cases

# Show the help page both on -h/--help and when the command is run with nothing at all: with
# --folder defaulting to the working directory and --rstep optional for static keywords, a bare
# invocation has no other useful thing to do.
COMMAND_SETTINGS = {
    "context_settings": {"help_option_names": ["-h", "--help"]},
    "no_args_is_help": True,
}

# Folders are searched for cases by resolve_paths() below, which falls back to the working
# directory when none are given. Every case found is part of one run: the main run followed by
# its restarts, see opm_vis.utils.cases.
FOLDER_OPTION = click.option(
    "-f",
    "--folder",
    "folders",
    multiple=True,
    type=click.Path(exists=True, file_okay=False),
    metavar="DIR",
    help="Folder with the case's output files (repeatable). Every case found in the given "
    "folders is read as one run: the main run followed by its restarts, ordered by where "
    "each starts. Default: the current folder.",
)

KEYWORD_OPTION = click.option(
    "-K",
    "--keyword",
    default=None,
    help="OPM keyword to plot, e.g. SGAS or PRESSURE. Required unless --grid-only is given.",
)

# -i/-j/-k replace the old --slice-dim/--slice-index pair: at least one is given, and its
# value is the index of the slice on that dimension. Each is repeatable (-k 1 -k 6 -j 3) so
# several slices can be plotted together; this is also why --keyword lost its -k short form.
# Indices are 1-based (Fortran/Eclipse-style, matching e.g. COMPDAT), converted to the 0-based
# indices the rest of opm_vis uses internally by resolve_slices().
SLICE_OPTIONS = [
    click.option(
        "-i",
        "--i-index",
        "slice_i",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the i dimension at this 1-based index. Repeatable.",
    ),
    click.option(
        "-j",
        "--j-index",
        "slice_j",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the j dimension at this 1-based index. Repeatable.",
    ),
    click.option(
        "-k",
        "--k-index",
        "slice_k",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the k dimension at this 1-based index. Repeatable.",
    ),
]

# An interactive window is shown by default (no value); --save/-s switches to writing a file
# instead, either an explicit PATH or (given with no value) a name generated from what is being
# plotted - see default_output_name and default_summary_output_name. This is click's "option
# with an optional value" mechanism: the three observable states are None (not given), "" (given
# with no value) and a path string.
SAVE_OPTION = click.option(
    "--save",
    "-s",
    is_flag=True,
    default=False,
    help="Save to a file instead of opening an interactive window. The file name is generated "
    "from what is being plotted, in --save-folder.",
)




def _check_save_name(_ctx: click.Context, _param: click.Parameter, value: str | None) -> str | None:
    """
    Reject a --save-name that is empty or holds a folder, which --save-folder picks instead
    """
    if value is None:
        return None
    if not value.strip():
        raise click.BadParameter("must not be empty.")
    if "/" in value or "\\" in value:
        raise click.BadParameter(
            f"is a file name, without a folder; got '{value}'. Use --save-folder for the folder."
        )
    return value


# Given on its own, --save-name implies --save, the same way --save-folder does
SAVE_NAME_OPTION = click.option(
    "--save-name",
    "-sn",
    "save_name",
    default=None,
    metavar="NAME",
    callback=_check_save_name,
    help="File name to save to, without its suffix, which is added to match the format (e.g. "
    ".png). Implies --save. The folder is --save-folder's. Default: a name generated from "
    "what is being plotted.",
)


def save_folder_option(figure_folder: str, animation_folder: str | None = None) -> Callable:
    """
    Build the --save-folder option, whose default folder names differ per program

    Parameters
    ----------
    figure_folder : str
        Default folder name for still images, e.g. "pv-figs"
    animation_folder : str | None, optional
        Default folder name for animations, e.g. "pv-gifs", by default None for a program
        that does not animate

    Returns
    -------
    Callable
        The click.option decorator

    Notes
    -----
    Given on its own, --save-folder implies --save: naming a folder to save to is a clear
    enough request to save. click.Path(file_okay=False) rejects an existing file; a missing
    folder is fine, since save_path() creates it.
    """
    defaults = f"{figure_folder}/" + (
        f" for an image, {animation_folder}/ for an animation" if animation_folder else ""
    )
    return click.option(
        "--save-folder",
        "-sf",
        "save_folder",
        type=click.Path(file_okay=False),
        default=None,
        metavar="DIR",
        help=f"Folder to save to, created if it does not exist. Implies --save. Default: "
        f"{defaults}, inside the first -f/--folder (the current folder if none is given).",
    )


WELL_NAME_OPTION = click.option(
    "--well-name",
    "well_names",
    multiple=True,
    metavar="NAME",
    help="Only draw this well (repeatable). Without it, every well is drawn.",
)

FAULT_LABELS_OPTION = click.option(
    "--fault-labels/--no-fault-labels",
    "fault_labels",
    default=True,
    show_default=True,
    help="Label each fault with its name. Only used with --fault.",
)

# Polygons in the plot's own coordinates; see opm_vis.utils.polygons.read_polygons
POLYGON_OPTIONS = [
    click.option(
        "--polygon",
        "polygon_paths",
        multiple=True,
        type=click.Path(exists=True, dir_okay=False),
        metavar="PATH",
        help="File with polygons to draw (repeatable): NumPy .npy/.npz, text (.txt, .csv, "
        ".dat, .xyz: x y [z] columns, a blank line between polygons) or GeoJSON. Points are "
        "in the grid's own coordinates, with z as depth. x,y-only outlines are drawn on "
        "k-slices, and at the top of the grid in 3D.",
    ),
    click.option(
        "--polygon-color",
        default="red",
        show_default=True,
        help="Colour of the --polygon lines and labels.",
    ),
    click.option(
        "--polygon-linewidth",
        type=click.FloatRange(min=0, min_open=True),
        default=None,
        metavar="WIDTH",
        help="Line thickness of the --polygon lines: pixels in opm-vis-pv (default 3), points "
        "in opm-vis-mpl (default 2).",
    ),
    click.option(
        "--polygon-label",
        "polygon_labels",
        multiple=True,
        metavar="TEXT",
        help="Label for the polygons of each --polygon file, given once per file in the same "
        'order (repeatable). "" leaves that file unlabelled. Default: each polygon\'s own '
        "name, i.e. its file name, .npz key or GeoJSON name.",
    ),
    click.option(
        "--polygon-labels/--no-polygon-labels",
        "show_polygon_labels",
        default=True,
        show_default=True,
        help="Label each polygon.",
    ),
]


def polygon_labels_arg(
    polygon_paths: Sequence[str], polygon_labels: Sequence[str], show_polygon_labels: bool
) -> bool | list[str]:
    """
    Turn the --polygon label options into add_polygons/plot_polygons' labels argument

    Parameters
    ----------
    polygon_paths : Sequence[str]
        Value of --polygon
    polygon_labels : Sequence[str]
        Value of --polygon-label
    show_polygon_labels : bool
        Value of --polygon-labels/--no-polygon-labels

    Returns
    -------
    bool | list[str]
        False to draw no labels, the --polygon-label values to relabel each file, or True to
        keep every polygon's own name

    Raises
    ------
    click.UsageError
        If --polygon-label is given without --polygon, or not once per --polygon
    """
    if polygon_labels and not polygon_paths:
        raise click.UsageError("--polygon-label needs --polygon.")
    if polygon_labels and len(polygon_labels) != len(polygon_paths):
        raise click.UsageError(
            f"--polygon-label was given {len(polygon_labels)} time(s) for {len(polygon_paths)} "
            '--polygon file(s); give one label per file, "" for none.'
        )
    if not show_polygon_labels:
        return False
    return list(polygon_labels) if polygon_labels else True

COLORBAR_LABEL_OPTION = click.option(
    "--colorbar-label",
    "-clabel",
    "colorbar_label",
    default=None,
    metavar="TEXT",
    help="Colour bar label instead of the generated keyword and unit. Text between $ signs is "
    "rendered as math, LaTeX-style: e.g. '$k_x$ [mD]' or '$\\Delta p$ [bar]' (single-quote it "
    "so the shell leaves the $ alone).",
)


def check_colorbar_label(
    colorbar_label: str | None, *, no_colorbar: bool, grid_only: bool
) -> None:
    """
    Reject --colorbar-label where there is no colour bar to label

    Parameters
    ----------
    colorbar_label : str | None
        Value of --colorbar-label
    no_colorbar : bool
        Value of --no-colorbar
    grid_only : bool
        Value of --grid-only, which colours by no keyword and so has no colour bar

    Raises
    ------
    click.UsageError
        If --colorbar-label is given with --no-colorbar or --grid-only, or its math (text
        between $ signs) is not valid mathtext

    Notes
    -----
    Both backends render math with Matplotlib's mathtext (opm-vis-pv through VTK's MathText,
    which uses it), so laying the label out once here catches a typo in either up front, as a
    clean error - instead of a traceback when Matplotlib saves the figure, or VTK quietly
    logging a warning and drawing the label wrong.
    """
    if colorbar_label is None:
        return
    if no_colorbar:
        raise click.UsageError("--colorbar-label has no colour bar to label with --no-colorbar.")
    if grid_only:
        raise click.UsageError("--colorbar-label has no colour bar to label with --grid-only.")

    if "$" in colorbar_label:
        # Imported here: only needed for a label with math in it
        # pylint: disable=import-outside-toplevel
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        figure = Figure()
        FigureCanvasAgg(figure)
        figure.text(0, 0, colorbar_label)
        try:
            figure.canvas.draw()
        except ValueError as exc:
            raise click.UsageError(
                f"--colorbar-label '{colorbar_label}' has invalid math: "
                f"{str(exc).strip().splitlines()[-1]}"
            ) from exc


FONT_SCALE_OPTION = click.option(
    "--font-scale",
    type=click.FloatRange(min=0, min_open=True),
    default=1.0,
    show_default=True,
    metavar="FACTOR",
    help="Scale every text size by this factor, e.g. 1.5 for 50% bigger text.",
)

CMAP_OPTION = click.option(
    "--cmap", default="viridis", show_default=True, help="Matplotlib colour map name."
)

CLIM_OPTION = click.option(
    "--clim",
    type=(float, float),
    default=None,
    metavar="MIN MAX",
    help="Colour limits. Defaults to the data range of the report step(s) shown.",
)

# --rstep is optional and its shape depends on --animate: a single report step normally, or a
# START:END[:STEP] range for --animate (parsed by parse_rstep below, since click options can't
# have a variable number of values). Left out entirely, a static keyword needs no report step
# at all, and --animate covers every report step in the case.
RSTEP_OR_ANIMATE_OPTIONS = [
    click.option(
        "-r",
        "--rstep",
        default=None,
        metavar="STEP | START:END[:STEP]",
        help=(
            "Report step to plot. A single value normally; a START:END or START:END:STEP range "
            "with --animate (default: every report step in the case). Not needed at all for a "
            "keyword that does not change over time."
        ),
    ),
    click.option(
        "--animate", is_flag=True, default=False, help="Animate over report steps instead."
    ),
    click.option(
        "--fps", type=int, default=3, show_default=True, help="Frames per second for --animate."
    ),
]

# --diff turns on difference mode; --diff-rstep/--diff-kind customize it and are otherwise
# ignored. --diff-rstep is a report step number like --rstep, not a grid index, so it is not
# part of the 1-based -i/-j/-k convention.
DIFF_OPTIONS = [
    click.option(
        "-d",
        "--diff",
        is_flag=True,
        default=False,
        help="Plot the difference from --diff-rstep instead of --keyword's own values.",
    ),
    click.option(
        "--diff-rstep",
        type=int,
        default=0,
        show_default=True,
        metavar="STEP",
        help="Report step to difference against. Only used with --diff.",
    ),
    click.option(
        "--diff-kind",
        type=click.Choice(["plain", "absolute", "relative"]),
        default="plain",
        show_default=True,
        help=(
            "plain: value minus reference. absolute: the plain difference's magnitude. "
            "relative: percent change from the reference. Only used with --diff."
        ),
    ),
]

# -c/--calculator reduces --keyword across a range of grid layers along the sliced dimension,
# from the given -i/-j/-k index to the grid's last layer, instead of using the slice's own
# values; --calc-count limits that range to fewer layers, after the -i/-j/-k index itself, which
# is always included. "mean"/"sum" aggregate every layer in the range; "surface" instead picks
# each position's first active layer from the range's start. Combines with --diff: see
# opm_vis.utils.calc and _SlicePoly.generate()'s notes for what that means.
CALCULATOR_OPTIONS = [
    click.option(
        "-c",
        "--calculator",
        "calc_kind",
        type=click.Choice(CALC_KINDS),
        default=None,
        help="Reduce --keyword across grid layers along the sliced dimension, from the given "
        "-i/-j/-k index to the grid's last layer (or --calc-count further layers). mean/sum "
        "aggregate every layer in that range; surface instead takes each position's first "
        "active layer from the range's start. Requires exactly one of -i/-j/-k.",
    ),
    click.option(
        "--calc-count",
        type=int,
        default=None,
        metavar="N",
        help="Limit --calculator to N further layers after the given -i/-j/-k index, which is "
        "always included itself, instead of continuing to the grid's last layer - e.g. "
        "--calc-count 1 aggregates the given index plus the next one. Only used with "
        "--calculator.",
    ),
]

# --grid-only skips scalar colouring entirely and plots the grid (or a slice of it, for
# opm-vis-mpl always a slice) in a solid colour instead; --keyword is then neither needed nor
# allowed. --grid-color customizes the fill colour, left as None to keep the backend's own
# default.
GRID_ONLY_OPTIONS = [
    click.option(
        "--grid-only",
        is_flag=True,
        default=False,
        help="Plot the grid in a solid colour instead of colouring by --keyword. --keyword "
        "must not be given in this mode.",
    ),
    click.option(
        "--grid-color",
        default=None,
        metavar="COLOR",
        help="Solid fill colour for --grid-only, e.g. a name or hex code. Defaults to the "
        "backend's own fill colour.",
    ),
]

# Draws each cell's outline on top of its fill colour - the two backends take this as a
# different kwarg (show_edges vs. edgecolor), so each CLI translates this flag itself rather
# than a shared helper forcing one shape on both.
SHOW_EDGES_OPTION = click.option(
    "--show-edges",
    is_flag=True,
    default=False,
    help="Draw each cell's outline on top of its fill colour.",
)


def add_options(options: Sequence[Callable]) -> Callable:
    """
    Apply a list of click.option decorators to one command

    Parameters
    ----------
    options : Sequence[Callable]
        click.option (or click.argument) decorators

    Returns
    -------
    Callable
        Decorator applying all of them
    """

    def _add_options(func: Callable) -> Callable:
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


def wants_save(save: bool, save_folder: str | None, save_name: str | None = None) -> bool:
    """
    Whether to save to a file rather than open an interactive window

    Parameters
    ----------
    save : bool
        Value of --save
    save_folder : str | None
        Value of --save-folder, which implies --save
    save_name : str | None, optional
        Value of --save-name, which implies --save, by default None

    Returns
    -------
    bool
        True if any of them was given
    """
    return save or save_folder is not None or save_name is not None


def save_path(
    save_folder: str | None,
    filename: str,
    *,
    folders: Sequence[str],
    default: str,
    save_name: str | None = None,
) -> Path:
    """
    Path to save a figure or animation to, creating its folder if needed

    Parameters
    ----------
    save_folder : str | None
        Value of --save-folder, or None for the default folder
    filename : str
        File name, e.g. as default_output_name generates it
    folders : Sequence[str]
        Value of --folder. The default folder goes inside the first one - the main run's -
        or inside the current folder if none was given
    default : str
        Default folder name, e.g. "pv-figs"
    save_name : str | None, optional
        Value of --save-name, used instead of filename's own name, with filename's suffix
        (e.g. ".png") added unless it already ends with it; by default None, which keeps
        filename

    Returns
    -------
    Path
        save_folder/filename, or folders[0]/default/filename if save_folder is None - with
        save_name + filename's suffix as the file name if save_name is given

    Raises
    ------
    click.UsageError
        If the folder exists as a file instead
    """
    if save_folder is not None:
        folder = Path(save_folder)
    else:
        folder = Path(folders[0] if folders else ".") / default

    if not folder.is_dir():
        try:
            folder.mkdir(parents=True)
        except FileExistsError as exc:
            raise click.UsageError(
                f"Cannot save to {folder}: it exists, but is not a folder."
            ) from exc
        click.echo(f"Created folder {folder}")

    if save_name is not None:
        suffix = Path(filename).suffix
        # A name already ending in the right suffix (e.g. "sgas.png") is not given a second
        # one. Case-sensitive, since PyVista only writes lower-case extensions.
        filename = save_name if save_name.endswith(suffix) else save_name + suffix
    return folder / filename


def resolve_paths(folders: tuple[str, ...]) -> list[str]:
    """
    Find the cases in --folder, falling back to the working directory when none were given

    Parameters
    ----------
    folders : tuple[str, ...]
        Value of --folder

    Returns
    -------
    list[str]
        Case path prefixes of every case in folders, main run first, as find_cases returns
        them

    Raises
    ------
    click.UsageError
        If no case was found in any of the folders
    """
    searched = list(folders) if folders else ["."]
    cases = find_cases(searched)
    if not cases:
        raise click.UsageError(
            f"No simulation case (.EGRID, .INIT, .UNRST, .X, .SMSPEC or .UNSMRY files) found "
            f"in {', '.join(searched)}. Pass the case's folder with -f/--folder."
        )

    return cases


def resolve_case_groups(folders: tuple[str, ...]) -> list[list[str]]:
    """
    Find the cases in each --folder separately, one group per folder

    Parameters
    ----------
    folders : tuple[str, ...]
        Value of --folder

    Returns
    -------
    list[list[str]]
        For each folder, its cases as resolve_paths returns them - one run with its restarts

    Raises
    ------
    click.UsageError
        If a folder has no case
    """
    return [resolve_paths((folder,)) for folder in (folders or (".",))]


def resolve_diff_rstep(diff: bool, diff_rstep: int) -> int | None:
    """
    Resolve --diff/--diff-rstep into the diff_rstep value set_scalars/plot/animate expect

    Parameters
    ----------
    diff : bool
        Value of --diff
    diff_rstep : int
        Value of --diff-rstep

    Returns
    -------
    int | None
        diff_rstep if --diff was given, otherwise None (plot keyword's own values)
    """
    return diff_rstep if diff else None


def resolve_calculator(
    calc_kind: str | None, calc_count: int | None, slices: list[tuple[str, int]]
) -> tuple[str, int] | None:
    """
    Validate --calculator/--calc-count and pick the single slice it aggregates along

    Parameters
    ----------
    calc_kind : str | None
        Value of --calculator
    calc_count : int | None
        Value of --calc-count
    slices : list[tuple[str, int]]
        Every (dim, index) slice given, as resolve_slices() returns them

    Returns
    -------
    tuple[str, int] | None
        None if --calculator was not given; otherwise the single (dim, index) slice to
        aggregate along, i.e. slices[0]

    Raises
    ------
    click.UsageError
        If --calc-count was given without --calculator; if --calculator was given without
        exactly one of -i/-j/-k; or if --calc-count is not a positive integer
    """
    if calc_kind is None:
        if calc_count is not None:
            raise click.UsageError("--calc-count is only valid together with --calculator.")
        return None

    if len(slices) != 1:
        raise click.UsageError(
            "--calculator requires exactly one of -i/-j/-k, to pick which dimension to "
            "aggregate along."
        )

    if calc_count is not None and calc_count < 1:
        raise click.UsageError("--calc-count must be a positive integer.")

    return slices[0]


def resolve_keyword(keyword: str | None, grid_only: bool) -> str | None:
    """
    Validate --keyword/--grid-only are used correctly

    Parameters
    ----------
    keyword : str | None
        Value of --keyword
    grid_only : bool
        Value of --grid-only

    Returns
    -------
    str | None
        keyword unchanged - always a str unless grid_only, since exactly one of the two is
        required

    Raises
    ------
    click.UsageError
        If --grid-only was given together with --keyword, or neither was given at all
    """
    if grid_only and keyword is not None:
        raise click.UsageError("--keyword is not allowed together with --grid-only.")
    if not grid_only and keyword is None:
        raise click.UsageError("Pass --keyword, or --grid-only to plot without colouring it.")

    return keyword


# fnmatch metacharacters. A -K/--keyword value carrying one of these is a pattern to expand
# against the case's own summary vectors; one without is a plain vector name, and gets a "not in
# this case" error rather than a "matched nothing" one - a misspelling and an over-narrow pattern
# need different advice.
_WILDCARD_CHARS = "*?["


def resolve_summary_keywords(
    patterns: Sequence[str], available: Sequence[str]
) -> list[str]:
    """
    Expand every -K/--keyword value against the summary vectors a case actually has

    Parameters
    ----------
    patterns : Sequence[str]
        Values of -K/--keyword: plain vector names, or fnmatch patterns such as "WOPR*"
    available : Sequence[str]
        Every summary vector in the case, as SummaryReader.available_keywords() returns them

    Returns
    -------
    list[str]
        Selected vectors, in the order the patterns were given; each pattern's own matches are
        sorted among themselves, and a vector matched by more than one pattern is kept once

    Raises
    ------
    click.UsageError
        If any pattern matches no summary vector in the case

    Notes
    -----
    fnmatchcase, not fnmatch: fnmatch normalizes the case of both sides, so "-K fopr" would
    match on Windows and not on Linux. Summary mnemonics are upper case, so matching them
    exactly is both portable and unsurprising.
    """
    selected: list[str] = []
    for pattern in patterns:
        matches = sorted(name for name in available if fnmatch.fnmatchcase(name, pattern))
        if not matches:
            if any(char in pattern for char in _WILDCARD_CHARS):
                raise click.UsageError(
                    f"No summary vector matches '{pattern}'. Run --list-keywords to see what "
                    "this case has."
                )
            raise click.UsageError(
                f"{pattern} is not a summary vector in this case. Run --list-keywords to see "
                "what it has."
            )
        selected.extend(match for match in matches if match not in selected)

    return selected


def resolve_subplot_layout(
    layout: tuple[int, int] | None, subplots: bool, n_plots: int
) -> tuple[int, int] | None:
    """
    Validate --layout against --subplots and the number of subplots it has to hold

    Parameters
    ----------
    layout : tuple[int, int] | None
        Value of --layout, as (rows, cols)
    subplots : bool
        Value of --subplots
    n_plots : int
        Number of subplots the grid has to hold, i.e. the number of selected keywords

    Returns
    -------
    tuple[int, int] | None
        layout unchanged, or None to leave the grid shape to the plotter's own near-square
        default

    Raises
    ------
    click.UsageError
        If --layout was given without --subplots, either of its values is below 1, or the grid
        it describes has fewer cells than there are keywords to place in it
    """
    if layout is None:
        return None

    if not subplots:
        raise click.UsageError(
            "--layout only shapes the --subplots grid; pass --subplots, or drop --layout to "
            "draw every keyword in one axes."
        )

    rows, cols = layout
    if rows < 1 or cols < 1:
        raise click.UsageError(
            f"--layout ROWS COLS must both be at least 1; got {rows} {cols}."
        )
    if rows * cols < n_plots:
        raise click.UsageError(
            f"--layout {rows} {cols} has room for {rows * cols} of the {n_plots} keywords "
            "selected; give a larger grid, or fewer -K/--keyword."
        )

    return layout


def check_figsize(figsize: tuple[float, float] | None) -> None:
    """
    Reject a --figsize that Matplotlib cannot draw

    Parameters
    ----------
    figsize : tuple[float, float] | None
        Value of --figsize

    Raises
    ------
    click.UsageError
        If either dimension is zero or negative
    """
    if figsize is not None and (figsize[0] <= 0 or figsize[1] <= 0):
        raise click.UsageError(
            f"--figsize WIDTH HEIGHT must both be positive; got {figsize[0]} {figsize[1]}."
        )


def check_curve_option_count(
    option_name: str, values: Sequence[str], keywords: Sequence[str]
) -> None:
    """
    Validate a --linestyle/--marker-style option was given once, or once per keyword

    Parameters
    ----------
    option_name : str
        Display name of the option, e.g. "--linestyle"
    values : Sequence[str]
        Values given on the command line, in the order given
    keywords : Sequence[str]
        Keywords being plotted, already resolved from -K/--keyword

    Raises
    ------
    click.UsageError
        If more than one value was given and the count does not match the number of keywords

    Notes
    -----
    A single value broadcasts to every keyword - this only rejects a count that is neither 1
    nor len(keywords), e.g. two --linestyle for three keywords, which is ambiguous rather than
    a deliberate choice.
    """
    if len(values) in (0, 1, len(keywords)):
        return

    raise click.UsageError(
        f"{option_name} was given {len(values)} times, but {len(keywords)} keyword(s) were "
        f"selected ({', '.join(keywords)}); give it once to use for all of them, or exactly "
        f"{len(keywords)} times, one per keyword in that order."
    )


def grid_color_kwargs(grid_color: str | None) -> dict:
    """
    Build the fill-colour kwarg for --grid-only, or none at all to keep the backend's default

    Parameters
    ----------
    grid_color : str | None
        Value of --grid-color

    Returns
    -------
    dict
        {} to leave the default fill colour, or {"color": grid_color}
    """
    return {} if grid_color is None else {"color": grid_color}


def resolve_slices(
    slice_i: Sequence[int], slice_j: Sequence[int], slice_k: Sequence[int]
) -> list[tuple[str, int]]:
    """
    Collect every -i/-j/-k value given into a list of (dim, index) slices

    Parameters
    ----------
    slice_i : Sequence[int]
        Values of -i, 1-based
    slice_j : Sequence[int]
        Values of -j, 1-based
    slice_k : Sequence[int]
        Values of -k, 1-based

    Returns
    -------
    list[tuple[str, int]]
        One (dim, index) pair per -i/-j/-k given, grouped by dimension in i/j/k order (the
        order between different dimensions on the command line isn't tracked, only repeats of
        the same option). Empty if none were given at all - callers that need at least one
        (opm-vis-mpl) check for that themselves; opm-vis-pv instead plots the whole grid.
        Indices are converted to 0-based here, since that is what every reader/plotter in
        opm_vis works in internally.

    Raises
    ------
    click.UsageError
        If the same (dim, index) pair was given more than once, or an index was less than 1
    """
    slices = (
        [("i", value) for value in slice_i]
        + [("j", value) for value in slice_j]
        + [("k", value) for value in slice_k]
    )

    invalid = sorted({s for s in slices if s[1] < 1})
    if invalid:
        tags = ", ".join(f"{dim}{index}" for dim, index in invalid)
        raise click.UsageError(
            f"-i/-j/-k indices are 1-based; got {tags}. The first cell along an axis is 1, "
            "not 0."
        )

    duplicates = sorted({s for s in slices if slices.count(s) > 1})
    if duplicates:
        tags = ", ".join(f"{dim}{index}" for dim, index in duplicates)
        raise click.UsageError(f"Slice given more than once: {tags}.")

    return [(dim, index - 1) for dim, index in slices]


@overload
def parse_rstep(raw: str | None, animate: Literal[False]) -> int | None: ...
@overload
def parse_rstep(raw: str | None, animate: Literal[True]) -> tuple[int, int, int] | None: ...
@overload
def parse_rstep(raw: str | None, animate: bool) -> int | tuple[int, int, int] | None: ...
def parse_rstep(raw: str | None, animate: bool) -> int | tuple[int, int, int] | None:
    """
    Parse --rstep, whose shape depends on --animate

    Parameters
    ----------
    raw : str | None
        Raw value of --rstep
    animate : bool
        Value of --animate

    Returns
    -------
    int | tuple[int, int, int] | None
        None if --rstep was not given (caller resolves a default); a single report step if
        --animate is not set; an inclusive (start, end, step) range if --animate is set

    Raises
    ------
    click.UsageError
        If the value's shape does not match whether --animate was given, or it is not made of
        integers
    """
    if raw is None:
        return None

    if not animate:
        if ":" in raw:
            raise click.UsageError(
                "--rstep must be a single report step; a START:END[:STEP] range is only valid "
                "with --animate."
            )
        try:
            return int(raw)
        except ValueError as exc:
            raise click.UsageError(f"--rstep must be an integer, got '{raw}'.") from exc

    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise click.UsageError(
            f"--rstep with --animate must be START:END or START:END:STEP, got '{raw}'."
        )
    try:
        values = [int(part) for part in parts]
    except ValueError as exc:
        raise click.UsageError(f"--rstep values must be integers, got '{raw}'.") from exc

    start, end = values[0], values[1]
    step = values[2] if len(values) == 3 else 1
    if step <= 0:
        raise click.UsageError("--rstep step must be positive.")

    return start, end, step


def resolve_animate_rsteps(
    available_steps: Sequence[int], rstep_range: tuple[int, int, int] | None
) -> list[int]:
    """
    Report steps to animate

    Parameters
    ----------
    available_steps : Sequence[int]
        Every report step the case actually has
    rstep_range : tuple[int, int, int] | None
        (start, end, step) from parse_rstep, or None for every report step

    Returns
    -------
    list[int]
        Report steps to animate, in the case's own order

    Notes
    -----
    Report steps are not necessarily contiguous integers (RPTRST can be set to output at an
    irregular frequency), so start:end:step is used to build the same candidate set
    range(start, end + 1, step) would (matching GridPlotter.animate's own rsteps convention),
    which is then filtered down to the report steps the case actually has.
    """
    if rstep_range is None:
        return list(available_steps)

    start, end, step = rstep_range
    candidates = set(range(start, end + 1, step))
    selected = [rstep for rstep in available_steps if rstep in candidates]
    if not selected:
        raise click.UsageError(f"No report steps in {start}:{end}:{step} found in this case.")

    return selected


def resolve_rstep_selection(available_steps: Sequence[int], raw: str | None) -> list[int]:
    """
    Report steps to list, from a --rstep that is either a single step or a range

    Parameters
    ----------
    available_steps : Sequence[int]
        Every report step the case actually has
    raw : str | None
        Raw value of --rstep: a single report step, a START:END[:STEP] range, or None for
        every report step

    Returns
    -------
    list[int]
        Selected report steps, in the case's own order

    Raises
    ------
    click.UsageError
        If the value is not made of integers, or the case has no report step matching it

    Notes
    -----
    Unlike the plotting commands, where the shape of --rstep follows --animate, a listing
    command accepts either shape at any time - so the branch is picked from the value itself
    and handed to the same parse_rstep/resolve_animate_rsteps pair the plotters use.
    """
    if raw is None:
        return list(available_steps)

    if ":" in raw:
        return resolve_animate_rsteps(available_steps, parse_rstep(raw, animate=True))

    rstep = parse_rstep(raw, animate=False)
    assert rstep is not None  # raw is not None, so parse_rstep(raw, animate=False) is not None
    if rstep not in available_steps:
        raise click.UsageError(f"Report step {rstep} was not found in this case.")

    return [rstep]


def default_output_name(
    keyword: str,
    slices: Sequence[tuple[str, int]],
    *,
    rstep: int | None = None,
    rsteps: Sequence[int] | None = None,
    ext: str = "png",
    diff_rstep: int | None = None,
    diff_kind: str = "plain",
    calc_kind: str | None = None,
    calc_end: int | None = None,
) -> str:
    """
    Build the output file name for --save

    Parameters
    ----------
    keyword : str
        OPM keyword being plotted
    slices : Sequence[tuple[str, int]]
        Every (dim, index) slice being plotted, 0-based as resolve_slices() returns them, or
        empty for the whole grid (opm-vis-pv only)
    rstep : int | None, optional
        Single report step, for a still image
    rsteps : Sequence[int] | None, optional
        Report steps being animated, for --animate
    ext : str, optional
        File extension, by default "png"
    diff_rstep : int | None, optional
        Report step being differenced against, by default None (not a diff plot). See
        resolve_diff_rstep.
    diff_kind : str, optional
        See opm_vis.utils.diff.DIFF_KINDS; only used when diff_rstep is given, by default
        "plain"
    calc_kind : str | None, optional
        See opm_vis.utils.calc.CALC_KINDS, by default None (not a calculator plot). See
        resolve_calculator.
    calc_end : int | None, optional
        0-based index of the calculator's last aggregated layer, by default None (the end
        returned by resolve_calc_range). Only used when calc_kind is given; appended to the
        slice tag as e.g. "k1-3" (1-based, matching the -i/-j/-k index itself) instead of just
        "k1", since --calculator always resolves to exactly one slice.

    Returns
    -------
    str
        e.g. "SGAS_k1_r60.png", "SGAS_k1_j6_r0-120.gif", "SGAS-diff0-absolute_k1_r60.png" with
        --diff, or "SGAS-mean_k1-3_r60.png" with --calculator aggregating layers 1-3, saved in
        --save-folder (see save_path)

    Notes
    -----
    The slice tag is 1-based, matching what the user typed on the command line via -i/-j/-k,
    even though `slices` (and calc_end) are 0-based internally.
    """
    if rsteps is not None:
        step_tag = f"r{rsteps[0]}-{rsteps[-1]}"
    elif rstep is not None:
        step_tag = f"r{rstep}"
    else:
        step_tag = "all"

    if not slices:
        slice_tag = "grid"
    elif calc_kind is not None and calc_end is not None:
        # --calculator requires exactly one of -i/-j/-k; see resolve_calculator
        dim, index = slices[0]
        slice_tag = f"{dim}{index + 1}-{calc_end + 1}"
    else:
        slice_tag = "_".join(f"{dim}{index + 1}" for dim, index in slices)

    keyword_tag = keyword
    if calc_kind is not None:
        keyword_tag += f"-{calc_kind}"
    if diff_rstep is not None:
        keyword_tag += f"-diff{diff_rstep}"
        if diff_kind != "plain":
            keyword_tag += f"-{diff_kind}"

    return f"{keyword_tag}_{slice_tag}_{step_tag}.{ext}"


# At most this many keywords are spelled out in a generated summary file name; beyond that the
# name says how many more there were, so a wildcard matching twenty wells still gives a usable
# file name.
_MAX_NAME_KEYWORDS = 3


def default_summary_output_name(
    keywords: Sequence[str],
    *,
    x_axis: str = "date",
    compare: bool = False,
    ext: str = "png",
) -> str:
    """
    Build the output file name for opm-vis-sum's --save

    Parameters
    ----------
    keywords : Sequence[str]
        Summary vectors being plotted, already expanded by resolve_summary_keywords - never a
        pattern, so no wildcard ever reaches a file name
    x_axis : str, optional
        Value of --x-axis, by default "date"
    compare : bool, optional
        Value of --compare, by default False
    ext : str, optional
        File extension, by default "png"

    Returns
    -------
    str
        e.g. "FOPR_date.png", "WOPR-INJ_WOPR-PROD_years.png", "FOPR_compare_date.png" or
        "FGOR_FOPR_WBHP-INJ_and19more_date.png", saved in --save-folder (see
        save_path)

    Notes
    -----
    A sibling of default_output_name rather than an extension of it: two of that name's three
    parts (slice, report step) do not exist for a time series, and the two this one needs (a
    list of keywords, an x axis) have no place there.

    Summary mnemonics carry ":" and "," separators - WBHP:PROD, BPR:1,1,1 - which make awkward
    file names, and ":" is outright invalid on Windows, so every run of non-alphanumeric
    characters becomes a single "-".

    Only what is plotted goes into the name. --compare does, since it changes which cases are
    read, while --subplots, --layout and the axis limits do not: they change how the same data
    is laid out, not what it is.
    """
    tags = [
        re.sub(r"[^A-Za-z0-9]+", "-", keyword) for keyword in keywords[:_MAX_NAME_KEYWORDS]
    ]
    if len(keywords) > _MAX_NAME_KEYWORDS:
        tags.append(f"and{len(keywords) - _MAX_NAME_KEYWORDS}more")
    if compare:
        tags.append("compare")
    tags.append(x_axis)

    return f"{'_'.join(tags)}.{ext}"


def require_dynamic_keyword_error(keyword: str) -> click.UsageError:
    """
    Build the error for a time-varying keyword shown with neither --rstep nor --animate

    Parameters
    ----------
    keyword : str
        OPM keyword that turned out not to be static

    Returns
    -------
    click.UsageError
        Ready to raise
    """
    return click.UsageError(
        f"{keyword} changes over time; pass --rstep to pick a report step, or --animate to "
        "animate."
    )


def resolve_keyword_rstep(
    keyword: str,
    rstep_value: int | None,
    report_steps: Sequence[int],
    restart_reader: Any,
    init_reader: Any,
) -> int | None:
    """
    Resolve the report step to read keyword at when no --animate was given

    Parameters
    ----------
    keyword : str
        OPM keyword being plotted
    rstep_value : int | None
        Parsed value of --rstep
    report_steps : Sequence[int]
        Every report step in the case's restart files, empty if it has none
    restart_reader : opm_vis.utils.restart.RestartReader
        Restart reader for the case
    init_reader : opm_vis.utils.static.InitReader
        .INIT reader for the case

    Returns
    -------
    int | None
        rstep_value itself if given. Otherwise the case's first report step, once confirmed
        that keyword does not change over time - defaulting silently would hide a keyword
        that actually needs an explicit --rstep. None if the case has no report steps at all
        (only .EGRID/.INIT, e.g. a dry run) and keyword is in its .INIT file, which the
        readers take as "read the .INIT copy"

    Raises
    ------
    click.UsageError
        If rstep_value is None and keyword changes over time, or if the case has no report
        steps and keyword is not in its .INIT file
    """
    if rstep_value is not None:
        return rstep_value

    if not report_steps:
        if keyword in init_reader.available_keywords():
            return None
        raise click.UsageError(
            f"{keyword} is not in the .INIT file, and this case has no restart files (.UNRST "
            "or .X) to read it from. Only .INIT keywords such as PERMX or DEPTH can be "
            "plotted for a case that has not been run."
        )

    probe_rstep = report_steps[0]
    if keyword in restart_reader.available_keywords(probe_rstep):
        raise require_dynamic_keyword_error(keyword)
    return probe_rstep


def matplotlib_font_scale(func: Callable) -> Callable:
    """
    Run a Matplotlib command callback with its text scaled by --font-scale

    Parameters
    ----------
    func : Callable
        Command callback taking a font_scale argument (see FONT_SCALE_OPTION)

    Returns
    -------
    Callable
        Wrapped callback, run inside a Matplotlib rc_context with font.size scaled

    Notes
    -----
    Matplotlib sizes titles, axis labels, ticks, colorbars, legends and annotations relative to
    font.size by default, so scaling that one setting scales every text element together. The
    rc_context restores it afterwards, so it never leaks into another plot in the same process.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Imported here: opm-vis-pv shares this module but does not otherwise need Matplotlib
        import matplotlib as mpl  # pylint: disable=import-outside-toplevel

        scaled = {"font.size": mpl.rcParams["font.size"] * kwargs["font_scale"]}
        with mpl.rc_context(scaled):
            return func(*args, **kwargs)

    return wrapper


def handle_errors(func: Callable) -> Callable:
    """
    Turn the exceptions the readers/plotters raise for bad input into a clean CLI error

    Parameters
    ----------
    func : Callable
        Command callback to wrap

    Returns
    -------
    Callable
        Wrapped callback, raising click.ClickException instead of letting KeyError/ValueError/
        RuntimeError surface as a traceback (e.g. an unknown keyword, a report step not present
        in the restart files, or an empty plotter)
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeyError as exc:
            # KeyError's __str__ reprs its argument, quoting an already-readable message
            raise click.ClickException(exc.args[0] if exc.args else str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper
