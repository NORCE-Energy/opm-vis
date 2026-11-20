""" Calculate various attributes from restart files """
from __future__ import annotations

import datetime as dt
import warnings
from collections.abc import Iterable
from typing import Any, Iterator

import numpy as np
from numpy.typing import NDArray
from opm.io.ecl import EclFile, ERst

from opm_vis.utils.cases import case_files
from opm_vis.utils.timeline import DAYS_PER_YEAR
from opm_vis.utils.timeline import format_timeline as _format_timeline
from opm_vis.utils.timeline import timeline_entries as _timeline_entries


_IGNORE = frozenset(
    {
        "INTEHEAD",
        "LOGIHEAD",
        "DOUBHEAD",
        "IGRP",
        "SGRP",
        "XGRP",
        "ZGRP",
        "IWEL",
        "SWEL",
        "XWEL",
        "ZWEL",
        "ZWLS",
        "IWLS",
        "ICON",
        "SCON",
        "XCON",
        "STARTSOL",
        "ENDSOL",
    }
)

# XWEL items with well rates: oil, water, gas and reservoir voidage. Injection is stored as
# negative production rates, so these cover both producers and injectors.
_XWEL_RATES = [0, 1, 2, 4]


# pylint: disable=too-few-public-methods
class _RestartFiles:
    """
    Top class for ERst wrapper
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Init. class by instantiating ERst classes for each restart file in input folders

        Parameters
        ----------
        paths : list[str]
            List of paths with restart files. Main folder is in paths[0]; rest of entries, if any,
            are folders with simulator restart runs.
        """
        # Kept for RestartReader.unit_convention()'s .INIT fallback, which needs the main run's
        # own path prefix (paths[0]) to look for a .INIT file once no restart data exists yet.
        self._paths = paths

        # Instantiate OPM restart class. Need to search paths for .UNRST or .X files
        self.rst = []
        for path in paths:
            # Init. restart file list for current search path
            restart_files = []

            unrst_files = case_files(path, ".UNRST")
            x_files = case_files(path, ".X")

            # Are there UNRST and X files in same folder? We load the UNRST file and issue warning
            if unrst_files and x_files:
                warnings.warn(
                    f"There are .UNRST and .X files in {path}. We load the UNRST file!"
                )
                if len(unrst_files) > 1:
                    warnings.warn(
                        f"Multiple .UNRST files in {path}. Importing {unrst_files[0]}."
                    )
                restart_files = [unrst_files[0]]

            # Are there no files in the folder? Warn and continue
            elif not unrst_files and not x_files:
                warnings.warn(f"No .UNRST or .X files found {path}! Skipping folder...")

            # .UNRST file
            elif unrst_files and not x_files:
                if len(unrst_files) > 1:
                    warnings.warn(
                        f"Multiple .UNRST files in {path}. Importing {unrst_files[0]}"
                    )
                restart_files = [unrst_files[0]]

            # .X files
            elif not unrst_files and x_files:
                restart_files = x_files

            # Instantiate ERst class for each file in path
            if restart_files:
                self.rst.extend([ERst(file) for file in restart_files])

        # Build a lookup from report step to its (erst index, local index within that erst) and
        # the absolute offset of each erst's report steps in a flattened list. erst.report_steps
        # is a property that recomputes on every access, so we read it once per erst here and
        # reuse it everywhere else instead of re-querying and re-scanning it on every lookup.
        self._step_index: dict[int, tuple[int, int]] = {}
        self._erst_step_offsets: list[int] = []
        offset = 0
        for erst_idx, erst in enumerate(self.rst):
            self._erst_step_offsets.append(offset)
            report_steps = erst.report_steps
            for local_idx, rstep in enumerate(report_steps):
                self._step_index.setdefault(rstep, (erst_idx, local_idx))
            offset += len(report_steps)


