""" Calculate various attributes from restart files """
import datetime as dt
import warnings
from glob import glob

import numpy as np
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

    def __init__(self, paths):
        """
        Init. class by instantiating ERst classes for each restart file in input folders

        Parameters
        ----------
        paths : list
            List of paths with restart files
        """
        # Instantiate OPM restart class. Need to search paths for .UNRST or .X files
        self.rst = []
        for path in paths:
            # Init. restart file list for current search path
            restart_files = []

            # Are there UNRST and X files in same folder? We load the UNRST file and issue warning
            if glob(path + "*.UNRST") and glob(path + "*.X*"):
                warnings.warn(
                    f"There are .UNRST and .X files in {path}. We load the UNRST file!"
                )
                if len(glob(path + "*.UNRST")) > 1:
                    warnings.warn(
                        f"Multiple .UNRST files in {path}. Importing {glob(path + '*.UNRST')[0]}."
                    )
                restart_files = glob(path + "*.UNRST")[0]

            # Are there no files in the folder? Warn and continue
            elif not glob(path + "*.UNRST") and not glob(path + "*.X*"):
                warnings.warn(f"No .UNRST or .X files found {path}! Skipping folder...")

            # .UNRST file
            elif glob(path + "*.UNRST") and not glob(path + "*.X*"):
                if len(glob(path + "*.UNRST")) > 1:
                    warnings.warn(
                        f"Multiple .UNRST files in {path}. Importing {glob(path + '*.UNRST')[0]}"
                    )
                restart_files = glob(path + "*.UNRST")[0]

            # .X files
            elif not glob(path + "*.UNRST") and glob(path + "*.X*"):
                restart_files = glob(path + "*.X*")

            # Instantiate ERst class for each file in path
            if restart_files:
                self.rst.extend([ERst(file) for file in restart_files])


class RestartReader(_RestartFiles):
    """
    Class for reading restart files (mainly). Initialization in parent class.
    """

    def read(self, keyword, rstep, act=None):
        """
        Read restart file at report step and return array for active indices.

        Parameters
        ----------
        keyword : str
            OPM keyword (must exist in restart file, i.e., either be one of the default outputs or
            inputed in RST-type mnemonics).
        rstep : int
            Report step.
        act : list, optional
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

    def available_keywords(self, rstep):
        """
        Available keyword at report step

        Parameters
        ----------
        rstep : int
            Report step
        """
        #  Loop over restart files to find info at correct report step
        for erst in self.rst:
            if rstep in erst.report_steps:
                return [key[0] for key in erst.arrays(rstep) if key[0] not in _IGNORE]

        # Raise error if report step does not exist in restart files
        raise ValueError(f"Report step {rstep} was not found in restart files!")


class Report(_RestartFiles):
    """
    Class to organize and handle report dates/steps from restart files
    """

    def __init__(self, paths):
        # Instantiate Erst class for restart files using parent class
        super().__init__(paths)

        # Extract report dates and report steps from restart files
        self._report_dates_and_steps()

    def _report_dates_and_steps(self):
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

    def __str__(self):
        """
        Print an table of report dates and steps if called by Python print method
        """
        # Print table with columns: report step // report dates
        output_string = "Report step\tDate\n"
        for i, date in enumerate(self.rdates):
            output_string += f'{self.rsteps[i]}\t\t{date.strftime("%d.%m.%Y")}\n'

        return output_string

    def report_dates(self):
        """Return report dates"""
        return self.rdates

    def report_steps(self):
        """Return report steps"""
        return self.rsteps


class Wells(_RestartFiles):
    """
    Well information from restart files
    """

    def __init__(self, paths):
        # Call parent class __init__
        super().__init__(paths)

        # Organize well information for all report dates
        self._well_info_all_report_steps()

    def _well_info_all_report_steps(self):
        """
        Get coordinates and status for all wells at all report dates.

        Notes
        -----
        Information on what is available in restart files can be found in OPM Flow manual appendices
        or Eclipse file format manual
        """
        # Init. well info as a list with entry for each report date
        self.well_info = [{} for erst in self.rst for _ in erst.report_steps]

        # Loop over all restart files and report steps for each file and organize well information
        # in dictionaries using well names as keys.
        ind = 0
        for erst in self.rst:
            for rstep in erst.report_steps:
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
                assert len(well_names) == nwells, (
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
                self.well_info[ind] = {key: [] for key in well_names}
                for i, name in enumerate(well_names):
                    # i,j indices of well head
                    self.well_info[ind][name].extend(iwel[i, :2].tolist())

                    # k-indices for well connection
                    self.well_info[ind][name].extend(icon[i, icon[i, :, 3] > 0, 3] - 1)

                    # Well status (open/shut = True/False).
                    # OBS: convert to Python bool instead of numpy.bool_
                    self.well_info[ind][name].extend([bool(iwel[i, 10] > 0)])

                # Increase internal well_info index counter
                ind += 1

    def __getitem__(self, rstep):
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
        # rstep is not necessarily equal to index of self.well_info since it is possible output
        # restart arrays at any frequency (see, e.g., RPTRST keyword, and BASIC and FREQ mnemonics!)
        # Start return index at zero and count up until we reach report step in some restart file.
        ind = 0
        for erst in self.rst:
            if rstep in erst.report_steps:
                ind += erst.report_steps.index(rstep)
            else:
                ind += len(erst.report_steps)
        return self.well_info[ind]
