""" Unit tests for opm_vis.utils.static, backed by the SPE1CASE1 INIT test dataset """
import shutil
from pathlib import Path

import numpy as np
import pytest

from opm_vis.utils.static import InitReader

DATA_DIR = Path(__file__).parent / "data"
CASE = str(DATA_DIR / "SPE1CASE1")  # "path" prefix, as _InitFile's glob() expects


@pytest.fixture(scope="module")
def reader():
    return InitReader(CASE)


# ---------------------------------------------------------------------------
# _InitFile.__init__ (through InitReader, real files + synthetic warnings)
# ---------------------------------------------------------------------------


def test_no_init_file_found_warns_and_leaves_init_unset(tmp_path):
    with pytest.warns(UserWarning, match="No .INIT file found"):
        ir = InitReader(str(tmp_path / "MISSING"))
    assert ir.init is None


def test_multiple_init_files_warns_and_loads_first(tmp_path):
    shutil.copy(DATA_DIR / "SPE1CASE1.INIT", tmp_path / "CASE1.INIT")
    shutil.copy(DATA_DIR / "SPE1CASE1.INIT", tmp_path / "CASE2.INIT")

    with pytest.warns(UserWarning, match="Multiple .INIT files"):
        ir = InitReader(str(tmp_path / "CASE"))
    assert ir.init is not None


# ---------------------------------------------------------------------------
# InitReader.read
# ---------------------------------------------------------------------------


def test_read_returns_full_array_for_keyword(reader):
    poro = reader.read("PORO")

    assert poro.shape == (300,)  # SPE1CASE1 is a 10x10x3 grid, fully active
    np.testing.assert_allclose(poro[0], 0.3)


def test_read_applies_active_indices(reader):
    poro = reader.read("PORO", act=[2, 0])

    full = reader.read("PORO")
    np.testing.assert_allclose(poro, full[[2, 0]])


def test_read_raises_when_no_init_file_was_found(tmp_path):
    with pytest.warns(UserWarning, match="No .INIT file found"):
        ir = InitReader(str(tmp_path / "MISSING"))

    with pytest.raises(ValueError, match="No .INIT file was found"):
        ir.read("PORO")


# ---------------------------------------------------------------------------
# InitReader.available_keywords
# ---------------------------------------------------------------------------


def test_available_keywords_lists_dataset_keywords(reader):
    keywords = reader.available_keywords()

    assert "PORO" in keywords
    assert "PERMX" in keywords
    assert "PRESSURE" in keywords


def test_available_keywords_filters_ignored_mnemonics():
    # SPE1CASE1.INIT's own array list never includes the ignored mnemonics, so the
    # filter itself is exercised with a small stand-in exposing just the interface
    # available_keywords() needs.
    class _StubInit:
        def get_list_of_arrays(self):
            return [
                ("INTEHEAD", None),
                ("LOGIHEAD", None),
                ("DOUBHEAD", None),
                ("PORO", None),
                ("STARTSOL", None),
                ("PRESSURE", None),
                ("ENDSOL", None),
            ]

    ir = object.__new__(InitReader)
    ir.init = _StubInit()

    assert ir.available_keywords() == ["PORO", "PRESSURE"]


def test_available_keywords_raises_when_no_init_file_was_found(tmp_path):
    with pytest.warns(UserWarning, match="No .INIT file found"):
        ir = InitReader(str(tmp_path / "MISSING"))

    with pytest.raises(ValueError, match="No .INIT file was found"):
        ir.available_keywords()
