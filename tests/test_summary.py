""" Unit tests for opm_vis.utils.summary, backed by the SPE1CASE1/SPE1CASE2 SMSPEC test datasets """
import datetime as dt
import shutil
from pathlib import Path

import numpy as np
import pytest

from opm_vis.utils.summary import SummaryReader

DATA_DIR = Path(__file__).parent / "data"
CASE1 = str(DATA_DIR / "SPE1CASE1")  # "path" prefix, as SummaryReader's glob() expects

# SPE1CASE2_RESTART_60 is a restart of SPE1CASE2 from report step 60: it reproduces
# SPE1CASE2's last 60 timesteps bit-for-bit. Together they exercise the restart
# stitching in _time_and_indices(). Both files share the "SPE1CASE2" filename prefix
# in tests/data, so glob("...SPE1CASE2*.SMSPEC") would ambiguously match both -
# copying each into its own directory keeps the two paths unambiguous, mirroring how
# separate restart runs live in separate folders in practice.


@pytest.fixture(scope="module")
def reader():
    return SummaryReader([CASE1])


@pytest.fixture(scope="module")
def restart_paths(tmp_path_factory):
    base = tmp_path_factory.mktemp("restart_data")
    main_dir = base / "main"
    restart_dir = base / "restart"
    main_dir.mkdir()
    restart_dir.mkdir()

    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(DATA_DIR / f"SPE1CASE2{ext}", main_dir / f"CASE{ext}")
        shutil.copy(DATA_DIR / f"SPE1CASE2_RESTART_60{ext}", restart_dir / f"CASE{ext}")

    return [str(main_dir / "CASE"), str(restart_dir / "CASE")]


@pytest.fixture(scope="module")
def restart_reader(restart_paths):
    return SummaryReader(restart_paths)


@pytest.fixture(scope="module")
def full_run_reader():
    # SPE1CASE2 alone already spans the full 123 timesteps that the restart run
    # re-simulates the tail of, so it's the ground truth the stitched result must match.
    return SummaryReader([str(DATA_DIR / "SPE1CASE2")])


# ---------------------------------------------------------------------------
# __init__ (through SummaryReader, real files + synthetic warning)
# ---------------------------------------------------------------------------


def test_no_smspec_file_found_warns_and_skips_that_path(tmp_path):
    with pytest.warns(UserWarning, match="No .SMSPEC found"):
        sr = SummaryReader([CASE1, str(tmp_path / "MISSING")])

    assert len(sr.smry) == 1


# ---------------------------------------------------------------------------
# SummaryReader.read / available_keywords / summary_dates - single run
# ---------------------------------------------------------------------------


def test_read_returns_full_array_for_keyword(reader):
    fopr = reader.read("FOPR")

    assert fopr.shape == (123,)
    np.testing.assert_allclose(fopr[0], 20000.0)


def test_available_keywords_lists_dataset_keywords(reader):
    assert "FOPR" in reader.available_keywords()


def test_summary_dates_match_dataset(reader):
    dates = reader.summary_dates()

    assert len(dates) == 123
    assert dates[0] == dt.datetime(2015, 1, 2)
    assert dates[-1] == dt.datetime(2024, 12, 29)


# ---------------------------------------------------------------------------
# SummaryReader - restart behavior (SPE1CASE2 + SPE1CASE2_RESTART_60)
# ---------------------------------------------------------------------------


def test_restart_time_series_has_no_overlap_and_stays_sorted(restart_reader):
    times = restart_reader.summary_dates()

    assert len(times) == 123
    assert len(set(times)) == len(times)
    assert times == sorted(times)
    assert times[0] == dt.datetime(2015, 1, 2)
    assert times[-1] == dt.datetime(2024, 12, 29)


def test_restart_time_indices_split_at_the_overlap(restart_reader):
    # The restart run duplicates the main run's last 60 of 123 steps, so the main
    # run should only contribute its first 63 steps, and the restart run all 60 of
    # its own.
    assert restart_reader.time_ind[0] == list(range(63))
    assert restart_reader.time_ind[1] == list(range(60))


