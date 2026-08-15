""" Unit tests for opm_vis.utils.timeline """
import csv
import datetime as dt
import io
import json

import pytest

from opm_vis.utils.timeline import (
    DAYS_PER_YEAR,
    TIMELINE_FORMATS,
    format_timeline,
    timeline_entries,
)

# A small hand-built case: report steps that are neither contiguous nor starting at a round
# date, so filtering and elapsed-time arithmetic are checked independently of any dataset.
RSTEPS = [0, 5, 10]
RDATES = [
    dt.datetime(2015, 1, 1),
    dt.datetime(2015, 1, 31),
    dt.datetime(2016, 1, 1),
]


@pytest.fixture
def entries():
    return timeline_entries(RSTEPS, RDATES)


# ---------------------------------------------------------------------------
# timeline_entries
# ---------------------------------------------------------------------------


def test_entries_pair_every_report_step_with_its_date(entries):
    assert [entry["rstep"] for entry in entries] == RSTEPS
    assert [entry["date"] for entry in entries] == RDATES


def test_elapsed_days_are_measured_from_the_first_report_date(entries):
    assert [entry["days"] for entry in entries] == [0, 30, 365]


def test_elapsed_years_divide_days_by_the_summary_convention(entries):
    assert entries[2]["years"] == pytest.approx(365 / DAYS_PER_YEAR)
    assert DAYS_PER_YEAR == 365.25


def test_filter_keeps_the_selection_in_the_cases_own_order():
    entries = timeline_entries(RSTEPS, RDATES, [10, 0])

    assert [entry["rstep"] for entry in entries] == [0, 10]


def test_filter_ignores_report_steps_the_case_does_not_have():
    entries = timeline_entries(RSTEPS, RDATES, [5, 999])

    assert [entry["rstep"] for entry in entries] == [5]


def test_filter_does_not_move_time_zero():
    # Elapsed time is always measured from the case's first report date, even when that report
    # step is filtered out
    entries = timeline_entries(RSTEPS, RDATES, [10])

    assert entries[0]["days"] == 365


def test_a_report_step_repeated_by_a_restart_run_is_listed_once():
    # A main run and a restart of it both report the step the restart branches from; the first
    # occurrence wins, as it does in Report.report_date()
    entries = timeline_entries(
        [0, 5, 5, 10],
        [
            dt.datetime(2015, 1, 1),
            dt.datetime(2015, 1, 31),
            dt.datetime(2015, 1, 31),
            dt.datetime(2016, 1, 1),
        ],
    )

    assert [entry["rstep"] for entry in entries] == [0, 5, 10]


def test_empty_report_steps_raise(entries):
    with pytest.raises(ValueError, match="No report steps found"):
        timeline_entries([], [])


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="must match"):
        timeline_entries(RSTEPS, RDATES[:2])


# ---------------------------------------------------------------------------
# format_timeline
# ---------------------------------------------------------------------------


def test_table_has_a_header_and_one_line_per_entry(entries):
    lines = format_timeline(entries).splitlines()

    assert lines[0].split() == ["Report", "step", "Date", "Days", "Years"]
    assert len(lines) == 1 + len(entries)
    assert lines[1].split() == ["0", "01.01.2015", "0", "0.000"]
    assert lines[3].split() == ["10", "01.01.2016", "365", "0.999"]


def test_table_columns_are_aligned(entries):
    lines = format_timeline(entries).splitlines()

    assert len({len(line) for line in lines}) == 1


def test_table_is_the_default_format(entries):
    assert format_timeline(entries) == format_timeline(entries, "table")


def test_csv_parses_back_into_rows(entries):
    rows = list(csv.reader(io.StringIO(format_timeline(entries, "csv"))))

    assert rows[0] == ["rstep", "date", "days", "years"]
    assert len(rows) == 1 + len(entries)
    assert rows[3] == ["10", "2016-01-01", "365", "0.999316"]


def test_json_round_trips(entries):
    parsed = json.loads(format_timeline(entries, "json"))

    assert len(parsed) == len(entries)
    assert parsed[0] == {"rstep": 0, "date": "2015-01-01", "days": 0, "years": 0.0}
    assert parsed[2]["date"] == "2016-01-01"


def test_unknown_format_raises(entries):
    with pytest.raises(ValueError, match="fmt must be one of"):
        format_timeline(entries, "yaml")


def test_every_advertised_format_renders(entries):
    for fmt in TIMELINE_FORMATS:
        assert format_timeline(entries, fmt).strip()
