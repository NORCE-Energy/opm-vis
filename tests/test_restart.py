""" Unit tests for opm_vis.utils.restart, backed by the SPE1CASE1 UNRST test dataset """
import datetime as dt
import shutil

import numpy as np
import pytest

from opm_vis.utils.restart import Report, RestartReader, Wells

# The case1/data_dir fixtures come from conftest.py.
#
# SPE1CASE1 has 121 report steps (0-120), two wells (PROD, INJ) that stay open at
# fixed locations for the whole run, and no report step besides 0 lacks well data -
# so the "well data present but not at rstep 0" branch of Wells is exercised by the
# real dataset, while the report-step alignment itself (the thing most likely to
# silently regress) is verified below with a small synthetic stand-in.


@pytest.fixture(scope="module")
def reader(case1):
    return RestartReader([case1])


@pytest.fixture(scope="module")
def report(case1):
    return Report([case1])


@pytest.fixture(scope="module")
def wells(case1):
    return Wells([case1])


# ---------------------------------------------------------------------------
# _RestartFiles.__init__ (through RestartReader, real files + synthetic warnings)
# ---------------------------------------------------------------------------


def test_no_restart_files_found_warns_and_skips(tmp_path):
    with pytest.warns(UserWarning, match="No .UNRST or .X files found"):
        rr = RestartReader([str(tmp_path / "MISSING")])
    assert rr.rst == []


def test_multiple_unrst_files_warns_and_loads_first(tmp_path, data_dir):
    shutil.copy(data_dir / "SPE1CASE1.UNRST", tmp_path / "CASE1.UNRST")
    shutil.copy(data_dir / "SPE1CASE1.UNRST", tmp_path / "CASE2.UNRST")

    with pytest.warns(UserWarning, match="Multiple .UNRST files"):
        rr = RestartReader([str(tmp_path / "CASE")])
    assert len(rr.rst) == 1


def test_unrst_and_x_files_together_warns_and_loads_unrst(tmp_path, data_dir):
    shutil.copy(data_dir / "SPE1CASE1.UNRST", tmp_path / "CASE.UNRST")
    (tmp_path / "CASE.X0001").touch()

    with pytest.warns(UserWarning, match="There are .UNRST and .X files"):
        rr = RestartReader([str(tmp_path / "CASE")])
    assert len(rr.rst) == 1
    assert rr.available_keywords(0) == ["SEQNUM", "PRESSURE", "RS", "SGAS", "SWAT"]


# ---------------------------------------------------------------------------
# RestartReader
# ---------------------------------------------------------------------------


def test_read_returns_full_array_for_keyword(reader):
    pressure = reader.read("PRESSURE", 1)

    assert pressure.shape == (300,)  # SPE1CASE1 is a 10x10x3 grid, fully active
    np.testing.assert_allclose(pressure[0], 6058.3247, rtol=1e-5)


def test_read_applies_active_indices(reader):
    pressure = reader.read("PRESSURE", 1, act=[2, 0])

    full = reader.read("PRESSURE", 1)
    np.testing.assert_allclose(pressure, full[[2, 0]])


def test_read_raises_for_missing_report_step(reader):
    with pytest.raises(ValueError, match="Report step 999"):
        reader.read("PRESSURE", 999)


def test_available_keywords_filters_ignored_mnemonics(reader):
    assert reader.available_keywords(1) == ["SEQNUM", "PRESSURE", "RS", "SGAS", "SWAT"]


def test_available_keywords_raises_for_missing_report_step(reader):
    with pytest.raises(ValueError, match="Report step 999"):
        reader.available_keywords(999)


def test_intehead_reads_requested_item(reader):
    assert reader.intehead(16, 1) == 2  # nwells


def test_intehead_raises_for_missing_report_step(reader):
    with pytest.raises(ValueError, match="INTEHEAD item 16"):
        reader.intehead(16, 999)


def test_unit_convention_for_field_units(reader):
    assert reader.unit_convention() == "field"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_report_steps_and_dates_match_dataset(report):
    assert report.report_steps() == list(range(121))
    assert report.report_dates()[0] == dt.datetime(2015, 1, 1)
    assert report.report_dates()[-1] == dt.datetime(2024, 12, 29)


def test_report_date_looks_up_by_report_step(report):
    assert report.report_date(0) == dt.datetime(2015, 1, 1)
    assert report.report_date(120) == dt.datetime(2024, 12, 29)


def test_report_start_date_is_the_first_report_date(report):
    assert report.start_date() == dt.datetime(2015, 1, 1)


def test_report_start_date_raises_without_restart_files(tmp_path):
    with pytest.warns(UserWarning, match="No .UNRST or .X files found"):
        empty = Report([str(tmp_path / "MISSING")])

    with pytest.raises(ValueError, match="cannot determine the start date"):
        empty.start_date()


def test_report_elapsed_time_since_simulation_start(report):
    assert report.elapsed_days(0) == 0
    assert report.elapsed_days(120) == 3650  # cross-checked against TIME in SPE1CASE1.UNSMRY
    assert report.elapsed_years(120) == pytest.approx(9.9931555, abs=1e-6)


def test_report_timeline_covers_every_report_step(report):
    entries = report.timeline()

    assert len(entries) == 121
    assert entries[0] == {
        "rstep": 0,
        "date": dt.datetime(2015, 1, 1),
        "days": 0,
        "years": 0.0,
    }


def test_report_timeline_takes_a_selection(report):
    assert [entry["rstep"] for entry in report.timeline([0, 120])] == [0, 120]


