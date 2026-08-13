"""Click options and helpers shared by opm-vis-pv and opm-vis-mpl"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import wraps
from pathlib import Path
from typing import Any

import click

# Show the help page both on -h/--help and when the command is run with nothing at all: with
# PATHS defaulting to the working directory and --rstep optional for static keywords, a bare
# invocation has no other useful thing to do.
COMMAND_SETTINGS = {
    "context_settings": {"help_option_names": ["-h", "--help"]},
    "no_args_is_help": True,
}

# Paths are filename prefixes, not directories: the first entry is the main run, any further
# entries are restart runs. See README.md and every reader in opm_vis.utils/opm_vis.pvplot.
# Optional: resolve_paths() below searches the working directory when none are given.
PATHS_ARGUMENT = click.argument("paths", nargs=-1, required=False)

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
# instead, either an explicit PATH or (given with no value) a name generated from the keyword,
# slice and report step(s). This is click's "option with an optional value" mechanism: the
# three observable states are None (not given), "" (given with no value) and a path string.
SAVE_OPTION = click.option(
    "--save",
    "-s",
    is_flag=False,
    flag_value="",
    default=None,
    metavar="[PATH]",
    help=(
        "Save to file instead of opening an interactive window. If PATH is omitted, a name is "
        "generated from the keyword, slice and report step(s)."
    ),
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


def resolve_paths(paths: tuple[str, ...]) -> list[str]:
    """
    Fall back to searching the working directory when no paths were given

    Parameters
    ----------
    paths : tuple[str, ...]
        Value of the PATHS argument

    Returns
    -------
    list[str]
        paths itself if non-empty, otherwise ["./"]
    """
    return list(paths) if paths else ["./"]


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


def default_output_name(
    keyword: str,
    slices: Sequence[tuple[str, int]],
    *,
    rstep: int | None = None,
    rsteps: Sequence[int] | None = None,
    ext: str = "png",
    diff_rstep: int | None = None,
    diff_kind: str = "plain",
) -> str:
    """
    Build an output filename when --save is given with no path

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

    Returns
    -------
    str
        e.g. "SGAS_k1_60.png", "SGAS_k1_j6_0-120.gif", or "SGAS-diff0-absolute_k1_60.png"
        with --diff, written to the current directory

    Notes
    -----
    The slice tag is 1-based, matching what the user typed on the command line via -i/-j/-k,
    even though `slices` itself is 0-based internally.
    """
    if rsteps is not None:
        step_tag = f"{rsteps[0]}-{rsteps[-1]}"
    elif rstep is not None:
        step_tag = str(rstep)
    else:
        step_tag = "all"

    slice_tag = "_".join(f"{dim}{index + 1}" for dim, index in slices) if slices else "grid"

    keyword_tag = keyword
    if diff_rstep is not None:
        keyword_tag += f"-diff{diff_rstep}"
        if diff_kind != "plain":
            keyword_tag += f"-{diff_kind}"

    return f"{keyword_tag}_{slice_tag}_{step_tag}.{ext}"


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


def is_static_keyword(restart_reader: Any, keyword: str, probe_rstep: int) -> bool:
    """
    Check whether a keyword only exists in the .INIT file, i.e. never changes over time

    Parameters
    ----------
    restart_reader : opm_vis.utils.restart.RestartReader
        Restart reader for the case
    keyword : str
        OPM keyword
    probe_rstep : int
        Report step to check availability at; any report step gives the same answer for a
        genuinely static keyword

    Returns
    -------
    bool
        True if the keyword is absent from the restart files at probe_rstep
    """
    return keyword not in restart_reader.available_keywords(probe_rstep)


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
