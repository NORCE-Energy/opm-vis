""" Tests for the opm-vis-mpl CLI, backed by the SPE1CASE1 test dataset """
import shutil
from pathlib import Path

import matplotlib
import numpy as np
import pytest
from click.testing import CliRunner

matplotlib.use("Agg")  # headless: never try to open a GUI window while saving

from matplotlib.image import imread  # noqa: E402

from opm_vis.cli.plot_cli import main  # noqa: E402
from opm_vis.plot.collections import _SlicePolyCollection  # noqa: E402

# The case1_dir and data_dir fixtures come from conftest.py.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_single_frame_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_figsize_sets_the_saved_image_size(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--figsize", "10", "3",
         "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    # Saved with bbox_inches="tight", so the image is cropped to its content rather than
    # exactly 10x3 inches at 100 dpi - but it keeps the figure's wide proportions
    height, width = imread(output / "SGAS_k1_r60.png").shape[:2]
    assert width > 2 * height


def test_figsize_must_be_positive(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--figsize", "0", "3"]
    )

    assert result.exit_code != 0
    assert "must both be positive" in result.output


def test_animate_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:20",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_animate_range_with_step(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:10",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_static_keyword_does_not_need_rstep(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "PORO", "-k", "1", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_dynamic_keyword_without_rstep_or_animate_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1"])

    assert result.exit_code != 0
    assert "changes over time" in result.output


def test_save_with_no_path_generates_a_name(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-sf", "."]
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k1_r60.png").exists()


# ---------------------------------------------------------------------------
# --diff / --diff-rstep / --diff-kind
# ---------------------------------------------------------------------------


def test_diff_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--diff", "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_diff_default_name_reflects_diff_rstep_and_kind(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
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
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("PRESSURE-diff0-absolute_k1_r60.png").exists()


def test_diff_animate_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "--diff",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


# ---------------------------------------------------------------------------
# -c/--calculator / --calc-count
# ---------------------------------------------------------------------------


def test_calculator_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "mean", "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_default_name_reflects_calc_kind(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["-f", case1_dir, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "sum", "-sf", "."],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 aggregates layers 1-3 (the grid's last layer)
        assert Path("PRESSURE-sum_k1-3_r60.png").exists()


def test_calculator_default_name_reflects_calc_count(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
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
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        # -k 1 is always included; --calc-count 1 adds just the next layer (k2)
        assert Path("PRESSURE-sum_k1-2_r60.png").exists()


def test_calculator_with_calc_count_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
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
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_combines_with_diff(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
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
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_animate_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "-c",
            "mean",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_surface_writes_output_file(case1_dir, runner, tmp_path):
    # SPE1CASE1 has no inactive cells, so this is a smoke test that -c surface is wired
    # through the CLI/SlicePoly construction without error - not a test of its gap-filling
    # behaviour itself (see test_grid.py, with synthetic inactive-cell data, for that).
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "surface", "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_surface_default_name_reflects_calc_kind(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["-f", case1_dir, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "surface", "-sf", "."],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 scans layers 1-3 (the grid's last layer) for surface
        assert Path("PRESSURE-surface_k1-3_r60.png").exists()


def test_calculator_surface_combines_with_diff(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
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
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_surface_animate_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--animate",
            "--rstep",
            "0:60:20",
            "-c",
            "surface",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calc_count_without_calculator_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--calc-count", "2"],
    )

    assert result.exit_code != 0
    assert "only valid together with --calculator" in result.output


def test_calc_count_must_be_positive(case1_dir, runner):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
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


def test_calculator_is_rejected_with_grid_only(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-k", "1", "--grid-only", "-c", "mean"])

    assert result.exit_code != 0
    assert "has no effect with --grid-only" in result.output


def test_calculator_kind_is_rejected_when_unknown(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "bogus"]
    )

    assert result.exit_code != 0
    assert "Invalid value for" in result.output


# ---------------------------------------------------------------------------
# --grid-only / --grid-color
# ---------------------------------------------------------------------------


def test_grid_only_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "-k", "1", "--grid-only", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_grid_only_accepts_a_custom_color(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "-k", "1", "--grid-only", "--grid-color", "tan", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_grid_only_works_with_no_restart_files(data_dir, runner, tmp_path):
    # A dry run: only .EGRID/.INIT exist yet, no .UNRST/.X files at all
    (tmp_path / "CASE.EGRID").write_bytes((data_dir / "SPE1CASE1" / "SPE1CASE1.EGRID").read_bytes())
    (tmp_path / "CASE.INIT").write_bytes((data_dir / "SPE1CASE1" / "SPE1CASE1.INIT").read_bytes())
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", str(tmp_path), "-k", "1", "--grid-only", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_grid_only_requires_a_slice(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--grid-only"])

    assert result.exit_code != 0
    assert "at least one of -i, -j, or -k" in result.output


def test_grid_only_default_output_name_uses_grid_tag(case1_dir, runner):
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-k", "1", "--grid-only", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("GRID_k1_all.png").exists()


# ---------------------------------------------------------------------------
# --show-edges
# ---------------------------------------------------------------------------


def test_show_edges_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "--rstep",
            "60",
            "--show-edges",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_show_edges_works_with_grid_only(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "-k", "1", "--grid-only", "--show-edges", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_grid_only_and_keyword_together_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--grid-only"])

    assert result.exit_code != 0
    assert "--keyword is not allowed together with --grid-only" in result.output


def test_neither_keyword_nor_grid_only_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-k", "1"])

    assert result.exit_code != 0
    assert "Pass --keyword, or --grid-only" in result.output


def test_grid_only_with_animate_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-k", "1", "--grid-only", "--animate"])

    assert result.exit_code != 0
    assert "--grid-only does not support --animate" in result.output


def test_paths_default_to_the_working_directory(data_dir, runner, tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, case_dir / source.name)

    monkeypatch.chdir(case_dir)
    result = runner.invoke(main, ["--keyword", "SGAS", "-k", "1", "--rstep", "60", "-s"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "mpl-figs" / "SGAS_k1_r60.png").exists()


def test_at_least_one_slice_dimension_is_required(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60"])

    assert result.exit_code != 0
    assert "at least one of -i, -j, or -k" in result.output


def test_more_than_one_slice_dimension_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "-i", "1", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "only supports one slice" in result.output


def test_rstep_range_requires_animate(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "0:60"])

    assert result.exit_code != 0
    assert "only valid with --animate" in result.output


def test_animate_requires_a_range_not_a_single_step(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--animate", "--rstep", "60"]
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


def test_unknown_keyword_is_a_clean_error(case1_dir, runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "NOPE",
            "-k",
            "1",
            "--rstep",
            "60",
            "-sf",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# --fault / --fault-name
# ---------------------------------------------------------------------------


@pytest.fixture
def fault_file(tmp_path):
    """FAULT1 at i=4 (0-based) spanning every j/k in SPE1CASE1's 10x10x3 grid."""
    path = tmp_path / "FAULTS.DATA"
    path.write_text(
        """
FAULTS
  'FAULT1'  5 5 1 10 1 3 'I' /
/
"""
    )
    return str(path)


def test_fault_draws_the_fault_trace(case1_dir, fault_file, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60",
            "--fault", fault_file, "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_fault_works_with_3d_view(case1_dir, fault_file, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--view", "3d",
            "--fault", fault_file, "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_fault_works_with_grid_only(case1_dir, fault_file, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--grid-only", "-k", "1",
            "--fault", fault_file, "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_fault_name_restricts_to_the_given_fault(case1_dir, fault_file, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60",
            "--fault", fault_file, "--fault-name", "FAULT1", "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_fault_name_unknown_fault_is_a_clean_error(case1_dir, fault_file, runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60",
            "--fault", fault_file, "--fault-name", "NOPE", "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_fault_name_without_fault_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--fault-name", "FAULT1"],
    )

    assert result.exit_code != 0
    assert "--fault-name needs --fault" in result.output


def test_fault_missing_file_is_a_clean_error(case1_dir, runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60",
            "--fault", str(tmp_path / "NOPE.DATA"), "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output


@pytest.fixture
def dry_run_dir(data_dir, tmp_path):
    # A dry run: only .EGRID/.INIT exist yet, no .UNRST/.X files at all
    shutil.copy(data_dir / "SPE1CASE1" / "SPE1CASE1.EGRID", tmp_path / "CASE.EGRID")
    shutil.copy(data_dir / "SPE1CASE1" / "SPE1CASE1.INIT", tmp_path / "CASE.INIT")
    return tmp_path


@pytest.mark.parametrize(
    "extra",
    [
        ["-K", "PERMX", "-k", "1"],
        ["-K", "DEPTH", "-k", "1", "--view", "3d"],
        ["-K", "PERMX", "-k", "1", "-c", "mean"],
    ],
)
def test_init_keyword_plots_with_no_restart_files(dry_run_dir, runner, extra):
    output = dry_run_dir / "out"

    with pytest.warns(UserWarning, match="No .UNRST or .X files"):
        result = runner.invoke(main, ["-f", str(dry_run_dir), *extra, "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_restart_keyword_with_no_restart_files_is_a_clean_error(dry_run_dir, runner):
    with pytest.warns(UserWarning, match="No .UNRST or .X files"):
        result = runner.invoke(main, ["-f", str(dry_run_dir), "-K", "SGAS", "-k", "1"])

    assert result.exit_code != 0
    assert "SGAS is not in the .INIT file" in result.output
    assert "Traceback" not in result.output


def test_diff_with_no_restart_files_is_a_clean_error(dry_run_dir, runner):
    with pytest.warns(UserWarning, match="No .UNRST or .X files"):
        result = runner.invoke(main, ["-f", str(dry_run_dir), "-K", "PERMX", "-k", "1", "-d"])

    assert result.exit_code != 0
    assert "--diff needs restart data" in result.output


def test_save_defaults_to_mpl_folders_inside_the_case_folder(data_dir, runner, tmp_path):
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, tmp_path / source.name)
    args = ["-f", str(tmp_path), "-K", "SGAS", "-k", "1"]

    image = runner.invoke(main, [*args, "-r", "60", "-s"])
    animation = runner.invoke(main, [*args, "-r", "0:2", "--animate", "-s"])

    assert image.exit_code == 0, image.output
    assert animation.exit_code == 0, animation.output
    assert f"Created folder {tmp_path / 'mpl-figs'}" in image.output
    assert f"Created folder {tmp_path / 'mpl-gifs'}" in animation.output
    assert (tmp_path / "mpl-figs" / "SGAS_k1_r60.png").exists()
    assert (tmp_path / "mpl-gifs" / "SGAS_k1_r0-2.gif").exists()


@pytest.mark.parametrize("view", [["-k", "1"], ["-k", "1", "--view", "3d"]])
def test_polygons_are_drawn(case1_dir, polygon_files, runner, tmp_path, view):
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "PERMX", *view,
            "--polygon", polygon_files["outline"], "--polygon", polygon_files["line"],
            "--polygon-color", "white", "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_polygon_outlines_on_an_i_slice_are_skipped_with_a_warning(
    case1_dir, polygon_files, runner, tmp_path
):
    with pytest.warns(UserWarning, match="x,y-only polygon"):
        result = runner.invoke(
            main,
            [
                "-f", case1_dir, "-K", "PERMX", "-i", "5",
                "--polygon", polygon_files["outline"], "-sf", str(tmp_path / "out"),
            ],
        )

    assert result.exit_code == 0, result.output


def test_missing_polygon_file_is_a_clean_error(case1_dir, runner, tmp_path):
    result = runner.invoke(
        main, ["-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", str(tmp_path / "x.npy")]
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_unreadable_polygon_file_is_a_clean_error(case1_dir, runner, tmp_path):
    bad = tmp_path / "bad.npy"
    bad.write_bytes(b"not numpy")
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", str(bad), "-sf", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    "label_args", [["--polygon-label", "Licence", "--polygon-label", ""], ["--no-polygon-labels"]]
)
def test_polygon_labels_can_be_replaced_or_turned_off(
    case1_dir, polygon_files, runner, tmp_path, label_args
):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "PERMX", "-k", "1",
            "--polygon", polygon_files["outline"], "--polygon", polygon_files["line"],
            *label_args, "-sf", str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--polygon-label", "a"], "--polygon-label needs --polygon"),
        (["--polygon", "OUTLINE", "--polygon-label", "a", "--polygon-label", "b"],
         "one label per file"),
    ],
)
def test_polygon_label_misuse_is_rejected(case1_dir, polygon_files, runner, args, message):
    args = [polygon_files["outline"] if arg == "OUTLINE" else arg for arg in args]
    result = runner.invoke(main, ["-f", case1_dir, "-K", "PERMX", "-k", "1", *args])

    assert result.exit_code != 0
    assert message in result.output


def test_polygon_outside_the_grid_is_warned_about(case1_dir, runner, tmp_path):
    path = tmp_path / "km.npy"
    # Far outside SPE1CASE1, which spans 0-10000 ft
    np.save(path, np.array([[1.0, 1.0], [9.0, 1.0], [9.0, 9.0]]) + 100000)

    with pytest.warns(UserWarning, match="entirely outside the plotted grid"):
        result = runner.invoke(
            main,
            ["-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", str(path),
             "-sf", str(tmp_path / "out")],
        )

    assert result.exit_code == 0, result.output


def test_font_scale_writes_output_file(case1_dir, runner, tmp_path):
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--font-scale", "1.5", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_font_scale_must_be_positive(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--font-scale", "0"])

    assert result.exit_code != 0
    assert "--font-scale" in result.output


def test_font_scale_does_not_leak_into_later_plots(case1_dir, runner, tmp_path):
    before = matplotlib.rcParams["font.size"]

    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--font-scale", "2", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert matplotlib.rcParams["font.size"] == before


# ---------------------------------------------------------------------------
# --save-name
# ---------------------------------------------------------------------------


def test_save_name_replaces_the_generated_name(case1_dir, runner, tmp_path):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "my plot", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["my plot.png"]


def test_save_name_already_ending_in_the_suffix_keeps_it_once(case1_dir, runner, tmp_path):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "plot.png", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["plot.png"]


def test_save_name_implies_save(data_dir, runner, tmp_path):
    # A writable copy of the case, since the default save folder goes inside -f/--folder
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, tmp_path / source.name)

    result = runner.invoke(main, ["-f", str(tmp_path), "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "plot"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "mpl-figs" / "plot.png").exists()


@pytest.mark.parametrize(("name", "message"), [("out/plot", "without a folder"), ("", "empty")])
def test_save_name_must_be_a_plain_file_name(case1_dir, runner, name, message):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", name])

    assert result.exit_code != 0
    assert message in result.output


# ---------------------------------------------------------------------------
# --colorbar-label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [["-r", "60"], ["-r", "0:2", "--animate"]])
def test_colorbar_label_with_math_writes_output_file(case1_dir, runner, tmp_path, extra):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", *extra, "-clabel", r"$S_g$ [-]",
         "-sf", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert any(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["-K", "SGAS", "-r", "60", "--no-colorbar"], "with --no-colorbar"),
        (["--grid-only"], "with --grid-only"),
        (["-K", "SGAS", "-r", "60", "-clabel", r"$\frac{1$"], "invalid math"),
    ],
)
def test_colorbar_label_misuse_is_rejected(case1_dir, runner, extra, message):
    if "-clabel" not in extra:
        extra = [*extra, "-clabel", "label"]
    result = runner.invoke(main, ["-f", case1_dir, "-k", "1", *extra])

    assert result.exit_code != 0
    assert message in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(("args", "expected"), [([], None), (["--polygon-linewidth", "6"], 6.0)])
def test_polygon_linewidth_is_passed_on_only_when_given(
    case1_dir, polygon_files, runner, tmp_path, monkeypatch, args, expected
):
    # Spy on the method, so the backend's own default width is untouched when the option is not
    # given, rather than the CLI imposing one
    seen = {}
    original = _SlicePolyCollection.plot_polygons

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(_SlicePolyCollection, "plot_polygons", spy)
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", polygon_files["line"],
            *args, "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen.get("linewidth") == expected


@pytest.mark.parametrize("width", ["0", "-2"])
def test_polygon_linewidth_must_be_positive(case1_dir, polygon_files, runner, width):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", polygon_files["line"],
            "--polygon-linewidth", width,
        ],
    )

    assert result.exit_code != 0
    assert "--polygon-linewidth" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [([], True), (["--fault-labels"], True), (["--no-fault-labels"], False)],
)
def test_fault_labels_can_be_turned_off(
    case1_dir, fault_file, runner, tmp_path, monkeypatch, args, expected
):
    seen = {}
    original = _SlicePolyCollection.plot_faults

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(_SlicePolyCollection, "plot_faults", spy)
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--fault", fault_file,
            *args, "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen["labels"] is expected


