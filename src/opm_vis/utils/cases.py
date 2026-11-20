""" Locate simulation cases and their output files on disk """
from __future__ import annotations

import os
import re
import warnings
from glob import escape, glob
from pathlib import Path

from opm.io.ecl import ERst, ESmry

# Output files that make a file stem a simulation case. Include files (.INC, .GRDECL, ...) and
# the .DATA deck itself are left out: they say nothing about whether a case has been run.
_CASE_FILE = re.compile(r"\.(EGRID|INIT|UNRST|SMSPEC|UNSMRY|X\d{4})$")

# Glob suffix standing in for ".X" in case_files: one file per report step, .X0000 onward
_X_SUFFIX = ".X[0-9][0-9][0-9][0-9]"


def case_files(path: str, ext: str) -> list[str]:
    """
    Find a case's files with the given extension

    Parameters
    ----------
    path : str
        Case path prefix, e.g. "run/CASE" for run/CASE.EGRID, run/CASE.UNRST, ... Can also be
        a directory, which matches every file with that extension in it
    ext : str
        Extension including the dot, e.g. ".EGRID". ".X" matches the per-report-step
        .X0000-style restart files

    Returns
    -------
    list[str]
        Matching files, sorted

    Notes
    -----
    A prefix matches its own case exactly: "run/CASE" finds run/CASE.UNRST but not
    run/CASE_RESTART.UNRST, so a main run and its restarts can share one folder.
    """
    suffix = _X_SUFFIX if ext == ".X" else escape(ext)
    if os.path.isdir(path):
        pattern = os.path.join(escape(path), "*" + suffix)
    else:
        pattern = escape(path) + suffix

    return sorted(glob(pattern))


def find_cases(folders: list[str]) -> list[str]:
    """
    Find every simulation case in one or more folders, ordered as a main run and its restarts

    Parameters
    ----------
    folders : list[str]
        Directories to search. Every case in all of them is taken as part of the same run

    Returns
    -------
    list[str]
        Case path prefixes (folder/CASE), main run first; see order_cases. Empty if no folder
        has any

    Raises
    ------
    NotADirectoryError
        If one of folders is not a directory
    """
    cases: dict[str, None] = {}
    for folder in folders:
        if not os.path.isdir(folder):
            raise NotADirectoryError(f"{folder} is not a directory!")

        stems = sorted(
            _CASE_FILE.sub("", entry.name)
            for entry in os.scandir(folder)
            if entry.is_file() and _CASE_FILE.search(entry.name)
        )
        # Keyed on the resolved path so the same folder given twice adds its cases once
        for stem in stems:
            cases.setdefault(os.path.join(os.path.normpath(folder), stem), None)

    return order_cases(list(cases))


def order_cases(cases: list[str]) -> list[str]:
    """
    Order cases as a main run followed by its restart runs

    Parameters
    ----------
    cases : list[str]
        Case path prefixes, as find_cases returns them

    Returns
    -------
    list[str]
        cases sorted by where each one starts: its first report step if every case has
        restart files, else its first summary TIME if every case has summary files, else by
        name alone. Cases that start at the same point are ordered by name

    Notes
    -----
    A restart run begins where it restarted from, so it starts later than the run it
    continues. Report steps and summary times are not comparable with each other, so one of
    them is used for every case or neither is.
    """
    keys: dict[str, float] = {}
    for starts in (_first_report_step, _first_summary_time):
        found = {case: starts(case) for case in cases}
        if all(start is not None for start in found.values()):
            keys = {case: start for case, start in found.items() if start is not None}
            break

    ordered = sorted(cases, key=lambda case: (keys.get(case, 0.0), Path(case).name))

    if keys:
        for first, second in zip(ordered, ordered[1:]):
            if keys[first] == keys[second]:
                warnings.warn(
                    f"{first} and {second} start at the same point, so which one restarts "
                    "the other is unclear. Ordering them by name."
                )

    return ordered


def _first_report_step(case: str) -> float | None:
    """
    Report step a case's restart files start at, or None if it has none
    """
    unrst_files = case_files(case, ".UNRST")
    if unrst_files:
        report_steps = ERst(unrst_files[0]).report_steps
        return report_steps[0] if report_steps else None

    x_files = case_files(case, ".X")
    return int(x_files[0][-4:]) if x_files else None


def _first_summary_time(case: str) -> float | None:
    """
    First summary TIME (days) of a case, or None if it has no summary files
    """
    smspec_files = case_files(case, ".SMSPEC")
    if not smspec_files:
        return None

    time = ESmry(smspec_files[0])["TIME"]
    return float(time[0]) if len(time) else None
