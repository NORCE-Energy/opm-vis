""" Calculate various attributes from restart files """
from glob import glob
import warnings
import datetime as dt

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


class RestartFiles:
    """
    Top class for initiating and reading restart files
    """

    def __init__(self, paths):
        """
        Init. class by instantiating ERst classes for each restart file in input folders

        Parameters
        ----------
        paths : list
            List of paths with restart files
        """
        # Instantiate Erst class for restart files
        self._instantiate_restart_files(paths)

    def _instantiate_restart_files(self, paths):
        """
        Instantiate ERst classes for restart files in paths

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
                print([key[0] for key in erst.arrays(rstep) if key[0] not in _IGNORE])
                return

        # Raise error if report step does not exist in restart files
        raise ValueError(f"Report step {rstep} was not found in restart files!")


class Report(RestartFiles):
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
