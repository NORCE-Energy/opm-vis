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

        Notes
        -----
        A restart run's TIME axis starts at the point it restarted from and re-simulates
        everything from there onward, so once a later file's first timestep is reached, it and
        everything after it supersede whatever was kept from earlier files for that same stretch
        of time - regardless of which earlier file(s) contributed it. Truncating by comparison
        (rather than requiring an exact timestamp match) also keeps the series strictly
        chronological even if a restart's first reported step doesn't land on exactly the same
        timestep as the run it restarts from.
        """
        # Start date should be the same in any file
        start_date = self.smry[0].start_date

        # Accumulate (datetime, file index, local index) triples for every timestep that ends up
        # in the final stitched series, in chronological/file order.
        entries = []
        for i, smry in enumerate(self.smry):
            # TIME keyword is in days; convert to datetime objects
            time_unsmry = [
                start_date + dt.timedelta(days=float(t)) for t in smry["TIME"]
            ]

            # A restart's first reported step supersedes everything from that point onward that
            # was kept so far, wherever it came from - drop it before appending this file's data.
            if entries and time_unsmry:
                restart_point = time_unsmry[0]
                entries = [entry for entry in entries if entry[0] < restart_point]

            entries.extend(
                (time, i, local_ind) for local_ind, time in enumerate(time_unsmry)
            )

        self.time = [entry[0] for entry in entries]
        self.time_ind = [[] for _ in self.smry]
        for _, file_ind, local_ind in entries:
            self.time_ind[file_ind].append(local_ind)

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
