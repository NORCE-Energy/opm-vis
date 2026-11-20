""" Tests for the opm-vis-rdates CLI, backed by the SPE1CASE1 test dataset """
import csv
import io
import json

import click
import pytest
from click.testing import CliRunner

from opm_vis.cli.common import resolve_rstep_selection
from opm_vis.cli.rdates_cli import main

# The case1_dir fixture comes from conftest.py: SPE1CASE1 has report steps 0-120, running from
# 2015-01-01 to 2024-12-29 (3650 days, 9.993 years).


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# resolve_rstep_selection
# ---------------------------------------------------------------------------


def test_selection_defaults_to_every_report_step():
    assert resolve_rstep_selection([0, 5, 10], None) == [0, 5, 10]


def test_selection_takes_a_single_report_step():
    assert resolve_rstep_selection([0, 5, 10], "5") == [5]


def test_selection_takes_a_range():
    assert resolve_rstep_selection([0, 5, 10], "0:5") == [0, 5]


def test_selection_takes_a_range_with_a_step():
    assert resolve_rstep_selection([0, 5, 10, 15], "0:15:10") == [0, 10]


def test_selection_rejects_a_missing_report_step():
    with pytest.raises(click.UsageError, match="Report step 999"):
        resolve_rstep_selection([0, 5, 10], "999")


def test_selection_rejects_a_range_matching_nothing():
    with pytest.raises(click.UsageError, match="No report steps"):
        resolve_rstep_selection([0, 5, 10], "20:30")


def test_selection_rejects_a_non_integer():
    with pytest.raises(click.UsageError, match="must be an integer"):
        resolve_rstep_selection([0, 5, 10], "first")


# ---------------------------------------------------------------------------
# opm-vis-rdates
# ---------------------------------------------------------------------------


def test_lists_every_report_step_by_default(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == ["Report", "step", "Date", "Days", "Years"]
    assert len(lines) == 1 + 121
    assert lines[1].split() == ["0", "01.01.2015", "0", "0.000"]
    assert lines[-1].split() == ["120", "29.12.2024", "3650", "9.993"]


def test_single_report_step(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-r", "60"])

    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 2
    assert result.output.splitlines()[1].split() == ["60", "31.12.2019", "1825", "4.997"]


def test_report_step_range(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--rstep", "0:120:60"])

    assert result.exit_code == 0, result.output
    assert [line.split()[0] for line in result.output.splitlines()[1:]] == ["0", "60", "120"]


def test_missing_report_step_is_a_usage_error(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-r", "999"])

    assert result.exit_code != 0
    assert "Report step 999" in result.output


def test_csv_format(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-F", "csv", "-r", "0:120:120"])

    assert result.exit_code == 0, result.output
    rows = list(csv.reader(io.StringIO(result.output)))
    assert rows[0] == ["rstep", "date", "days", "years"]
    assert rows[2] == ["120", "2024-12-29", "3650", "9.993155"]


def test_json_format(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--format", "json", "-r", "120"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [
        {"rstep": 120, "date": "2024-12-29", "days": 3650, "years": 9.993155}
    ]


def test_save_writes_the_same_output_to_a_file(case1_dir, runner, tmp_path):
    output = tmp_path / "timeline.csv"

    result = runner.invoke(main, ["-f", case1_dir, "-F", "csv", "-r", "60", "-s", str(output)])

    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert output.read_text().splitlines() == [
        "rstep,date,days,years",
        "60,2019-12-31,1825,4.996578",
    ]


def test_no_restart_files_is_a_clean_error(data_dir, runner):
    # MAPAXES is a case, but an EGRID-only one with no restart files
    result = runner.invoke(main, ["-f", str(data_dir / "MAPAXES")])

    assert result.exit_code != 0
    assert "No report steps found" in result.output


def test_restart_in_the_same_folder_extends_the_timeline(case2_dir, runner):
    result = runner.invoke(main, ["-f", case2_dir, "-F", "csv", "-r", "0:120:120"])

    assert result.exit_code == 0, result.output
    assert [row.split(",")[0] for row in result.output.splitlines()[1:]] == ["0", "120"]
