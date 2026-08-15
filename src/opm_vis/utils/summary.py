""" Read and manipulate summary files """
from __future__ import annotations

import datetime as dt
import warnings
from glob import glob

import numpy as np
from numpy.typing import NDArray
from opm.io.ecl import ESmry

from opm_vis.utils.timeline import DAYS_PER_YEAR

# Summary files report at ministep resolution, so a timestep can land part way into a day; days
# are therefore computed from whole seconds rather than timedelta.days, which would truncate
# several ministeps onto the same value. See elapsed_days().
_SECONDS_PER_DAY = 86400.0


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
                if len(smspec) > 1:
                    warnings.warn(
                        f"Multiple .SMSPEC files in {path}. Importing {smspec[0]}."
                    )
                smry_path.append(smspec[0])

        # Keep the resolved file names, not just the prefixes they were found from: a prefix can
        # be "./", which says nothing about which case it is, while the file name identifies it
        # (used for plot legends and for error messages naming the offending file).
        self.smry_paths = smry_path

        # Instantiate ESmry class for each .SMSPEC file found
        self.smry = [ESmry(smry) for smry in smry_path]

        # Lazily filled caches; see has_keyword() and read()
        self._keyword_set: set[str] | None = None
        self._cache: dict[str, NDArray] = {}

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
        # No .SMSPEC files were found in any of the input paths - nothing to stitch together
        if not self.smry:
            self.time = []
            self.time_ind = []
            return

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

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths
        KeyError
            If the mnemonic is missing from one of the summary files

        Notes
        -----
        Each mnemonic is read from file once and then kept: plotting several vectors, or the same
        vector on several axes, otherwise costs one decompression pass over every .UNSMRY per
        read. The cached array itself is handed back, so callers must not modify it in place.
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot read summary data!")

        if keyword in self._cache:
            return self._cache[keyword]

        # Read mnemonic from correct path (in case of multiple paths) and extend a time series list
        time_series = []
        for i, smry in enumerate(self.smry):
            try:
                values = smry[keyword]
            except ValueError as exc:
                # ESmry's own message quotes the source file it was built from, which says
                # nothing to a user; a restart run whose SUMMARY section is missing a mnemonic
                # the main run has is the case worth naming.
                raise KeyError(
                    f"{keyword} was not found in {self.smry_paths[i]}!"
                ) from exc
            time_series.extend(values[self.time_ind[i]])

        self._cache[keyword] = np.array(time_series)

        return self._cache[keyword]

    def available_keywords(self) -> list[str]:
        """
        Return available summary keywords

        Returns
        -------
        list[str]
            List of summary keywords

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths

        Notes
        -----
        Only the first file is consulted, so a restart run adding entries to its SUMMARY section
        is not seen here. read() raises for such a mnemonic, naming the file it is missing from.
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot list available keywords!")

        # Assume the same keywords exist in all .SMPEC files
        return self.smry[0].keys()

    def has_keyword(self, keyword: str) -> bool:
        """
        Check whether a mnemonic exists in the summary file(s)

        Parameters
        ----------
        keyword : str
            Summary mnemonic

        Returns
        -------
        bool
            True if the mnemonic exists, False otherwise - including when no .SMSPEC file was
            found at all, so a caller picking which vectors to plot never has to guard the call

        Notes
        -----
        Backed by a set built on first use: ESmry.keys() rebuilds its list on every call, and a
        plot with several vectors and several cases asks this once per combination.
        """
        if not self.smry:
            return False

        if self._keyword_set is None:
            self._keyword_set = set(self.available_keywords())

        return keyword in self._keyword_set

    def unit(self, keyword: str) -> str:
        """
        Return the unit the summary file records for a mnemonic

        Parameters
        ----------
        keyword : str
            Summary mnemonic

        Returns
        -------
        str
            Raw unit string, e.g. "STB/DAY", or "" for a dimensionless vector such as a
            saturation. See opm_vis.utils.units.summary_unit_label to render it for a plot.

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths
        KeyError
            If the mnemonic does not exist

        Notes
        -----
        Unlike the grid keywords in opm_vis.utils.units.Label, summary vectors need no unit
        convention table: .SMSPEC stores a unit string per vector, so the file itself says
        whether a rate is in STB/DAY or SM3/DAY. Read from the first file only, as
        available_keywords() is.
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot read units!")

        try:
            return self.smry[0].units(keyword)
        except IndexError as exc:
            # ESmry.units() raises a bare IndexError("unordered_map::at") for an unknown
            # mnemonic, which names neither the keyword nor the problem
            raise KeyError(f"{keyword} is not a summary keyword!") from exc

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

    def start_date(self) -> dt.datetime:
        """
        Return the date the simulation started

        Returns
        -------
        dt.datetime
            Start date, i.e. the deck's START

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths

        Notes
        -----
        This is not necessarily summary_dates()[0]: the first reported timestep is normally some
        way into the run. It is the point the TIME and YEARS vectors are measured from.
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot read the start date!")

        return self.smry[0].start_date

    def end_date(self) -> dt.datetime:
        """
        Return the date the simulation ended

        Returns
        -------
        dt.datetime
            End date of the last summary file, i.e. of the last restart run

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot read the end date!")

        return self.smry[-1].end_date

    def elapsed_days(self) -> NDArray[np.float64]:
        """
        Return the time since the simulation started, in days, for every timestep

        Returns
        -------
        NDArray[np.float64]
            One value per entry in summary_dates(), the same quantity as the TIME vector

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths

        Notes
        -----
        Measured from start_date() rather than from the first reported timestep, which is what
        makes this equal to TIME rather than to TIME minus its own first value.
        """
        if not self.smry:
            raise ValueError("No .SMSPEC file was found; cannot compute elapsed time!")

        start = self.start_date()

        return np.array(
            [(time - start).total_seconds() / _SECONDS_PER_DAY for time in self.time],
            dtype=np.float64,
        )

    def elapsed_years(self) -> NDArray[np.float64]:
        """
        Return the time since the simulation started, in years, for every timestep

        Returns
        -------
        NDArray[np.float64]
            One value per entry in summary_dates(), the same quantity as the YEARS vector

        Raises
        ------
        ValueError
            If no .SMSPEC file was found in any of the input paths

        Notes
        -----
        A year is 365.25 days (opm_vis.utils.timeline.DAYS_PER_YEAR), matching both the YEARS
        vector and what opm-vis-rdates reports.
        """
        return self.elapsed_days() / DAYS_PER_YEAR
