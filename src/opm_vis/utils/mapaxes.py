""" MAPAXES helper for OPM EGRID files """
from opm.io.ecl import EclFile


def has_mapaxes(path: str) -> bool:
    """
    Check whether an EGRID file defines a MAPAXES transform

    Parameters
    ----------
    path : str
        Path to the .EGRID file

    Returns
    -------
    bool
        True if the file has a MAPAXES keyword

    Notes
    -----
    opm.io.ecl.EGrid has no way to tell whether MAPAXES was actually present on its own - its
    own export_mapaxes() returns all zeros whether or not the keyword exists - so presence is
    checked through EclFile, which exposes the raw keyword list, instead.
    """
    return "MAPAXES" in EclFile(path)