class RestartReader(_RestartFiles):
    """
    Class for reading info from restart files. Initialization in parent class.
    """

    def read(
        self, keyword: str, rstep: int, act: list[int] | None = None
    ) -> NDArray[Any]:
        """
        Read restart file at report step and return array for active indices.

        Parameters
        ----------
        keyword : str
            OPM keyword (must exist in restart file, i.e., either be one of the default outputs or
            inputed in RST-type mnemonics).
        rstep : int
            Report step.
        act : list[int] | None, optional
            Active indices for output array. If act=None, whole array is outputted.

        Returns
        -------
        out : ndarray
            Array with keyword variables at report step.
        """
        # Look up which restart file holds the requested report step
        location = self._step_index.get(rstep)
        if location is None:
            raise ValueError(f"Report step {rstep} was not found in restart files!")

        erst_idx, _ = location
        out = self.rst[erst_idx][(keyword, rstep)]
        return out[act] if act is not None else out

    def available_keywords(self, rstep: int) -> list[str]:
        """
        Available keyword at report step

        Parameters
        ----------
        rstep : int
            Report step

        Returns
        -------
        list[str]
            List of available keywords
        """
        # Look up which restart file holds the requested report step
        location = self._step_index.get(rstep)
        if location is None:
            raise ValueError(f"Report step {rstep} was not found in restart file(s)!")

        erst_idx, _ = location
        return [
            key[0] for key in self.rst[erst_idx].arrays(rstep) if key[0] not in _IGNORE
        ]

    def intehead(self, item: int, rstep: int) -> int:
        """
        Lookup INTEHEAD information in restart file(s)

        Parameters
        ----------
        item : int
            Requested item in INTEHEAD
        rstep : int
            Report step

        Returns
        -------
        info : int
            Information from header
        """
        # Look up which restart file holds the requested report step
        location = self._step_index.get(rstep)
        if location is None:
            raise ValueError(f"INTEHEAD item {item} not found in restart file(s)!")

        erst_idx, _ = location
        return self.rst[erst_idx][("INTEHEAD", rstep)][item]

    def unit_convention(self) -> str:
        """
        Return the unit convention used in the run

        Returns
        -------
        str
            One of 'metric', 'field', 'lab' or 'pvt-m'

        Raises
        ------
        ValueError
            If item 2 of INTEHEAD could not be found in either the restart files or the main
            run's .INIT file

        Notes
        -----
        Falls back to the main run's .INIT file when report step 0 has no restart data - e.g. a
        dry run that has only been initialized, with no .UNRST/.X files yet. INTEHEAD's own
        unit-convention item does not change between the two, and a case that got far enough to
        write a .INIT file always has one, well before it has any restart data.
        """
        try:
            item = self.intehead(2, 0)
        except ValueError:
            item = self._intehead_from_init(2)
        return ["metric", "field", "lab", "pvt-m"][item - 1]

    def _intehead_from_init(self, item: int) -> int:
        """
        Fallback for unit_convention(): read one INTEHEAD item from the main run's .INIT file

        Parameters
        ----------
        item : int
            Requested item in INTEHEAD

        Returns
        -------
        int
            Information from header

        Raises
        ------
        ValueError
            If no .INIT file was found for the main run

        Notes
        -----
        Reads through the raw EclFile interface rather than opm.util.EModel (used elsewhere for
        .INIT data, e.g. opm_vis.utils.static.InitReader): EModel is scoped to per-active-cell
        arrays and does not expose header arrays like INTEHEAD at all.
        """
        init_files = case_files(self._paths[0], ".INIT")
        if not init_files:
            raise ValueError(
                f"INTEHEAD item {item} not found in restart file(s), and no .INIT file was "
                f"found in {self._paths[0]} to fall back to!"
            )
        if len(init_files) > 1:
            warnings.warn(
                f"Multiple .INIT files in {self._paths[0]}. Importing {init_files[0]}."
            )

        return EclFile(init_files[0])["INTEHEAD"][item]


