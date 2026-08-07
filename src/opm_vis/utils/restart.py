""" Calculate various attributes from restart files """
from __future__ import annotations

import datetime as dt
import os
import warnings
from glob import glob
from typing import Any, Iterator

import numpy as np
from numpy.typing import NDArray
from opm.io.ecl import ERst


_IGNORE = [
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
]


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
        # Instantiate OPM restart class. Need to search paths for .UNRST or .X files
        self.rst = []
        for path in paths:
            # Init. restart file list for current search path
            restart_files = []

            unrst_files = glob(os.path.join(path, "*.UNRST"))
            x_files = glob(os.path.join(path, "*.X*"))

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
        # Loop over restart files to find array at correct report step
        for erst in self.rst:
            if rstep in erst.report_steps:
                out = erst[(keyword, rstep)]
                return out[act] if act is not None else out

        # Raise error if report step does not exist in restart files
        raise ValueError(f"Report step {rstep} was not found in restart files!")

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
        #  Loop over restart files to find info at correct report step
        for erst in self.rst:
            if rstep in erst.report_steps:
                return [key[0] for key in erst.arrays(rstep) if key[0] not in _IGNORE]

        # Raise error if report step does not exist in restart files
        raise ValueError(f"Report step {rstep} was not found in restart file(s)!")

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
        # Lookup in restart file
        info = None
        for erst in self.rst:
            if rstep in erst.report_steps:
                info = erst[("INTEHEAD", rstep)][item]
                break

        # If header info is not found, raise error
        if info is None:
            raise ValueError(f"INTEHEAD item {item} not found in restart file(s)!")

        return info

    def unit_convension(self) -> str:
        """Return unit convension used in run"""
        return ["metric", "field", "lab", "pvt-m"][self.intehead(2, 0) - 1]


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
            self.rsteps += erst.report_steps

            # Loop over report steps and get report dates as datetime object
            for rstep in rsteps_unrst:
                self.rdates.extend(
                    [
                        dt.datetime(
                            day=erst[("INTEHEAD", rstep)][64],
                            month=erst[("INTEHEAD", rstep)][65],
                            year=erst[("INTEHEAD", rstep)][66],
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

    def __str__(self) -> str:
        """
        Print an table of report dates and steps if called by Python print method

        Returns
        -------
        str
            Table of report steps // report dates
        """
        # Print table with columns: report step // report dates
        output_string = "Report step\tDate\n"
        for i, date in enumerate(self.rdates):
            output_string += f'{self.rsteps[i]}\t\t{date.strftime("%d.%m.%Y")}\n'

        return output_string

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
        return self.rdates[self.rsteps.index(rstep)]

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
                niwelz = erst[("INTEHEAD", rstep)][24]
                niconz = erst[("INTEHEAD", rstep)][32]
                ncwmax = erst[("INTEHEAD", rstep)][17]
                nwells = erst[("INTEHEAD", rstep)][16]

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

                    # Well status (open/shut = True/False).
                    # OBS: convert to Python bool instead of numpy.bool_
                    self._well_info[ind][name].extend([bool(iwel[i, 10] > 0)])

                # Increase internal well_info index counter
                ind += 1

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
        # Start index at zero and count up until we reach report step in some restart file.
        ind = 0
        for erst in self.rst:
            if rstep in erst.report_steps:
                ind += erst.report_steps.index(rstep)
            else:
                ind += len(erst.report_steps)
        return self._well_info[ind]

    def __iter__(self) -> Iterator[dict[str, list[Any]]]:
        for elem in self._well_info:
            yield elem
