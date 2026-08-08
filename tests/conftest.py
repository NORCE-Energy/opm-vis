""" Shared fixtures locating the datasets in tests/data """
from pathlib import Path

import pytest

# Test datasets live next to this file. Note that "path" arguments throughout opm_vis are
# filename prefixes rather than directories - every reader does glob(path + "*.EXT") - so the
# case fixtures below deliberately return a prefix with no extension.
_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """
    Directory holding the test datasets

    Returns
    -------
    Path
        Path to tests/data
    """
    return _DATA_DIR


@pytest.fixture(scope="session")
def case1() -> str:
    """
    Filename prefix of the SPE1CASE1 dataset

    Returns
    -------
    str
        Path prefix, as the glob() in every opm_vis reader expects

    Notes
    -----
    SPE1CASE1 is a fully active, standard-oriented 10x10x3 Cartesian box grid in field units,
    with 121 report steps (0-120) and two vertical wells (PROD, INJ). It has no inactive cells,
    no NaN corner points and no faults.
    """
    return str(_DATA_DIR / "SPE1CASE1")
