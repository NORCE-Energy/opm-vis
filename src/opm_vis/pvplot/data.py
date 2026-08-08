""" Keyword lookup across the restart and .INIT files of one case """
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from opm_vis.utils.restart import Report, RestartReader, Wells
from opm_vis.utils.static import InitReader


class CaseData:
    """
    Simulation results for one case, addressed by keyword and report step.

    Bundles the readers in :mod:`opm_vis.utils` behind a single lookup, so callers do not need
    to know whether a keyword is dynamic (restart files) or static (.INIT file).
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Initialize by instantiating the readers for the case

        Parameters
        ----------
        paths : list[str]
            List of paths to OPM files. First entry considered to be the main folder; rest of
            entries are folders with restart runs. Each entry is a filename prefix.

        Notes
        -----
        Only the main run's .INIT file is read: static properties do not change between a run
        and its restarts.
        """
        # Instantiate help classes
        self.restart = RestartReader(paths)
        self.static = InitReader(paths[0])
        self.report = Report(paths)

        # Internal variables. Wells walks every report step of every restart file, so it is
        # built only if something asks for it; see the wells property.
        self._paths = paths
        self._wells: Wells | None = None

    @property
    def wells(self) -> Wells:
        """
        Well information for every report step

        Returns
        -------
        Wells
            Indexable by report step, see opm_vis.utils.restart.Wells
        """
        if self._wells is None:
            self._wells = Wells(self._paths)
        return self._wells

    def read(self, keyword: str, rstep: int) -> NDArray[Any]:
        """
        Read a keyword at one report step

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step

        Returns
        -------
        NDArray[Any]
            One value per active cell, in active index order

        Notes
        -----
        Restart keywords take priority over .INIT keywords, matching opm_vis.plot. This
        matters because a handful of mnemonics (PRESSURE, RS, SGAS, SWAT) appear in both,
        where the .INIT copy is only the initial state.
        """
        if not self.is_static(keyword, rstep):
            return self.restart.read(keyword, rstep)

        if keyword in self.static.available_keywords():
            return self.static.read(keyword)

        raise KeyError(f"{keyword} not in restart files or .INIT file!")

    def value_range(self, keyword: str, rsteps: Sequence[int]) -> tuple[float, float]:
        """
        Smallest and largest value a keyword takes over a set of report steps

        Parameters
        ----------
        keyword : str
            OPM keyword
        rsteps : Sequence[int]
            Report steps to include

        Returns
        -------
        tuple[float, float]
            (minimum, maximum) over all the given report steps, ignoring NaNs

        Notes
        -----
        Seeded from the data rather than from 0. opm_vis.plot starts its accumulators at zero
        (see collections.py), so a pressure field in [4000, 6000] psia is given a colour range
        beginning at zero and most of the colour map goes unused.

        A static keyword has the same values at every report step, so it is only read once.
        """
        if len(rsteps) == 0:
            raise ValueError(
                f"No report steps given to compute the value range of {keyword}!"
            )

        # A static keyword does not vary with time, so one report step settles it
        steps = [rsteps[0]] if self.is_static(keyword, rsteps[0]) else rsteps

        low, high = np.inf, -np.inf
        for rstep in steps:
            data = self.read(keyword, rstep)
            low = min(low, np.nanmin(data))
            high = max(high, np.nanmax(data))

        return float(low), float(high)

    def is_static(self, keyword: str, rstep: int) -> bool:
        """
        Check whether a keyword has to come from the .INIT file

        Parameters
        ----------
        keyword : str
            OPM keyword
        rstep : int
            Report step

        Returns
        -------
        bool
            True if the keyword is absent from the restart files at this report step, and so
            does not vary with time
        """
        return keyword not in self.restart.available_keywords(rstep)

    def unit_convention(self) -> str:
        """
        Unit convention of the case

        Returns
        -------
        str
            One of 'metric', 'field', 'lab' or 'pvt-m'
        """
        return self.restart.unit_convention()
