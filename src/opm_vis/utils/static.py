""" Static parameters from INIT files """
from glob import glob
import warnings

from opm.util import EModel


# pylint: disable=too-few-public-methods
class _InitFile:
    """
    Top class for EModel wrapper
    """

    def __init__(self, path):
        """
        Initialize class by instantiating EModel with .INIT file input

        Parameters
        ----------
        path : str
            Path to .INIT file
        """
        # Check path for .INIT file and instantiate if it exist
        if glob(path + "*.INIT"):
            if len(glob(path + "*.INIT")) > 1:
                warnings.warn(
                    f"Multiple .INIT files in {path}. Importing {glob(path + '*.INIT')[0]}."
                )
            self.init = EModel(glob(path + "*.INIT")[0])
        else:
            raise FileNotFoundError(f"No .INIT file found in {path}!")


class InitReader(_InitFile):
    """
    Class for reading .INIT files. Initialization in parent class.
    """

    def read(self, keyword, act=None):
        """
        Read .INIT file and return array for active indices.

        Parameters
        ----------
        keyword : str
            Keyword for static parameters in OPM
        act : list, optional
            Active indices for output array. If act=None, whole array is outputted.

        Returns
        -------
        out : ndarray
            Array with static parameters
        """
        return (
            self.init.get(keyword)[act] if act is not None else self.init.get(keyword)
        )

    def available_keywords(self):
        """
        See keywords that are available in .INIT file
        """
        print([key[0] for key in self.init.get_list_of_arrays()])
