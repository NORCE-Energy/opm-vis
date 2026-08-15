""" Report dates and time since simulation start, as data and as printable tables """
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from collections.abc import Iterable, Sequence
from typing import Any

# OPM's YEARS summary vector is TIME/365.25, so elapsed years here use the same convention and
# can be compared directly against it (verified on tests/data/SPE1CASE1: TIME/YEARS == 365.25).
DAYS_PER_YEAR = 365.25

# "table": aligned columns for reading. "csv"/"json": machine-readable, with ISO-8601 dates.
TIMELINE_FORMATS = ("table", "csv", "json")

# Dates are shown as dd.mm.yyyy in the table, matching the plot titles and file name tags in
# opm_vis.pvplot/opm_vis.plot, but as ISO-8601 in csv/json, where an unambiguous, sortable date
# matters more than matching the plots.
_TABLE_DATE_FORMAT = "%d.%m.%Y"
_ISO_DATE_FORMAT = "%Y-%m-%d"

_HEADERS = ("Report step", "Date", "Days", "Years")
_FIELDS = ("rstep", "date", "days", "years")


def timeline_entries(
    rsteps: Sequence[int],
    rdates: Sequence[dt.datetime],
    rstep_filter: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Pair report steps with their dates and time since the start of the simulation

    Parameters
    ----------
    rsteps : Sequence[int]
        Report steps, in the case's own order (as Report.report_steps() returns them)
    rdates : Sequence[dt.datetime]
        Report date for each entry of rsteps, in the same order
    rstep_filter : Iterable[int] | None, optional
        Report steps to keep. Entries that the case does not have are ignored. If None (the
        default), every report step is kept.

    Returns
    -------
    list[dict[str, Any]]
        One dict per report step, in the case's own order, with keys "rstep" (int), "date"
        (dt.datetime), "days" (int) and "years" (float)

    Raises
    ------
    ValueError
        If rsteps is empty (no restart files were read), or if rsteps and rdates have
        different lengths

    Notes
    -----
    Time zero is the first entry of rdates: report step 0 is written at the start of the run,
    so its date is the deck's START. Filtering does not move time zero - elapsed times are
    always measured from the case's first report date, whether or not it is in the selection.

    Elapsed time is a whole number of days because report dates are: they come from the
    INTEHEAD record, which Report reads at day resolution (see
    Report._report_dates_and_steps). Years are those days divided by DAYS_PER_YEAR.

    A main run and a restart run of it overlap at the step the restart branches from, so the
    same report step can appear twice in rsteps. Only its first occurrence is kept, which is
    the one Report.report_date() and RestartReader.read() resolve to as well.
    """
    if not rsteps:
        raise ValueError("No report steps found; cannot build a timeline!")
    if len(rsteps) != len(rdates):
        raise ValueError(
            f"Got {len(rsteps)} report steps but {len(rdates)} report dates; they must match!"
        )

    start = rdates[0]
    wanted = None if rstep_filter is None else set(rstep_filter)

    entries = []
    seen: set[int] = set()
    for rstep, rdate in zip(rsteps, rdates):
        if wanted is not None and rstep not in wanted:
            continue
        if rstep in seen:
            continue
        seen.add(rstep)

        days = (rdate - start).days
        entries.append(
            {
                "rstep": rstep,
                "date": rdate,
                "days": days,
                "years": days / DAYS_PER_YEAR,
            }
        )

    return entries


def format_timeline(entries: Sequence[dict[str, Any]], fmt: str = "table") -> str:
    """
    Render timeline entries as a printable table, CSV or JSON

    Parameters
    ----------
    entries : Sequence[dict[str, Any]]
        Timeline entries, as timeline_entries() returns them
    fmt : str, optional
        One of TIMELINE_FORMATS: "table" (aligned columns, dd.mm.yyyy dates), "csv" or "json"
        (both with ISO-8601 dates). Default is "table".

    Returns
    -------
    str
        The rendered timeline, without a trailing newline

    Raises
    ------
    ValueError
        If fmt is not one of TIMELINE_FORMATS
    """
    if fmt not in TIMELINE_FORMATS:
        raise ValueError(f"fmt must be one of {TIMELINE_FORMATS}, got {fmt!r}")

    if fmt == "table":
        return _format_table(entries)
    if fmt == "csv":
        return _format_csv(entries)
    return _format_json(entries)


def _format_table(entries: Sequence[dict[str, Any]]) -> str:
    """
    Render timeline entries as right-aligned columns

    Parameters
    ----------
    entries : Sequence[dict[str, Any]]
        Timeline entries, as timeline_entries() returns them

    Returns
    -------
    str
        Header line followed by one line per entry, without a trailing newline

    Notes
    -----
    Column widths are computed from the values actually shown (and never fall below the header
    width), so a case with four-digit report steps or a long run stays aligned.
    """
    rows = [
        (
            str(entry["rstep"]),
            entry["date"].strftime(_TABLE_DATE_FORMAT),
            str(entry["days"]),
            f"{entry['years']:.3f}",
        )
        for entry in entries
    ]

    widths = [
        max(len(header), *(len(row[i]) for row in rows)) if rows else len(header)
        for i, header in enumerate(_HEADERS)
    ]

    lines = ["  ".join(head.rjust(width) for head, width in zip(_HEADERS, widths))]
    lines += [
        "  ".join(value.rjust(width) for value, width in zip(row, widths)) for row in rows
    ]

    return "\n".join(lines)


def _format_csv(entries: Sequence[dict[str, Any]]) -> str:
    """
    Render timeline entries as CSV

    Parameters
    ----------
    entries : Sequence[dict[str, Any]]
        Timeline entries, as timeline_entries() returns them

    Returns
    -------
    str
        Header row followed by one row per entry, without a trailing newline

    Notes
    -----
    Written through the csv module with an explicit "\\n" line terminator, so the output is the
    same on every platform rather than picking up "\\r\\n" on Windows.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_FIELDS)
    for entry in entries:
        writer.writerow(
            [
                entry["rstep"],
                entry["date"].strftime(_ISO_DATE_FORMAT),
                entry["days"],
                f"{entry['years']:.6f}",
            ]
        )

    return buffer.getvalue().rstrip("\n")


def _format_json(entries: Sequence[dict[str, Any]]) -> str:
    """
    Render timeline entries as a JSON array

    Parameters
    ----------
    entries : Sequence[dict[str, Any]]
        Timeline entries, as timeline_entries() returns them

    Returns
    -------
    str
        Indented JSON array of objects with the same keys as the entries, dates as ISO-8601
        strings
    """
    return json.dumps(
        [
            {
                "rstep": entry["rstep"],
                "date": entry["date"].strftime(_ISO_DATE_FORMAT),
                "days": entry["days"],
                "years": round(entry["years"], 6),
            }
            for entry in entries
        ],
        indent=2,
    )
