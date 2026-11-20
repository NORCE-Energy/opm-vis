""" Tests for the opm-vis-sum CLI, backed by the SPE1CASE1/SPE1CASE2 summary test datasets """
import shutil
from pathlib import Path

import click
import matplotlib
import pytest
from click.testing import CliRunner

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from opm_vis.cli.common import (  # noqa: E402
    check_curve_option_count,
    default_summary_output_name,
    resolve_subplot_layout,
    resolve_summary_keywords,
)
from opm_vis.cli.summary_cli import main  # noqa: E402

# The case1_dir/data_dir fixtures come from conftest.py: SPE1CASE1 has 123 summary timesteps from
# 2015-01-02 to 2024-12-29, in field units, with FOPR, FGOR, WBHP:PROD and one vector per well.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(scope="module")
def compare_paths(tmp_path_factory, data_dir):
    # SPE1CASE2 and its restart SPE1CASE2_RESTART_60 are each copied into a folder of their own
    # under the same name, CASE, so the two can be told apart only by folder - which is what
    # --compare labels them by. Returned as -f/--folder arguments, one per folder.
    base = tmp_path_factory.mktemp("cli_compare_data")
    first = base / "runA"
    second = base / "runB"
    first.mkdir()
    second.mkdir()

    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / "SPE1CASE2" / f"SPE1CASE2{ext}", first / f"CASE{ext}")
        shutil.copy(data_dir / "SPE1CASE2" / f"SPE1CASE2_RESTART_60{ext}", second / f"CASE{ext}")

    return ["-f", str(first), "-f", str(second)]


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
# check_curve_option_count
# ---------------------------------------------------------------------------


def test_curve_option_count_accepts_none_given():
    check_curve_option_count("--linestyle", (), ["FOPR", "FGOR"])


def test_curve_option_count_accepts_one_value_for_all():
    check_curve_option_count("--linestyle", ("dashed",), ["FOPR", "FGOR"])


def test_curve_option_count_accepts_one_value_per_keyword():
    check_curve_option_count("--linestyle", ("dashed", "dotted"), ["FOPR", "FGOR"])


def test_curve_option_count_rejects_a_mismatched_count():
    with pytest.raises(click.UsageError, match="was given 2 times, but 3 keyword"):
        check_curve_option_count("--linestyle", ("dashed", "dotted"), ["FOPR", "FGOR", "FGPR"])


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
        ["-K", "FOPR", "--linewidth", "2.5"],
        ["-K", "FOPR", "--lw", "2.5"],
        ["-K", "FOPR", "--linestyle", "dashed"],
        ["-K", "FOPR", "--ls", "dashed"],
        ["-K", "FOPR", "--marker", "o"],
        ["-K", "FOPR", "--marker", "o", "--linestyle", "solid"],
        ["-K", "FOPR", "-K", "FGOR", "--ls", "dashed", "--ls", "dotted"],
        ["-K", "FOPR", "-K", "FGOR", "--marker", "o", "--marker", "s"],
        ["-K", "FOPR", "-K", "FGOR", "--ls", "dashed", "--marker", "o", "--marker", "s"],
        ["-K", "FOPR", "--color", "red"],
        ["-K", "FOPR", "-K", "FGOR", "--color", "red", "--color", "#00ff00"],
        ["-K", "FOPR", "-c", "red"],
    ],
)
def test_plot_is_written_to_file(case1_dir, runner, tmp_path, options):
    out = tmp_path / "out"
    result = runner.invoke(main, ["-f", case1_dir, *options, "-sf", str(out)])

    assert result.exit_code == 0, result.output
    assert all(f.stat().st_size > 0 for f in out.iterdir())


# ---------------------------------------------------------------------------
# opm-vis-sum - generated file names
# ---------------------------------------------------------------------------