class Report(_RestartFiles):
    """
    Class to organize and handle report dates/steps from restart files
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Initialize by organizing report steps and dates.

        Parameters
        ----------
        paths : list[str]
            List of paths with restart files. Main folder is in paths[0]; rest of entries, if any,
            are folders with simulator restart runs.
        """
        # Instantiate Erst class for restart files using parent class
        super().__init__(paths)

        # Extract report dates and report steps from restart files
        self._report_dates_and_steps()

    def _report_dates_and_steps(self) -> None:
        """
        Organize report steps and dates from restart files.
        """
        # Read report steps and associated dates from the restart file(s). The date is stored in
        # INTEHEAD record, items 65 - 67 (note, Python indexing in code below).
        # OBS: we ignore hours, minutes and seconds here, but for future reference they are located
        # in items 207, 208 and 411, respectively.
        self.rsteps = []
        self.rdates = []
        for erst in self.rst:
            # Report steps in current file, which we also add to list of all report steps
            rsteps_unrst = erst.report_steps
            self.rsteps += rsteps_unrst

            # Loop over report steps and get report dates as datetime object
            for rstep in rsteps_unrst:
                intehead = erst[("INTEHEAD", rstep)]
                self.rdates.extend(
                    [
                        dt.datetime(
                            day=intehead[64],
                            month=intehead[65],
                            year=intehead[66],
                        )
                    ]
                )

        # Sort report dates in ascending order of report steps (in case restart files list is
        # not in ordered)
        # Index list of sorted rsteps
        ind_sort = sorted(range(len(self.rsteps)), key=self.rsteps.__getitem__)

        # Apply sorting to both report dates and steps
        self.rsteps = [self.rsteps[i] for i in ind_sort]
        self.rdates = [self.rdates[i] for i in ind_sort]

        # Lookup for report_date() so repeated calls don't rescan self.rsteps
        self._rstep_to_date: dict[int, dt.datetime] = {}
        for rstep, rdate in zip(self.rsteps, self.rdates):
            self._rstep_to_date.setdefault(rstep, rdate)

    def __str__(self) -> str:
        """
        Print a table of report steps, dates and time since simulation start

        Returns
        -------
        str
            Table with columns report step // date // days // years
        """
        return self.format_timeline()

    def report_date(self, rstep: int) -> dt.datetime:
        """
        Return report date at on report step

        Parameters
        ----------
        rstep : int
            Report step

        Returns
        -------
        dt.datetime
            Datetime object for report step
        """
        return self._rstep_to_date[rstep]

    def report_dates(self) -> list[dt.datetime]:
        """
        Return report dates

        Returns
        -------
        list[dt.datetime]
            List of report dates as datetime objects
        """
        return self.rdates

    def report_steps(self) -> list[int]:
        """
        Return report steps

        Returns
        -------
        list[int]
            List of report steps
        """
        return self.rsteps

    def start_date(self) -> dt.datetime:
        """
        Return the date the simulation started

        Returns
        -------
        dt.datetime
            Date of the first report step

        Raises
        ------
        ValueError
            If no report steps were read, i.e. no restart files were found

        Notes
        -----
        This is the earliest report date across all given paths. Report step 0 is written at
        the start of the run, so for a normal case it is the deck's START date. Given only a
        restart run's own path, it is instead the date that run restarted from.
        """
        if not self.rdates:
            raise ValueError("No report steps found; cannot determine the start date!")

        return self.rdates[0]

    def elapsed_days(self, rstep: int) -> int:
        """
        Return days from the start of the simulation to a report step

        Parameters
        ----------
        rstep : int
            Report step

        Returns
        -------
        int
            Whole days since start_date()

        Notes
        -----
        Report dates are read at day resolution (see _report_dates_and_steps), so the elapsed
        time is a whole number of days. This is the same quantity as the TIME summary vector.
        """
        return (self.report_date(rstep) - self.start_date()).days

    def elapsed_years(self, rstep: int) -> float:
        """
        Return years from the start of the simulation to a report step

        Parameters
        ----------
        rstep : int
            Report step

        Returns
        -------
        float
            Years since start_date(), i.e. elapsed_days() divided by DAYS_PER_YEAR (365.25),
            the same convention as the YEARS summary vector
        """
        return self.elapsed_days(rstep) / DAYS_PER_YEAR

    def timeline(self, rsteps: list[int] | None = None) -> list[dict[str, Any]]:
        """
        Return report steps with their dates and time since simulation start

        Parameters
        ----------
        rsteps : list[int] | None, optional
            Report steps to include. If None (the default), every report step is included.

        Returns
        -------
        list[dict[str, Any]]
            One dict per report step, with keys "rstep", "date", "days" and "years"; see
            opm_vis.utils.timeline.timeline_entries

        Raises
        ------
        ValueError
            If no report steps were read, i.e. no restart files were found
        """
        return _timeline_entries(self.rsteps, self.rdates, rsteps)

    def format_timeline(self, fmt: str = "table", rsteps: list[int] | None = None) -> str:
        """
        Render the timeline as a printable table, CSV or JSON

        Parameters
        ----------
        fmt : str, optional
            One of opm_vis.utils.timeline.TIMELINE_FORMATS: "table" (the default), "csv" or
            "json"
        rsteps : list[int] | None, optional
            Report steps to include. If None (the default), every report step is included.

        Returns
        -------
        str
            The rendered timeline, without a trailing newline

        Raises
        ------
        ValueError
            If no report steps were read, or if fmt is not a known format
        """
        return _format_timeline(self.timeline(rsteps), fmt)


