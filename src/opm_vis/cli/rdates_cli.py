"""opm-vis-rdates: list report dates and time since simulation start"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
    FOLDER_OPTION,
    handle_errors,
    resolve_paths,
    resolve_rstep_selection,
)
from opm_vis.utils.restart import Report
from opm_vis.utils.timeline import TIMELINE_FORMATS


# COMMAND_SETTINGS is deliberately not used here: its no_args_is_help only makes sense for the
# plotting commands, which have nothing to do without a --keyword. Run bare in a case
# directory, this command has an obvious job - list that case's report dates.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@FOLDER_OPTION
@click.option(
    "-r",
    "--rstep",
    default=None,
    metavar="STEP | START:END[:STEP]",
    help="Report step, or range of report steps, to list. Default: every report step.",
)
@click.option(
    "-F",
    "--format",
    "fmt",
    type=click.Choice(TIMELINE_FORMATS),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--save",
    "-s",
    "save",
    default=None,
    metavar="PATH",
    help="Write the output to a file instead of printing it.",
)
@handle_errors
def main(folders: tuple[str, ...], rstep: str | None, fmt: str, save: str | None) -> None:
    """
    List the report steps in a case with their dates and the time since the simulation started.

    The case is found in -f/--folder, by default the current folder. Several cases found
    there are read as one run: the main run followed by its restarts.

    Dates are read from the restart files (.UNRST/.X), at day resolution - no summary file is
    needed. Elapsed time is measured from the first report step, in days and in years (365.25
    days), matching the TIME and YEARS summary vectors.

    See the documentation for the full option reference with examples.
    """
    report = Report(resolve_paths(folders))
    rsteps = resolve_rstep_selection(report.report_steps(), rstep)
    output = report.format_timeline(fmt, rsteps)

    if save is None:
        click.echo(output)
    else:
        Path(save).write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