def test_save_with_no_path_generates_a_name(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_date.png").exists()


def test_save_with_no_path_reflects_the_x_axis(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "--x-axis", "years", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_years.png").exists()


def test_save_with_no_path_expands_a_wildcard_into_the_name(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-K", "WOPR:*", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("WOPR-INJ_WOPR-PROD_date.png").exists()


def test_compare_marks_the_generated_name(compare_paths, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["--compare", *compare_paths, "-K", "FOPR", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("FOPR_compare_date.png").exists()


# ---------------------------------------------------------------------------
# opm-vis-sum - --export
# ---------------------------------------------------------------------------


def test_export_writes_a_csv_file(case1_dir, runner, tmp_path):
    csv_out = tmp_path / "rates.csv"
    png_out = tmp_path / "out"
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "FOPR", "-K", "FGOR", "--export", str(csv_out), "-sf", str(png_out)],
    )

    assert result.exit_code == 0, result.output
    lines = csv_out.read_text().splitlines()
    assert lines[0] == "date,FOPR,FGOR"


def test_export_with_no_path_prints_to_stdout(case1_dir, runner):
    # --save with no value also generates a file next to the case; run in an isolated
    # filesystem so that file lands in a throwaway directory, not the repo itself
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "--export", "-sf", "."])

    assert result.exit_code == 0, result.output
    assert "date,FOPR" in result.output


def test_export_and_save_both_write_their_own_file(case1_dir, runner, tmp_path):
    csv_out = tmp_path / "rates.csv"
    png_out = tmp_path / "out"
    result = runner.invoke(
        main, ["-f", case1_dir, "-K", "FOPR", "--export", str(csv_out), "-sf", str(png_out)]
    )

    assert result.exit_code == 0, result.output
    assert csv_out.stat().st_size > 0
    assert all(f.stat().st_size > 0 for f in png_out.iterdir())


def test_export_respects_x_axis(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["-f", case1_dir, "-K", "FOPR", "--x-axis", "years", "--export", "-sf", "."]
        )

    assert result.exit_code == 0, result.output
    assert result.output.startswith("years,FOPR")


def test_export_reflects_compare(compare_paths, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["--compare", *compare_paths, "-K", "FOPR", "--export", "-sf", "."]
        )

    assert result.exit_code == 0, result.output
    assert "runA/CASE:FOPR" in result.output
    assert "runB/CASE:FOPR" in result.output


def test_export_combined_with_list_keywords_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--list-keywords", "--export"])

    assert result.exit_code != 0
    assert "--export/-e" in result.output


# ---------------------------------------------------------------------------
# opm-vis-sum - --folder, restart chain and --compare
# ---------------------------------------------------------------------------


def test_restart_chain_is_stitched_by_default(compare_paths, runner, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(main, [*compare_paths, "-K", "FOPR", "-sf", str(out)])

    assert result.exit_code == 0, result.output
    assert all(f.stat().st_size > 0 for f in out.iterdir())


def test_compare_plots_each_path_as_its_own_case(compare_paths, runner, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(main, ["--compare", *compare_paths, "-K", "FOPR", "-sf", str(out)])

    assert result.exit_code == 0, result.output
    assert all(f.stat().st_size > 0 for f in out.iterdir())


def test_compare_needs_two_paths(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--compare", "-K", "FOPR"])

    assert result.exit_code != 0
    assert "--compare needs at least two -f/--folder" in result.output


def test_folder_defaults_to_the_working_directory(data_dir, runner, tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / "SPE1CASE1" / f"SPE1CASE1{ext}", case_dir / f"SPE1CASE1{ext}")
    monkeypatch.chdir(case_dir)

    result = runner.invoke(main, ["-K", "FOPR", "-s"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "sum-figs" / "FOPR_date.png").exists()


# ---------------------------------------------------------------------------
# opm-vis-sum - --list-keywords
# ---------------------------------------------------------------------------


def test_list_keywords_prints_the_case_vectors(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--list-keywords"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "FOPR" in lines
    assert lines == sorted(lines)


def test_list_keywords_with_a_keyword_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--list-keywords", "-K", "FOPR"])

    assert result.exit_code != 0
    assert "--list-keywords only prints" in result.output
    assert "-K/--keyword" in result.output


def test_list_keywords_with_a_default_valued_option_is_rejected(case1_dir, runner):
    # --no-grid leaves --grid at a *falsy* value of a truthy-defaulted option, so only click's
    # parameter source can tell it was typed at all
    result = runner.invoke(main, ["-f", case1_dir, "--list-keywords", "--no-grid"])

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
        (["-K", "FOPR", "--linewidth", "0"], "Invalid value for"),
        (["-K", "FOPR", "--linewidth", "-1"], "Invalid value for"),
        (["-K", "FOPR", "--linestyle", "bogus"], "Invalid value for"),
        (["-K", "FOPR", "--linestyle", "none"], "--linestyle none needs --marker"),
        (["-K", "FOPR", "--marker", "bogus-marker"], "Unrecognized marker style"),
        (
            ["-K", "FOPR", "-K", "FGOR", "-K", "WBHP:PROD", "--ls", "dashed", "--ls", "dotted"],
            "--linestyle was given 2 times, but 3 keyword",
        ),
        (
            ["-K", "FOPR", "-K", "FGOR", "--marker", "o", "--marker", "s", "--marker", "^"],
            "--marker was given 3 times, but 2 keyword",
        ),
        (
            ["-K", "FOPR", "-K", "FGOR", "--ls", "none", "--ls", "dashed"],
            "--linestyle none needs --marker as well for FOPR",
        ),
        (["-K", "FOPR", "--color", "not-a-color"], "not a valid value for color"),
        (
            ["-K", "FOPR", "-K", "FGOR", "-K", "WBHP:PROD", "--color", "red", "--color", "green"],
            "--color was given 2 times, but 3 keyword",
        ),
    ],
)
def test_usage_errors_are_clean(case1_dir, runner, options, message):
    result = runner.invoke(main, ["-f", case1_dir, *options])

    assert result.exit_code != 0
    assert message in result.output
    assert "Traceback" not in result.output


def test_no_summary_files_is_a_clean_error(data_dir, runner):
    # MAPAXES is a case, but an EGRID-only one with no summary files
    with pytest.warns(UserWarning, match="No .SMSPEC found"):
        result = runner.invoke(main, ["-f", str(data_dir / "MAPAXES"), "-K", "FOPR"])

    assert result.exit_code != 0
    assert "No .SMSPEC file was found" in result.output
    assert "Traceback" not in result.output


def test_folder_with_no_case_is_a_clean_error(runner, tmp_path):
    result = runner.invoke(main, ["-f", str(tmp_path), "-K", "FOPR"])

    assert result.exit_code != 0
    assert "No simulation case" in result.output
    assert "Traceback" not in result.output


def test_missing_folder_is_a_clean_error(runner, tmp_path):
    result = runner.invoke(main, ["-f", str(tmp_path / "MISSING"), "-K", "FOPR"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_restart_in_the_same_folder_is_stitched(case2_dir, runner, tmp_path):
    out = tmp_path / "out"
    result = runner.invoke(main, ["-f", case2_dir, "-K", "FOPR", "-sf", str(out)])

    assert result.exit_code == 0, result.output
    assert all(f.stat().st_size > 0 for f in out.iterdir())


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


# ---------------------------------------------------------------------------
# --save / --save-folder
# ---------------------------------------------------------------------------


@pytest.fixture
def case1_copy(data_dir, tmp_path):
    # A writable copy of SPE1CASE1's summary files, since --save's default folder goes inside
    # -f/--folder, which must not be tests/data itself
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / "SPE1CASE1" / f"SPE1CASE1{ext}", case_dir / f"SPE1CASE1{ext}")
    return case_dir


def test_save_creates_the_sum_figs_folder_inside_the_case_folder(case1_copy, runner):
    result = runner.invoke(main, ["-f", str(case1_copy), "-K", "FOPR", "-s"])

    assert result.exit_code == 0, result.output
    assert f"Created folder {case1_copy / 'sum-figs'}" in result.output
    assert (case1_copy / "sum-figs" / "FOPR_date.png").exists()


def test_save_into_an_existing_folder_is_silent(case1_copy, runner):
    (case1_copy / "sum-figs").mkdir()
    result = runner.invoke(main, ["-f", str(case1_copy), "-K", "FOPR", "-s"])

    assert result.exit_code == 0, result.output
    assert "Created folder" not in result.output
    assert (case1_copy / "sum-figs" / "FOPR_date.png").exists()


def test_save_goes_inside_the_first_of_several_folders(data_dir, tmp_path, runner):
    main_dir = tmp_path / "main"
    restart_dir = tmp_path / "restart"
    for folder, name in ((main_dir, "SPE1CASE2"), (restart_dir, "SPE1CASE2_RESTART_60")):
        folder.mkdir()
        for ext in (".SMSPEC", ".UNSMRY"):
            shutil.copy(data_dir / "SPE1CASE2" / f"{name}{ext}", folder / f"CASE{ext}")

    result = runner.invoke(
        main, ["-f", str(main_dir), "-f", str(restart_dir), "-K", "FOPR", "-s"]
    )

    assert result.exit_code == 0, result.output
    assert (main_dir / "sum-figs" / "FOPR_date.png").exists()
    assert not (restart_dir / "sum-figs").exists()


def test_save_folder_implies_save_and_creates_nested_folders(case1_dir, runner, tmp_path):
    folder = tmp_path / "plots" / "rates"
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sf", str(folder)])

    assert result.exit_code == 0, result.output
    assert f"Created folder {folder}" in result.output
    assert (folder / "FOPR_date.png").exists()


def test_save_folder_that_is_a_file_is_rejected(case1_dir, runner, tmp_path):
    existing = tmp_path / "afile"
    existing.touch()
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sf", str(existing)])

    assert result.exit_code != 0
    assert "is a file" in result.output


def test_font_scale_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "--font-scale", "1.5", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_font_scale_must_be_positive(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "--font-scale", "0"])

    assert result.exit_code != 0
    assert "--font-scale" in result.output


def test_font_scale_does_not_leak_into_later_plots(case1_dir, runner, tmp_path):
    before = matplotlib.rcParams["font.size"]

    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "--font-scale", "2", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert matplotlib.rcParams["font.size"] == before


# ---------------------------------------------------------------------------
# --save-name
# ---------------------------------------------------------------------------


def test_save_name_replaces_the_generated_name(case1_dir, runner, tmp_path):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sn", "my plot", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["my plot.png"]


def test_save_name_already_ending_in_the_suffix_keeps_it_once(case1_dir, runner, tmp_path):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sn", "plot.png", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["plot.png"]


def test_save_name_implies_save(data_dir, runner, tmp_path):
    # A writable copy of the case, since the default save folder goes inside -f/--folder
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, tmp_path / source.name)

    result = runner.invoke(main, ["-f", str(tmp_path), "-K", "FOPR", "-sn", "plot"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "sum-figs" / "plot.png").exists()


@pytest.mark.parametrize(("name", "message"), [("out/plot", "without a folder"), ("", "empty")])
def test_save_name_must_be_a_plain_file_name(case1_dir, runner, name, message):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "FOPR", "-sn", name])

    assert result.exit_code != 0
    assert message in result.output