# ---------------------------------------------------------------------------
# --no-title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [["-r", "60"], ["-r", "0:2", "--animate"]])
def test_no_title_writes_output_file(case1_dir, runner, tmp_path, extra):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", *extra, "--no-title", "-sf", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert any(tmp_path.iterdir())


def test_no_title_leaves_the_title_out_of_the_saved_image(case1_dir, runner, tmp_path):
    titled = tmp_path / "titled"
    untitled = tmp_path / "untitled"
    args = ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "img"]
    runner.invoke(main, [*args, "-sf", str(titled)])
    result = runner.invoke(main, [*args, "--no-title", "-sf", str(untitled)])

    assert result.exit_code == 0, result.output
    # Saved with bbox_inches="tight", so a figure without a title is cropped shorter
    assert imread(untitled / "img.png").shape[0] < imread(titled / "img.png").shape[0]


# ---------------------------------------------------------------------------
# --well-name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [([], None), (["--well-name", "INJ"], ["INJ"]), (["--well-name", "INJ", "--well-name", "PROD"], ["INJ", "PROD"])],
)
def test_well_name_is_passed_on_only_when_given(
    case1_dir, runner, tmp_path, monkeypatch, args, expected
):
    seen = {}
    original = _SlicePolyCollection.plot

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(_SlicePolyCollection, "plot", spy)
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", *args, "-sf", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert seen.get("well_names") == expected


def test_unknown_well_name_is_a_clean_error(case1_dir, runner, tmp_path):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--well-name", "NOPE",
            "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Unknown well name(s): NOPE. Wells in the case: INJ, PROD." in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# --log-scale
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [[], ["-r", "0:2", "--animate"]])
def test_log_scale_writes_output_file(case1_dir, runner, tmp_path, extra):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "PERMX", "-i", "5", *extra, "--log-scale", "-sf", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert any(tmp_path.iterdir())


def test_log_scale_with_only_zeros_is_a_clean_error(case1_dir, runner, tmp_path):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "0", "--log-scale", "-sf", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "--log-scale needs positive values" in result.output
    assert "Traceback" not in result.output
