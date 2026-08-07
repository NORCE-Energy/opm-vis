""" Static parameters from INIT files """
from __future__ import annotations

from glob import glob
import warnings
from typing import Any

from numpy.typing import NDArray
from opm.util import EModel

# Keywords to ignore
_IGNORE = frozenset({"INTEHEAD", "LOGIHEAD", "DOUBHEAD", "STARTSOL", "ENDSOL"})


# pylint: disable=too-few-public-methods
class _InitFile:
    """
    Top class for EModel wrapper
    """

    def __init__(self, path: str) -> None:
        """
        Initialize class by instantiating EModel with .INIT file input

        Parameters
        ----------
        path : str
            Path prefix used to locate the .INIT file (glob pattern `path + "*.INIT"`)
        """
        # Check path for .INIT file and instantiate if it exist
        self.init = None
        init_files = glob(path + "*.INIT")
        if init_files:
            if len(init_files) > 1:
                warnings.warn(
                    f"Multiple .INIT files in {path}. Importing {init_files[0]}."
                )
            self.init = EModel(init_files[0])
        else:
            warnings.warn(f"No .INIT file found in {path}!")


class InitReader(_InitFile):
    """
    Class for reading .INIT files. Initialization in parent class.
    """

    # Cache for available_keywords(): the .INIT file's keyword list can't change
    # after construction, so there's no need to recompute it on every call.
    _keywords: list[str] | None = None

    def read(self, keyword: str, act: list[int] | None = None) -> NDArray[Any]:
        """
        Read .INIT file and return array for active indices.

        Parameters
        ----------
        keyword : str
            Keyword for static parameters in OPM
        act : list[int] | None, optional
            Active indices for output array. If act=None, whole array is outputted.

        Returns
        -------
        out : ndarray
            Array with static parameters
        """
        if self.init is None:
            raise ValueError("No .INIT file was found; cannot read static parameters!")

        out = self.init.get(keyword)
        return out[act] if act is not None else out

    def available_keywords(self) -> list[str]:
        """
        List of keywords that are available in .INIT file

        Returns
        -------
        list[str]
            Keywords available in .INIT file
        """
        if self._keywords is None:
            if self.init is None:
                raise ValueError(
                    "No .INIT file was found; cannot list available keywords!"
                )
            self._keywords = [
                key[0]
                for key in self.init.get_list_of_arrays()
                if key[0] not in _IGNORE
            ]
        return self._keywords