class Wells(_RestartFiles):
    """
    Well information from restart files
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Initialize by extracting all well information from restart files.

        Parameters
        ----------
        paths : list[str]
            List of paths with restart files. Main folder is in paths[0]; rest of entries, if any,
            are folders with simulator restart runs.
        """
        # Call parent class __init__
        super().__init__(paths)

        # Filled on first use by names()
        self._names: list[str] | None = None

        # Organize well information for all report dates
        self._well_info_all_report_steps()

    def _well_info_all_report_steps(self) -> None:
        """
        Get coordinates and status for all wells at all report dates.

        Notes
        -----
        Information on what is available in restart files can be found in OPM Flow manual appendices
        or Eclipse file format manual
        """
        # Init. well info as a list with entry for each report date
        self._well_info = [{} for erst in self.rst for _ in erst.report_steps]

        # Loop over all restart files and report steps for each file and organize well information
        # in dictionaries using well names as keys.
        ind = 0
        for erst in self.rst:
            for rstep in erst.report_steps:
                # Report step 0 does not have well information
                if rstep == 0:
                    ind += 1
                    continue

                # Check for well keywords in restart files
                available_keys = {key[0] for key in erst.arrays(rstep)}
                if "ZWEL" not in available_keys or "ICON" not in available_keys:
                    ind += 1
                    continue

                # Extract well names from ZWEL mnemonic
                # NOTE: ZWEL = [well_name, well_list, last_action] for each well at report step
                well_names = erst[("ZWEL", rstep)][::3]

                # Information about the wells are located in IWEL and ICON. IWEL and ICON have
                # specific lengths, and info for these can be found in INTEHEAD
                intehead = erst[("INTEHEAD", rstep)]
                niwelz = intehead[24]
                niconz = intehead[32]
                ncwmax = intehead[17]
                nwells = intehead[16]

                # Check that we have names for all wells found in INTEHEAD
                if len(well_names) != nwells:
                    raise ValueError(
                        f"Number of wells in ZWEL (={len(well_names)}) does not correspond to info"
                        f" in INTEHEAD (={nwells})!"
                    )

                # Information about the wells are located in IWEL and ICON, so we reshape those to
                # a more easily accessible shape
                iwel = np.reshape(erst[("IWEL", rstep)], (nwells, niwelz))
                icon = np.reshape(erst[("ICON", rstep)], (nwells, ncwmax, niconz))

                # Well-level surface/reservoir rates from XWEL, for alternative well status check
                if "XWEL" in available_keys:
                    nxwelz = intehead[26]
                    xwel = np.reshape(erst[("XWEL", rstep)], (nwells, nxwelz))
                    flowing = np.any(xwel[:, _XWEL_RATES] != 0, axis=1)
                else:
                    flowing = np.zeros(nwells, dtype=bool)

                # Loop over wells and organize info in list as follows
                # well_info = [i, j, k0, k1, ..., kend, status]
                # NOTE: Suited for vertical wells at the moment: i, j are well head indices. Status
                # is whether well is open or shut; could be modified to connection status (found in
                # icon[_, _, 5])
                self._well_info[ind] = {key: [] for key in well_names}
                for i, name in enumerate(well_names):
                    # i,j indices of well head
                    self._well_info[ind][name].extend((iwel[i, :2] - 1).tolist())

                    # k-indices for well connection
                    self._well_info[ind][name].extend(
                        (icon[i, icon[i, :, 3] > 0, 3] - 1).tolist()
                    )

                    # Well status (open/shut = True/False). OPM only sets IWEL status to open if a
                    # connection has a nonzero oil, water or gas rate, which misses e.g. solvent
                    # injectors, so a nonzero well rate in XWEL also counts as open.
                    # OBS: convert to Python bool instead of numpy.bool_
                    self._well_info[ind][name].extend([bool(iwel[i, 10] > 0 or flowing[i])])

                # Increase internal well_info index counter
                ind += 1

    def names(self) -> list[str]:
        """
        Names of every well at any report step

        Returns
        -------
        list[str]
            Sorted, without repeats. Includes wells that are only present at some report steps,
            e.g. ones drilled later in the run
        """
        if self._names is None:
            self._names = sorted({name for info in self._well_info for name in info})
        return self._names

    def check_names(self, names: Iterable[str]) -> None:
        """
        Check that names are all wells in the case

        Parameters
        ----------
        names : Iterable[str]
            Well names to check

        Raises
        ------
        KeyError
            If a name is not a well at any report step; the message lists the ones that are
        """
        unknown = [name for name in names if name not in self.names()]
        if unknown:
            raise KeyError(
                f"Unknown well name(s): {', '.join(unknown)}. Wells in the case: "
                f"{', '.join(self.names()) or 'none'}."
            )

    def __getitem__(self, rstep: int) -> dict[str, list[Any]]:
        """
        Get well info at inputted report step

        Parameters
        ----------
        rstep : int
            Report step

        Returns
        -------
        dict
            Dictionary with information for each well. List organized as [i, j, k0, k1, ..., kend,
            status]
        """
        # rstep is not necessarily equal to index of self._well_info since it is possible output
        # restart arrays at any frequency (see, e.g., RPTRST keyword, and BASIC and FREQ mnemonics!)
        erst_idx, local_idx = self._step_index[rstep]
        return self._well_info[self._erst_step_offsets[erst_idx] + local_idx]

    def __iter__(self) -> Iterator[dict[str, list[Any]]]:
        for elem in self._well_info:
            yield elem
