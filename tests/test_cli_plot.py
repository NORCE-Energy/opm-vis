""" Tests for the opm-vis-mpl CLI, backed by the SPE1CASE1 test dataset """
import shutil
from pathlib import Path

import matplotlib
import pytest
from click.testing import CliRunner

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from opm_vis.cli.plot_cli import main  # noqa: E402

# The case1 and data_dir fixtures come from conftest.py.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_single_frame_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-s", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_animate_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:20",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_animate_range_with_step(case1, runner, tmp_path):
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:10",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_static_keyword_does_not_need_rstep(case1, runner, tmp_path):
    output = tmp_path / "poro.png"

    result = runner.invoke(main, [case1, "--keyword", "PORO", "-k", "1", "-s", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_dynamic_keyword_without_rstep_or_animate_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "-k", "1"])

    assert result.exit_code != 0
    assert "changes over time" in result.output


def test_save_with_no_path_generates_a_name(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--save"]
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k1_r60.png").exists()


# ---------------------------------------------------------------------------
# --diff / --diff-rstep / --diff-kind
# ---------------------------------------------------------------------------


def test_diff_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--diff", "-s", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_diff_default_name_reflects_diff_rstep_and_kind(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                case1,
                "--keyword",
                "PRESSURE",
                "-k",
                "1",
                "--rstep",
                "60",
                "--diff",
                "--diff-rstep",
                "0",
                "--diff-kind",
                "absolute",
                "--save",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("PRESSURE-diff0-absolute_k1_r60.png").exists()


def test_diff_animate_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "--diff",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


# ---------------------------------------------------------------------------
# -c/--calculator / --calc-count
# ---------------------------------------------------------------------------


def test_calculator_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "mean", "-s", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_default_name_reflects_calc_kind(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [case1, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "sum", "--save"],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 aggregates layers 1-3 (the grid's last layer)
        assert Path("PRESSURE-sum_k1-3_r60.png").exists()


def test_calculator_default_name_reflects_calc_count(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                case1,
                "--keyword",
                "PRESSURE",
                "-k",
                "1",
                "--rstep",
                "60",
                "-c",
                "sum",
                "--calc-count",
                "1",
                "--save",
            ],
        )

        assert result.exit_code == 0, result.output
        # -k 1 is always included; --calc-count 1 adds just the next layer (k2)
        assert Path("PRESSURE-sum_k1-2_r60.png").exists()


def test_calculator_with_calc_count_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--rstep",
            "60",
            "-c",
            "mean",
            "--calc-count",
            "2",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_combines_with_diff(case1, runner, tmp_path):
    output = tmp_path / "pressure.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "PRESSURE",
            "-k",
            "1",
            "--rstep",
            "60",
            "-c",
            "mean",
            "--diff",
            "--diff-rstep",
            "0",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_animate_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "-c",
            "mean",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_surface_writes_output_file(case1, runner, tmp_path):
    # SPE1CASE1 has no inactive cells, so this is a smoke test that -c surface is wired
    # through the CLI/SlicePoly construction without error - not a test of its gap-filling
    # behaviour itself (see test_grid.py, with synthetic inactive-cell data, for that).
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [
            case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "surface", "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_surface_default_name_reflects_calc_kind(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [case1, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "surface", "--save"],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 scans layers 1-3 (the grid's last layer) for surface
        assert Path("PRESSURE-surface_k1-3_r60.png").exists()


def test_calculator_surface_combines_with_diff(case1, runner, tmp_path):
    output = tmp_path / "pressure.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "PRESSURE",
            "-k",
            "1",
            "--rstep",
            "60",
            "-c",
            "surface",
            "--diff",
            "--diff-rstep",
            "0",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calculator_surface_animate_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "-c",
            "surface",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_calc_count_without_calculator_is_rejected(case1, runner):
    result = runner.invoke(
        main,
        [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--calc-count", "2"],
    )

    assert result.exit_code != 0
    assert "only valid together with --calculator" in result.output


def test_calc_count_must_be_positive(case1, runner):
    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--rstep",
            "60",
            "-c",
            "mean",
            "--calc-count",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "must be a positive integer" in result.output


def test_calculator_is_rejected_with_grid_only(case1, runner):
    result = runner.invoke(main, [case1, "-k", "1", "--grid-only", "-c", "mean"])

    assert result.exit_code != 0
    assert "has no effect with --grid-only" in result.output


def test_calculator_kind_is_rejected_when_unknown(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "bogus"]
    )

    assert result.exit_code != 0
    assert "Invalid value for" in result.output


# ---------------------------------------------------------------------------
# --grid-only / --grid-color
# ---------------------------------------------------------------------------


def test_grid_only_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "grid.png"

    result = runner.invoke(main, [case1, "-k", "1", "--grid-only", "-s", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_grid_only_accepts_a_custom_color(case1, runner, tmp_path):
    output = tmp_path / "grid.png"

    result = runner.invoke(
        main, [case1, "-k", "1", "--grid-only", "--grid-color", "tan", "-s", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert output.exists()


def test_grid_only_requires_a_slice(case1, runner):
    result = runner.invoke(main, [case1, "--grid-only"])

    assert result.exit_code != 0
    assert "at least one of -i, -j, or -k" in result.output


def test_grid_only_default_output_name_uses_grid_tag(case1, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, [case1, "-k", "1", "--grid-only", "--save"])

        assert result.exit_code == 0, result.output
        assert Path("GRID_k1_all.png").exists()


# ---------------------------------------------------------------------------
# --show-edges
# ---------------------------------------------------------------------------


def test_show_edges_writes_output_file(case1, runner, tmp_path):
    output = tmp_path / "edges.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--rstep",
            "60",
            "--show-edges",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_show_edges_works_with_grid_only(case1, runner, tmp_path):
    output = tmp_path / "edges.png"

    result = runner.invoke(
        main, [case1, "-k", "1", "--grid-only", "--show-edges", "-s", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert output.exists()


def test_grid_only_and_keyword_together_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "-k", "1", "--grid-only"])

    assert result.exit_code != 0
    assert "--keyword is not allowed together with --grid-only" in result.output


def test_neither_keyword_nor_grid_only_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "-k", "1"])

    assert result.exit_code != 0
    assert "Pass --keyword, or --grid-only" in result.output


def test_grid_only_with_animate_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "-k", "1", "--grid-only", "--animate"])

    assert result.exit_code != 0
    assert "--grid-only does not support --animate" in result.output


def test_paths_default_to_the_working_directory(data_dir, runner, tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for source in data_dir.glob("SPE1CASE1.*"):
        shutil.copy(source, case_dir / source.name)

    monkeypatch.chdir(case_dir)
    result = runner.invoke(main, ["--keyword", "SGAS", "-k", "1", "--rstep", "60", "-s"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "SGAS_k1_r60.png").exists()


def test_at_least_one_slice_dimension_is_required(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "--rstep", "60"])

    assert result.exit_code != 0
    assert "at least one of -i, -j, or -k" in result.output


def test_more_than_one_slice_dimension_is_rejected(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "1", "-i", "1", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "only supports one slice" in result.output


def test_rstep_range_requires_animate(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "-k", "1", "--rstep", "0:60"])

    assert result.exit_code != 0
    assert "only valid with --animate" in result.output


def test_animate_requires_a_range_not_a_single_step(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "1", "--animate", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "START:END" in result.output


def test_bare_invocation_shows_help(runner):
    result = runner.invoke(main, [])

    assert "Usage:" in result.output


def test_help_flag_short_form(runner):
    result = runner.invoke(main, ["-h"])

    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_unknown_keyword_is_a_clean_error(case1, runner, tmp_path):
    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "NOPE",
            "-k",
            "1",
            "--rstep",
            "60",
            "-s",
            str(tmp_path / "x.png"),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
