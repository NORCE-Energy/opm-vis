""" Tests for the opm-vis-sum CLI, backed by the SPE1CASE1/SPE1CASE2 summary test datasets """
import shutil
from pathlib import Path

import click
import matplotlib
import pytest
from click.testing import CliRunner

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from opm_vis.cli.common import (  # noqa: E402
    default_summary_output_name,
    resolve_subplot_layout,
    resolve_summary_keywords,
)
from opm_vis.cli.summary_cli import main  # noqa: E402

# The case1/data_dir fixtures come from conftest.py: SPE1CASE1 has 123 summary timesteps from
# 2015-01-02 to 2024-12-29, in field units, with FOPR, FGOR, WBHP:PROD and one vector per well.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(scope="module")
def compare_paths(tmp_path_factory, data_dir):
    # SPE1CASE2 and SPE1CASE2_RESTART_60 share the "SPE1CASE2" filename prefix in tests/data, so
    # glob("...SPE1CASE2*.SMSPEC") would ambiguously match both - each is copied into its own
    # directory, mirroring how separate runs are kept in practice. tests/test_summary.py carries
    # the same fixture for the same reason.
    base = tmp_path_factory.mktemp("cli_compare_data")
    first = base / "runA"
    second = base / "runB"
    first.mkdir()
    second.mkdir()

    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / f"SPE1CASE2{ext}", first / f"CASE{ext}")
        shutil.copy(data_dir / f"SPE1CASE2_RESTART_60{ext}", second / f"CASE{ext}")

    return [str(first / "CASE"), str(second / "CASE")]


# ---------------------------------------------------------------------------
# resolve_summary_keywords
# ---------------------------------------------------------------------------


def test_keywords_expand_a_wildcard():
    available = ["FOPR", "WOPR:INJ", "WOPR:PROD"]

    assert resolve_summary_keywords(["WOPR:*"], available) == ["WOPR:INJ", "WOPR:PROD"]


def test_keywords_keep_the_order_they_were_given():
    assert resolve_summary_keywords(["FGOR", "FOPR"], ["FOPR", "FGOR"]) == ["FGOR", "FOPR"]


def test_keywords_are_not_repeated_across_patterns():
    assert resolve_summary_keywords(["FOPR", "F*"], ["FOPR", "FGOR"]) == ["FOPR", "FGOR"]


def test_keywords_reject_a_pattern_matching_nothing():
    with pytest.raises(click.UsageError, match="No summary vector matches"):
        resolve_summary_keywords(["Z*"], ["FOPR"])


def test_keywords_reject_an_unknown_name():
    # A plain name and an over-narrow pattern need different advice
    with pytest.raises(click.UsageError, match="is not a summary vector"):
        resolve_summary_keywords(["NOPE"], ["FOPR"])


def test_keywords_match_case_sensitively():
    # fnmatchcase, so the result does not depend on the platform's file name casing
    with pytest.raises(click.UsageError, match="is not a summary vector"):
        resolve_summary_keywords(["fopr"], ["FOPR"])


# ---------------------------------------------------------------------------
# resolve_subplot_layout
# ---------------------------------------------------------------------------


def test_layout_defaults_to_the_plotters_own_grid():
    assert resolve_subplot_layout(None, True, 4) is None


def test_layout_is_kept_when_it_fits():
    assert resolve_subplot_layout((2, 2), True, 4) == (2, 2)


def test_layout_without_subplots_is_rejected():
    with pytest.raises(click.UsageError, match="only shapes the --subplots grid"):
        resolve_subplot_layout((2, 2), False, 1)


def test_layout_values_must_be_at_least_one():
    with pytest.raises(click.UsageError, match="at least 1"):
        resolve_subplot_layout((0, 2), True, 1)


def test_layout_too_small_is_rejected():
    with pytest.raises(click.UsageError, match="has room for 2 of the 3 keywords"):
        resolve_subplot_layout((1, 2), True, 3)


# ---------------------------------------------------------------------------
# default_summary_output_name
# ---------------------------------------------------------------------------


def test_default_name_for_one_keyword():
    assert default_summary_output_name(["FOPR"]) == "FOPR_date.png"


def test_default_name_sanitizes_mnemonic_separators():
    name = default_summary_output_name(["WOPR:PROD", "BPR:1,1,1"])

    assert name == "WOPR-PROD_BPR-1-1-1_date.png"


def test_default_name_counts_extra_keywords():
    name = default_summary_output_name(["A", "B", "C", "D", "E"])

    assert name == "A_B_C_and2more_date.png"


def test_default_name_marks_compare_and_x_axis():
    name = default_summary_output_name(["FOPR"], x_axis="years", compare=True)

    assert name == "FOPR_compare_years.png"


# ---------------------------------------------------------------------------
# opm-vis-sum - plots that are written to file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "options",
    [
        ["-K", "FOPR"],
        ["-K", "FOPR", "-K", "FGOR"],
        ["-K", "WOPR:*"],
        ["-K", "FOPR", "--x-axis", "days"],
        ["-K", "FOPR", "--x-axis", "years"],
        ["-K", "FOPR", "-K", "FGOR", "--subplots"],
        ["-K", "FOPR", "-K", "FGOR", "--subplots", "--layout", "2", "1"],
        ["-K", "FOPR", "--log-y"],
        ["-K", "FOPR", "--xlim", "2016-01-01", "2020-01-01"],
        ["-K", "FOPR", "--x-axis", "days", "--xlim", "0", "1000"],
        ["-K", "FOPR", "--ylim", "0", "25000"],
        ["-K", "FOPR", "--title", "Field rates", "--figsize", "8", "4", "--no-grid",
         "--no-legend"],
    ],
)
def test_plot_is_written_to_file(case1, runner, tmp_path, options):
    out = tmp_path / "plot.png"
    result = runner.invoke(main, [case1, *options, "-s", str(out)])

    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# opm-vis-sum - generated file names