def test_restart_read_matches_equivalent_continuous_run(restart_reader, full_run_reader):
    stitched = restart_reader.read("FOPR")
    continuous = full_run_reader.read("FOPR")

    assert stitched.shape == continuous.shape == (123,)
    np.testing.assert_allclose(stitched, continuous)


def test_restart_summary_dates_match_equivalent_continuous_run(restart_reader, full_run_reader):
    assert restart_reader.summary_dates() == full_run_reader.summary_dates()


def test_restart_available_keywords(restart_reader):
    assert "FOPR" in restart_reader.available_keywords()


# ---------------------------------------------------------------------------
# _time_and_indices - restart-stitching edge cases (regression tests with
# synthetic stand-ins; the real dataset above only exercises an exact,
# whole-tail overlap between exactly two files)
# ---------------------------------------------------------------------------


class _FakeEsmry:
    """Minimal stand-in for ESmry exposing just what _time_and_indices/read need."""

    def __init__(self, start_date, time_days, data):
        self.start_date = start_date
        self._time_days = time_days
        self._data = data

    def __getitem__(self, keyword):
        if keyword == "TIME":
            return np.array(self._time_days, dtype=float)
        return np.array(self._data[keyword])


def _bypass_summary_init(smry):
    """Build a SummaryReader from fake ESmry stand-ins, without touching real files."""
    obj = object.__new__(SummaryReader)
    obj.smry = smry
    obj._time_and_indices()
    return obj


def test_time_indices_stay_within_bounds_across_chained_restarts():
    # Three files, each restarting from a point inside the previous file's tail (days
    # 8-9 and 13-14 are reported by two files each). Before the fix, each file's index
    # list was built from indices into the *cumulative* time series rather than its own,
    # so with three or more files it could exceed that file's own array length.
    start = dt.datetime(2020, 1, 1)
    main = _FakeEsmry(start, list(range(10)), {"X": list(range(100, 110))})
    restart_1 = _FakeEsmry(
        start, [8, 9, 10, 11, 12, 13, 14], {"X": [208, 209, 210, 211, 212, 213, 214]}
    )
    restart_2 = _FakeEsmry(start, [13, 14, 15, 16, 17], {"X": [313, 314, 315, 316, 317]})

    sr = _bypass_summary_init([main, restart_1, restart_2])

    assert sr.time == sorted(sr.time)
    assert sr.time_ind[0] == list(range(8))  # days 0-7, superseded from day 8 onward
    assert sr.time_ind[1] == list(range(5))  # days 8-12, superseded from day 13 onward
    assert sr.time_ind[2] == list(range(5))  # days 13-17, all kept

    x = sr.read("X")
    # Later files win at every overlap: day 8-9 come from restart_1, day 13-14 from restart_2.
    np.testing.assert_array_equal(
        x,
        [100, 101, 102, 103, 104, 105, 106, 107, 208, 209, 210, 211, 212, 313, 314, 315, 316, 317],
    )


def test_non_trailing_overlap_keeps_series_chronological():
    # The restart's first reported day (1) matches an entry in the *middle* of what's
    # already kept, not the trailing entry. Before the fix, only the exactly-matching
    # entry was dropped, leaving days 2-3 in place and appending the restart's days 4-5
    # after them - producing a non-chronological time series.
    start = dt.datetime(2020, 1, 1)
    main = _FakeEsmry(start, [0, 1, 2, 3], {"X": [100, 101, 102, 103]})
    restart = _FakeEsmry(start, [1, 4, 5], {"X": [201, 204, 205]})

    sr = _bypass_summary_init([main, restart])

    assert sr.time == sorted(sr.time)
    assert sr.time == [
        start + dt.timedelta(days=d) for d in (0, 1, 4, 5)
    ]
    np.testing.assert_array_equal(sr.read("X"), [100, 201, 204, 205])
