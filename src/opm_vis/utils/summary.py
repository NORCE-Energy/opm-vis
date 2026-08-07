""" Read and manipulate summary files """
import datetime as dt
import warnings
from glob import glob

import numpy as np
from numpy.typing import NDArray
from opm.io.ecl import ESmry


class SummaryReader:
    """
    ESmry wrapper class
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Init. class by instantiating ESmry classes for each .SMSPEC file in input folders

        Parameters
        ----------
        paths : list[str]
            List of paths with .SMSPEC files. Main folder is in paths[0]; rest of entries, if any,
            are folders with simulator restart runs.
        """
        # Search paths for .SMSPEC files
        smry_path = []
        for path in paths:
            # Check if .SMSPEC file is in path and raise warning if not; else add to smry_path
            smspec = glob(path + "*.SMSPEC")
            if not smspec:
                warnings.warn(f"No .SMSPEC found in {path}! Skipping folder...")
            else:
                smry_path.append(smspec[0])

        # Instantiate ESmry class for each .SMSPEC file found
        self.smry = [ESmry(smry) for smry in smry_path]

        # Get a consistent lists of time and associated indices to get a non-overlapping time series
        # from summary files (in case of simulation restart)
        self._time_and_indices()

    def _time_and_indices(self) -> None:
        """
        Create a consistent list of times (as datetime objects) in case of simulation restarts. In
        addition, a list of indices are created to be sure we read correct time series data from
        correct files (in the correct path).
        """
        # Start date should be the same in any file
        start_date = self.smry[0].start_date

        # Loop over summary files and get time as datetimes together with indices (for concatenating
        # time series across simulation restarts)
        self.time = []
        self.time_ind = [[] for _ in self.smry]
        for i, smry in enumerate(self.smry):
            # TIME keyword is in days; convert to datetime objects
            time_unsmry = [
                start_date + dt.timedelta(days=float(t)) for t in smry["TIME"]
            ]
            self.time_ind[i] = list(range(len(time_unsmry)))

            # Check for overlapping time between different .SMSPEC files (i.e. when simulation has
            # been restarted)
            if i > 0:
                _, ind, _ = np.intersect1d(self.time, time_unsmry, return_indices=True)

                # If overlap, stitch the times and indices together
                if ind.size > 0:
                    self.time_ind[i - 1] = [
                        k for k in range(len(self.time[:-1])) if k not in ind
                    ]
                    self.time = [
                        ent for j, ent in enumerate(self.time[:-1]) if j not in ind
                    ]

            # Add datetimes at the end of current list
            self.time.extend(time_unsmry)

    def read(self, keyword: str) -> NDArray:
        """
        Read time series arrays from summary file(s)

        Parameters
        ----------
        keyword : str
            Summary mnemonic. OBS: Must be given in the SUMMARY section in the OPM/Eclipse deck!

        Returns
        -------
        NDArray
            Time series
        """
        # Read mnemonic from correct path (in case of multiple paths) and extend a time series list
        time_series = []
        for i, smry in enumerate(self.smry):
            time_series.extend(smry[keyword][self.time_ind[i]])

        return np.array(time_series)

    def available_keywords(self) -> list[str]:
        """
        Return available summary keywords

        Returns
        -------
        list[str]
            List of summary keywords
        """
        # Assume the same keywords exist in all .SMPEC files
        return self.smry[0].keys()

    def summary_dates(self) -> list[dt.datetime]:
        """
        Return all dates in time series.

        Returns
        -------
        list[dt.datetime]
            List of summary dates

        Notes
        -----
        This can be a long list of dates, since summary files include data at all ministeps
        """
        return self.time