# ---------------------------------------------------------------------------


def test_save_with_no_path_generates_a_name(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, [case1, "-K", "FOPR", "--save"])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_date.png").exists()


def test_save_with_no_path_reflects_the_x_axis(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, [case1, "-K", "FOPR", "--x-axis", "years", "--save"])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_years.png").exists()


def test_save_with_no_path_expands_a_wildcard_into_the_name(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, [case1, "-K", "WOPR:*", "--save"])

        assert result.exit_code == 0, result.output
        assert Path("WOPR-INJ_WOPR-PROD_date.png").exists()


def test_compare_marks_the_generated_name(compare_paths, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["--compare", *compare_paths, "-K", "FOPR", "--save"])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_compare_date.png").exists()


# ---------------------------------------------------------------------------
# opm-vis-sum - PATHS, restart chain and --compare
# ---------------------------------------------------------------------------


def test_restart_chain_is_stitched_by_default(compare_paths, runner, tmp_path):
    out = tmp_path / "chain.png"
    result = runner.invoke(main, [*compare_paths, "-K", "FOPR", "-s", str(out)])

    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 0


def test_compare_plots_each_path_as_its_own_case(compare_paths, runner, tmp_path):
    out = tmp_path / "compare.png"
    result = runner.invoke(main, ["--compare", *compare_paths, "-K", "FOPR", "-s", str(out)])

    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 0


def test_compare_needs_two_paths(case1, runner):
    result = runner.invoke(main, [case1, "--compare", "-K", "FOPR"])

    assert result.exit_code != 0
    assert "--compare needs at least two PATHS" in result.output


def test_paths_default_to_the_working_directory(data_dir, runner, tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / f"SPE1CASE1{ext}", case_dir / f"SPE1CASE1{ext}")
    monkeypatch.chdir(case_dir)

    result = runner.invoke(main, ["-K", "FOPR", "--save"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "FOPR_date.png").exists()


# ---------------------------------------------------------------------------
# opm-vis-sum - --list-keywords
# ---------------------------------------------------------------------------


def test_list_keywords_prints_the_case_vectors(case1, runner):
    result = runner.invoke(main, [case1, "--list-keywords"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "FOPR" in lines
    assert lines == sorted(lines)


def test_list_keywords_with_a_keyword_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "--list-keywords", "-K", "FOPR"])

    assert result.exit_code != 0
    assert "--list-keywords only prints" in result.output
    assert "-K/--keyword" in result.output


def test_list_keywords_with_a_default_valued_option_is_rejected(case1, runner):
    # --no-grid leaves --grid at a *falsy* value of a truthy-defaulted option, so only click's
    # parameter source can tell it was typed at all
    result = runner.invoke(main, [case1, "--list-keywords", "--no-grid"])

    assert result.exit_code != 0
    assert "--grid/--no-grid" in result.output


# ---------------------------------------------------------------------------
# opm-vis-sum - usage errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "options, message",
    [
        ([], "Pass -K/--keyword at least once"),
        (["-K", "NOPE"], "is not a summary vector"),
        (["-K", "Z*"], "No summary vector matches"),
        (["-K", "FOPR", "--layout", "2", "2"], "only shapes the --subplots grid"),
        (
            ["-K", "FOPR", "-K", "FGOR", "-K", "WBHP:PROD", "--subplots", "--layout", "1", "2"],
            "has room for 2 of the 3 keywords",
        ),
        (["-K", "FOPR", "--xlim", "0", "1000"], "must be ISO dates"),
        (
            ["-K", "FOPR", "--x-axis", "days", "--xlim", "2016-01-01", "2020-01-01"],
            "must be numbers",
        ),
        (["-K", "FOPR", "--xlim", "2020-01-01", "2016-01-01"], "--xlim MIN MAX must be increasing"),
        (["-K", "FOPR", "--ylim", "10", "0"], "--ylim MIN MAX must be increasing"),
        (["-K", "FOPR", "--figsize", "0", "4"], "must both be positive"),
        (["-K", "FOPR", "--x-axis", "time"], "Invalid value for"),
    ],
)
def test_usage_errors_are_clean(case1, runner, options, message):
    result = runner.invoke(main, [case1, *options])

    assert result.exit_code != 0
    assert message in result.output
    assert "Traceback" not in result.output


def test_no_summary_files_is_a_clean_error(runner, tmp_path):
    with pytest.warns(UserWarning, match="No .SMSPEC found"):
        result = runner.invoke(main, [str(tmp_path / "MISSING"), "-K", "FOPR"])

    assert result.exit_code != 0
    assert "No .SMSPEC file was found" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# opm-vis-sum - plumbing
# ---------------------------------------------------------------------------


def test_bare_invocation_shows_help(runner):
    result = runner.invoke(main, [])

    assert "Usage:" in result.output


def test_help_flag_short_form(runner):
    result = runner.invoke(main, ["-h"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