def test_report_format_timeline_renders_csv(report):
    output = report.format_timeline("csv", [120])

    assert output.splitlines() == ["rstep,date,days,years", "120,2024-12-29,3650,9.993155"]


def test_report_str_formats_table(report):
    lines = str(report).splitlines()

    assert lines[0].split() == ["Report", "step", "Date", "Days", "Years"]
    assert lines[1].split() == ["0", "01.01.2015", "0", "0.000"]
    assert lines[-1].split() == ["120", "29.12.2024", "3650", "9.993"]


# ---------------------------------------------------------------------------
# Wells - real dataset (happy path)
# ---------------------------------------------------------------------------


def test_wells_report_step_zero_has_no_well_data(wells):
    assert wells[0] == {}


def test_wells_report_step_returns_well_info(wells):
    assert wells[1] == {
        "PROD": [9, 9, 2, True],
        "INJ": [0, 0, 0, True],
    }


def test_wells_iter_yields_one_entry_per_report_step(wells):
    entries = list(wells)

    assert len(entries) == 121
    assert entries[0] == {}
    assert entries[1] == {"PROD": [9, 9, 2, True], "INJ": [0, 0, 0, True]}


# ---------------------------------------------------------------------------
# Wells - report-step alignment (regression test with a synthetic restart file)
# ---------------------------------------------------------------------------


class _FakeErst:
    """Minimal stand-in for ERst exposing just what Wells needs.

    well_by_step maps a report step to well info (name, i, j, k, status), or to
    None for a report step with no well data (mirrors real report step 0).
    """

    def __init__(self, report_steps, well_by_step):
        self.report_steps = report_steps
        self._well_by_step = well_by_step

    def arrays(self, rstep):
        if self._well_by_step[rstep] is None:
            return [("SEQNUM", None, 1)]
        return [("ZWEL", None, 1), ("ICON", None, 1)]

    def __getitem__(self, key):
        keyword, rstep = key
        well = self._well_by_step[rstep]

        if keyword == "INTEHEAD":
            intehead = [0] * 40
            if well is not None:
                intehead[16] = 1  # nwells
                intehead[17] = 1  # ncwmax
                intehead[24] = 11  # niwelz
                intehead[32] = 4  # niconz
            return intehead
        if keyword == "ZWEL":
            return [well["name"], "", ""]
        if keyword == "IWEL":
            iwel = [0] * 11
            iwel[0] = well["i"] + 1
            iwel[1] = well["j"] + 1
            iwel[10] = 1 if well["status"] else 0
            return iwel
        if keyword == "ICON":
            icon = [0] * 4
            icon[3] = well["k"] + 1
            return icon
        raise KeyError(key)


def _bypass_wells_init(rst):
    """Create a Wells instance without running __init__ (no real files needed).

    Reproduces the report-step index that _RestartFiles.__init__ normally builds,
    since object.__new__ skips it.
    """
    obj = object.__new__(Wells)
    obj.rst = rst

    obj._step_index = {}
    obj._erst_step_offsets = []
    offset = 0
    for erst_idx, erst in enumerate(rst):
        obj._erst_step_offsets.append(offset)
        for local_idx, rstep in enumerate(erst.report_steps):
            obj._step_index.setdefault(rstep, (erst_idx, local_idx))
        offset += len(erst.report_steps)

    obj._well_info_all_report_steps()
    return obj


def test_wells_alignment_survives_a_skipped_report_step():
    # Report step 0 has no well data (like the real dataset); steps 5 and 10 have
    # distinct well info. Before the off-by-one fix, skipping step 0 without
    # advancing the fill index shifted step 5's data into step 0's slot and step
    # 10's data into step 5's slot.
    fake = _FakeErst(
        report_steps=[0, 5, 10],
        well_by_step={
            0: None,
            5: {"name": "A", "i": 1, "j": 2, "k": 3, "status": True},
            10: {"name": "A", "i": 9, "j": 8, "k": 7, "status": False},
        },
    )
    obj = _bypass_wells_init([fake])

    assert obj[0] == {}
    assert obj[5] == {"A": [1, 2, 3, True]}
    assert obj[10] == {"A": [9, 8, 7, False]}


def test_wells_alignment_survives_a_step_missing_well_keywords():
    # Step 5 has ZWEL/ICON, step 7 doesn't (e.g. RPTRST output at lower frequency
    # than the report steps) - the fill index must still advance for step 7.
    fake = _FakeErst(
        report_steps=[5, 7, 10],
        well_by_step={
            5: {"name": "A", "i": 1, "j": 2, "k": 3, "status": True},
            7: None,
            10: {"name": "A", "i": 4, "j": 5, "k": 6, "status": False},
        },
    )
    obj = _bypass_wells_init([fake])

    assert obj[5] == {"A": [1, 2, 3, True]}
    assert obj[7] == {}
    assert obj[10] == {"A": [4, 5, 6, False]}


def test_wells_raises_value_error_on_zwel_intehead_mismatch():
    class _MismatchErst(_FakeErst):
        """Claims 2 wells in INTEHEAD while ZWEL only ever has 1."""

        def __getitem__(self, key):
            value = super().__getitem__(key)
            if key[0] == "INTEHEAD":
                value[16] = 2
            return value

    fake = _MismatchErst(
        report_steps=[1],
        well_by_step={1: {"name": "A", "i": 0, "j": 0, "k": 0, "status": True}},
    )

    with pytest.raises(ValueError, match="does not correspond"):
        _bypass_wells_init([fake])
