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
    "--keyword", required=True, help="OPM keyword to plot, e.g. SGAS or PRESSURE."
)

# -i/-j/-k replace the old --slice-dim/--slice-index pair: at least one is given, and its
# value is the index of the slice on that dimension. Each is repeatable (-k 0 -k 5 -j 2) so
# several slices can be plotted together; this is also why --keyword lost its -k short form.
SLICE_OPTIONS = [
    click.option(
        "-i",
        "--i-index",
        "slice_i",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the i dimension at this index. Repeatable.",
    ),
    click.option(
        "-j",
        "--j-index",
        "slice_j",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the j dimension at this index. Repeatable.",
    ),
    click.option(
        "-k",
        "--k-index",
        "slice_k",
        type=int,
        multiple=True,
        metavar="INDEX",
        help="Slice on the k dimension at this index. Repeatable.",
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

# --rstep is optional and its shape depends on --gif: a single report step normally, or a
# START:END[:STEP] range for --gif (parsed by parse_rstep below, since click options can't have
# a variable number of values). Left out entirely, a static keyword needs no report step at all,
# and --gif covers every report step in the case.
RSTEP_OR_GIF_OPTIONS = [
    click.option(
        "--rstep",
        default=None,
        metavar="STEP | START:END[:STEP]",
        help=(
            "Report step to plot. A single value normally; a START:END or START:END:STEP range "
            "with --gif (default: every report step in the case). Not needed at all for a "
            "keyword that does not change over time."
        ),
    ),
    click.option(
        "--gif", is_flag=True, default=False, help="Animate over report steps instead."
    ),
    click.option(
        "--fps", type=int, default=3, show_default=True, help="Frames per second for --gif."
    ),
]


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


def resolve_slices(
    slice_i: Sequence[int], slice_j: Sequence[int], slice_k: Sequence[int]
) -> list[tuple[str, int]]:
    """
    Collect every -i/-j/-k value given into a list of (dim, index) slices

    Parameters
    ----------
    slice_i : Sequence[int]
        Values of -i
    slice_j : Sequence[int]
        Values of -j
    slice_k : Sequence[int]
        Values of -k

    Returns
    -------
    list[tuple[str, int]]
        One (dim, index) pair per -i/-j/-k given, at least one, grouped by dimension in i/j/k
        order (the order between different dimensions on the command line isn't tracked, only
        repeats of the same option)

    Raises
    ------
    click.UsageError
        If none were given, or the same (dim, index) pair was given more than once
    """
    slices = (
        [("i", value) for value in slice_i]
        + [("j", value) for value in slice_j]
        + [("k", value) for value in slice_k]
    )
    if not slices:
        raise click.UsageError("Pass at least one of -i, -j, or -k to select a slice.")

    duplicates = sorted({s for s in slices if slices.count(s) > 1})
    if duplicates:
        tags = ", ".join(f"{dim}{index}" for dim, index in duplicates)
        raise click.UsageError(f"Slice given more than once: {tags}.")

    return slices


def parse_rstep(raw: str | None, gif: bool) -> int | tuple[int, int, int] | None:
    """
    Parse --rstep, whose shape depends on --gif

    Parameters
    ----------
    raw : str | None
        Raw value of --rstep
    gif : bool
        Value of --gif

    Returns
    -------
    int | tuple[int, int, int] | None
        None if --rstep was not given (caller resolves a default); a single report step if
        --gif is not set; an inclusive (start, end, step) range if --gif is set

    Raises
    ------
    click.UsageError
        If the value's shape does not match whether --gif was given, or it is not made of
        integers
    """
    if raw is None:
        return None

    if not gif:
        if ":" in raw:
            raise click.UsageError(
                "--rstep must be a single report step; a START:END[:STEP] range is only valid "
                "with --gif."
            )
        try:
            return int(raw)
        except ValueError as exc:
            raise click.UsageError(f"--rstep must be an integer, got '{raw}'.") from exc

    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise click.UsageError(
            f"--rstep with --gif must be START:END or START:END:STEP, got '{raw}'."
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


def resolve_gif_rsteps(
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
) -> str:
    """
    Build an output filename when --save is given with no path

    Parameters
    ----------
    keyword : str
        OPM keyword being plotted
    slices : Sequence[tuple[str, int]]
        Every (dim, index) slice being plotted
    rstep : int | None, optional
        Single report step, for a still image
    rsteps : Sequence[int] | None, optional
        Report steps being animated, for a gif
    ext : str, optional
        File extension, by default "png"

    Returns
    -------
    str
        e.g. "SGAS_k0_60.png" or "SGAS_k0_j5_0-120.gif", written to the current directory
    """
    if rsteps is not None:
        step_tag = f"{rsteps[0]}-{rsteps[-1]}"
    elif rstep is not None:
        step_tag = str(rstep)
    else:
        step_tag = "all"

    slice_tag = "_".join(f"{dim}{index}" for dim, index in slices)

    return f"{keyword}_{slice_tag}_{step_tag}.{ext}"


def require_dynamic_keyword_error(keyword: str) -> click.UsageError:
    """
    Build the error for a time-varying keyword shown with neither --rstep nor --gif

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
        f"{keyword} changes over time; pass --rstep to pick a report step, or --gif to animate."
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
