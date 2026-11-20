""" Tests for the opm-vis-pv CLI, backed by the SPE1CASE1 test dataset """
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from click.testing import CliRunner

pv = pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.cli.pvplot_cli import main  # noqa: E402
from opm_vis.pvplot import GridPlotter  # noqa: E402

# The case1_dir, data_dir and offscreen fixtures come from conftest.py.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_single_frame_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_animate_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_animate_range_with_step(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_animate_without_save_plays_instead_of_writing_a_file(case1_dir, runner, monkeypatch):
    # animate(filename=None) opens a real on-screen window (off_screen=False) and blocks until
    # it is closed, so GridPlotter itself is stubbed out rather than actually constructed - this
    # only checks that the CLI passes filename=None, with the right report steps, when --save
    # is not given, instead of an actual path.
    fake_plotter = MagicMock()
    fake_plotter.__enter__.return_value = fake_plotter
    fake_plotter.case.report.report_steps.return_value = list(range(121))
    monkeypatch.setattr(
        "opm_vis.cli.pvplot_cli.GridPlotter", MagicMock(return_value=fake_plotter)
    )

    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--animate", "--rstep", "0:20"]
    )

    assert result.exit_code == 0, result.output
    fake_plotter.animate.assert_called_once()
    args, kwargs = fake_plotter.animate.call_args
    assert args[0] == "SGAS"
    assert args[1] is None
    assert kwargs["rsteps"] == list(range(21))


def test_static_keyword_does_not_need_rstep(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "PORO", "-k", "1", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_dynamic_keyword_without_rstep_or_animate_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1"])

    assert result.exit_code != 0
    assert "changes over time" in result.output


def test_save_with_no_path_generates_a_name(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-sf", "."]
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k1_r60.png").exists()


# ---------------------------------------------------------------------------
# --diff / --diff-rstep / --diff-kind
# ---------------------------------------------------------------------------


def test_diff_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--diff", "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_diff_default_name_reflects_diff_rstep_and_kind(case1_dir, offscreen, runner):
    del offscreen

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
                "relative",
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("PRESSURE-diff0-relative_k1_r60.png").exists()


def test_diff_animate_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_diff_kind_is_rejected_when_not_one_of_the_three(case1_dir, runner):
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
            "--diff",
            "--diff-kind",
            "bogus",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--diff-kind'" in result.output


# ---------------------------------------------------------------------------
# -c/--calculator / --calc-count
# ---------------------------------------------------------------------------


def test_calculator_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "mean", "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_default_name_reflects_calc_kind(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["-f", case1_dir, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "sum", "-sf", "."],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 aggregates layers 1-3 (the grid's last layer)
        assert Path("PRESSURE-sum_k1-3_r60.png").exists()


def test_calculator_default_name_reflects_calc_count(case1_dir, offscreen, runner):
    del offscreen

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


def test_calculator_with_calc_count_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_calculator_combines_with_diff(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_calculator_animate_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_calculator_requires_a_slice(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "--view", "3d", "--rstep", "60", "-c", "mean"]
    )

    assert result.exit_code != 0
    assert "requires exactly one of -i/-j/-k" in result.output


def test_calculator_rejects_more_than_one_slice(case1_dir, runner):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--view",
            "3d",
            "-k",
            "1",
            "-j",
            "3",
            "--rstep",
            "60",
            "-c",
            "mean",
        ],
    )

    assert result.exit_code != 0
    assert "requires exactly one of -i/-j/-k" in result.output


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
# -c surface - SPE1CASE1 has no inactive cells, so these are smoke tests that "surface" is
# wired through the CLI/GridPlotter construction (both the hex and --quads mesh paths) without
# error - not a test of its gap-filling behaviour itself (see test_grid.py and
# test_pvplot_mesh.py, with synthetic inactive-cell data, for that).
# ---------------------------------------------------------------------------


def test_calculator_surface_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_calculator_surface_with_quads_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "-c", "surface", "--quads",
            "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_calculator_surface_default_name_reflects_calc_kind(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["-f", case1_dir, "--keyword", "PRESSURE", "-k", "1", "--rstep", "60", "-c", "surface", "-sf", "."],
        )

        assert result.exit_code == 0, result.output
        # SPE1CASE1 has 3 k-layers: -k 1 scans layers 1-3 (the grid's last layer) for surface
        assert Path("PRESSURE-surface_k1-3_r60.png").exists()


# ---------------------------------------------------------------------------
# --grid-only / --grid-color
# ---------------------------------------------------------------------------


def test_grid_only_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "-k", "1", "--grid-only", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_grid_only_works_with_no_restart_files(data_dir, offscreen, runner, tmp_path):
    # A dry run: only .EGRID/.INIT exist yet, no .UNRST/.X files at all
    del offscreen
    shutil.copy(data_dir / "SPE1CASE1" / "SPE1CASE1.EGRID", tmp_path / "CASE.EGRID")
    shutil.copy(data_dir / "SPE1CASE1" / "SPE1CASE1.INIT", tmp_path / "CASE.INIT")
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", str(tmp_path), "-k", "1", "--grid-only", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_grid_only_plots_the_whole_grid_without_a_slice(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "--grid-only", "--view", "3d", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_grid_only_accepts_a_custom_color(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "-k", "1", "--grid-only", "--grid-color", "tan", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_grid_only_default_output_name_uses_grid_tag(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["-f", case1_dir, "-k", "1", "--grid-only", "-sf", "."])

        assert result.exit_code == 0, result.output
        assert Path("GRID_k1_r0.png").exists()


# ---------------------------------------------------------------------------
# --show-edges
# ---------------------------------------------------------------------------


def test_show_edges_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_show_edges_works_with_grid_only(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "-k", "1", "--grid-only", "--show-edges", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


# ---------------------------------------------------------------------------
# --threshold / --threshold-invert
# ---------------------------------------------------------------------------


def test_threshold_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--threshold",
            "0.1",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_threshold_accepts_a_low_high_range(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--threshold",
            "0.1:0.5",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_threshold_invert_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--threshold",
            "0.1",
            "--threshold-invert",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_threshold_default_output_name_uses_threshold_tag(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
                "--keyword",
                "SGAS",
                "--rstep",
                "60",
                "--view",
                "3d",
                "--threshold",
                "0.1",
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS-threshold_grid_r60.png").exists()


def test_threshold_with_a_slice_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--threshold", "0.1"],
    )

    assert result.exit_code != 0
    assert "--threshold works on the whole grid" in result.output


def test_threshold_with_grid_only_is_rejected(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "--grid-only", "--threshold", "0.1"])

    assert result.exit_code != 0
    assert "--threshold needs --keyword" in result.output


def test_threshold_with_animate_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "--animate", "--threshold", "0.1"]
    )

    assert result.exit_code != 0
    assert "--threshold does not support --animate" in result.output


def test_threshold_rejects_a_non_numeric_value(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d", "--threshold", "abc"],
    )

    assert result.exit_code != 0
    assert "--threshold values must be numbers" in result.output


def test_threshold_rejects_too_many_colon_parts(case1_dir, runner):
    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--threshold",
            "0.1:0.2:0.3",
        ],
    )

    assert result.exit_code != 0
    assert "--threshold must be LOW or LOW:HIGH" in result.output


# ---------------------------------------------------------------------------
# --clip / --clip-origin / --clip-invert / --clip-crinkle
# ---------------------------------------------------------------------------


def test_clip_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--clip",
            "x",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_clip_accepts_origin_invert_and_crinkle(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--clip",
            "x",
            "--clip-origin",
            "500",
            "500",
            "8350",
            "--no-clip-invert",
            "--clip-crinkle",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_clip_works_with_grid_only(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main, ["-f", case1_dir, "--grid-only", "--view", "3d", "--clip", "z", "-sf", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_clip_and_threshold_can_be_combined(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--clip",
            "x",
            "--threshold",
            "0.05",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_clip_works_with_animate(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--animate",
            "--rstep",
            "0:60:20",
            "--view",
            "3d",
            "--clip",
            "x",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_clip_default_output_name_uses_clip_tag(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
                "--keyword",
                "SGAS",
                "--rstep",
                "60",
                "--view",
                "3d",
                "--clip",
                "x",
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS-clip_grid_r60.png").exists()


def test_clip_and_threshold_default_output_name_combines_both_tags(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
                "--keyword",
                "SGAS",
                "--rstep",
                "60",
                "--view",
                "3d",
                "--clip",
                "x",
                "--threshold",
                "0.05",
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS-threshold-clip_grid_r60.png").exists()


def test_clip_with_a_slice_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "60", "--clip", "x"]
    )

    assert result.exit_code != 0
    assert "--clip works on the whole grid" in result.output


def test_clip_rejects_an_invalid_axis(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d", "--clip", "bogus"],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--clip'" in result.output


def test_grid_only_and_keyword_together_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--grid-only"]
    )

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


def test_paths_default_to_the_working_directory(data_dir, offscreen, runner, tmp_path, monkeypatch):
    del offscreen

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, case_dir / source.name)

    monkeypatch.chdir(case_dir)
    result = runner.invoke(main, ["--keyword", "SGAS", "-k", "1", "--rstep", "60", "-s"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "pv-figs" / "SGAS_k1_r60.png").exists()


def test_no_slice_with_default_2d_view_is_rejected(case1_dir, runner):
    # No -i/-j/-k plots the whole grid, which the 2d view (the default) cannot show
    result = runner.invoke(main, ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60"])

    assert result.exit_code != 0
    assert "2d has no whole-grid view" in result.output


def test_no_slice_with_quads_is_rejected(case1_dir, runner):
    # --quads is a slice fast-path; it has no meaning for the whole grid
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d", "--quads"]
    )

    assert result.exit_code != 0
    assert "--quads needs a slice" in result.output


# ---------------------------------------------------------------------------
# Whole grid (no -i/-j/-k)
# ---------------------------------------------------------------------------


def test_no_slice_with_3d_view_plots_the_whole_grid(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d", "-sf", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_no_slice_default_output_name_uses_grid_tag(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d", "-sf", "."],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_grid_r60.png").exists()


def test_no_slice_animates_the_whole_grid(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--animate",
            "--rstep",
            "0:60:20",
            "--view",
            "3d",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_no_slice_draws_every_well_without_needing_all_wells(case1_dir, offscreen, runner, tmp_path):
    # No slices to restrict to, so every well should be drawn even without --all-wells
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "--rstep",
            "60",
            "--view",
            "3d",
            "--wells",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_no_slice_with_glyphs_writes_output_file(tpsa_lagged_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", tpsa_lagged_dir,
            "--keyword",
            "DISPZ",
            "--rstep",
            "15",
            "--view",
            "3d",
            "--glyphs",
            "DISPX",
            "DISPY",
            "DISPZ",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_glyphs_prefix_expands_to_xyz_components(tpsa_lagged_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", tpsa_lagged_dir,
            "--keyword",
            "DISPZ",
            "-k",
            "1",
            "--rstep",
            "15",
            "--glyphs",
            "DISP",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_glyphs_with_two_values_is_rejected(tpsa_lagged_dir, runner):
    result = runner.invoke(
        main,
        ["-f", tpsa_lagged_dir, "--keyword", "DISPZ", "-k", "1", "--rstep", "15", "--glyphs", "DISPX", "DISPY"],
    )

    assert result.exit_code != 0
    assert "one keyword base" in result.output


def test_multiple_slices_with_default_2d_view_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "-i", "1", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "2d only supports one slice" in result.output


def test_duplicate_slice_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "-k", "1", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "Slice given more than once" in result.output


def test_glyph_every_n_writes_output_file(tpsa_lagged_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", tpsa_lagged_dir,
            "--keyword",
            "DISPZ",
            "-k",
            "1",
            "--rstep",
            "15",
            "--glyphs",
            "DISPX",
            "DISPY",
            "DISPZ",
            "--glyph-every-n",
            "2",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_glyph_every_n_rejects_less_than_one(tpsa_lagged_dir, runner):
    result = runner.invoke(
        main,
        [
            "-f", tpsa_lagged_dir,
            "--keyword",
            "DISPZ",
            "-k",
            "1",
            "--rstep",
            "15",
            "--glyphs",
            "DISPX",
            "DISPY",
            "DISPZ",
            "--glyph-every-n",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "not in the range" in result.output


def test_multiple_slices_with_3d_view_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "-j",
            "6",
            "--rstep",
            "60",
            "--view",
            "3d",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())
    assert all(f.stat().st_size > 0 for f in output.iterdir())


def test_default_output_name_joins_multiple_slice_tags(case1_dir, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "-f", case1_dir,
                "--keyword",
                "SGAS",
                "-k",
                "1",
                "-k",
                "3",
                "--rstep",
                "60",
                "--view",
                "3d",
                "-sf", ".",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k1_k3_r60.png").exists()


def test_wells_union_across_multiple_slices(case1_dir, offscreen, runner, tmp_path):
    # SPE1CASE1's INJ is completed at k=0, PROD at k=2 (0-based) - requesting both slices
    # (-k 1 -k 3, 1-based) should draw both wells, not just whichever is checked first
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir,
            "--keyword",
            "SGAS",
            "-k",
            "1",
            "-k",
            "3",
            "--rstep",
            "60",
            "--view",
            "3d",
            "-sf",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_rstep_range_requires_animate(case1_dir, runner):
    result = runner.invoke(
        main, ["-f", case1_dir, "--keyword", "SGAS", "-k", "1", "--rstep", "0:60"]
    )

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


def test_unknown_keyword_is_a_clean_error(case1_dir, offscreen, runner, tmp_path):
    del offscreen

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


def test_fault_draws_the_fault_surface(case1_dir, fault_file, offscreen, runner, tmp_path):
    del offscreen
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


def test_fault_name_restricts_to_the_given_fault(case1_dir, fault_file, offscreen, runner, tmp_path):
    del offscreen
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


def test_fault_with_no_slice_draws_every_fault(case1_dir, fault_file, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "--keyword", "SGAS", "--rstep", "60", "--view", "3d",
            "--fault", fault_file, "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


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
        ["-K", "DEPTH", "--view", "3d"],
        ["-K", "PERMX", "-k", "1", "-c", "mean"],
        ["-K", "PERMX", "--threshold", "100", "--view", "3d"],
    ],
)
def test_init_keyword_plots_with_no_restart_files(dry_run_dir, offscreen, runner, extra):
    del offscreen
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


def test_save_defaults_to_pv_folders_inside_the_case_folder(data_dir, offscreen, runner, tmp_path):
    del offscreen
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, tmp_path / source.name)
    args = ["-f", str(tmp_path), "-K", "SGAS", "-k", "1"]

    image = runner.invoke(main, [*args, "-r", "60", "-s"])
    animation = runner.invoke(main, [*args, "-r", "0:2", "--animate", "-s"])

    assert image.exit_code == 0, image.output
    assert animation.exit_code == 0, animation.output
    assert f"Created folder {tmp_path / 'pv-figs'}" in image.output
    assert f"Created folder {tmp_path / 'pv-gifs'}" in animation.output
    assert (tmp_path / "pv-figs" / "SGAS_k1_r60.png").exists()
    assert (tmp_path / "pv-gifs" / "SGAS_k1_r0-2.gif").exists()


@pytest.mark.parametrize("view", [["-k", "1"], ["-k", "1", "--view", "3d"]])
def test_polygons_are_drawn(case1_dir, polygon_files, offscreen, runner, tmp_path, view):
    del offscreen
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
    case1_dir, polygon_files, offscreen, runner, tmp_path
):
    del offscreen
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


def test_unreadable_polygon_file_is_a_clean_error(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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
    case1_dir, polygon_files, offscreen, runner, tmp_path, label_args
):
    del offscreen
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


def test_polygon_outside_the_grid_is_warned_about(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_font_scale_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--font-scale", "1.5", "-sf", str(output)])

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


def test_font_scale_must_be_positive(case1_dir, runner):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--font-scale", "0"])

    assert result.exit_code != 0
    assert "--font-scale" in result.output


# ---------------------------------------------------------------------------
# --camera
# ---------------------------------------------------------------------------


def test_camera_writes_output_file(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "out"

    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--view", "3d",
            "--camera", "-20000,-20000,30000/5000,5000,-41750/0,0,1", "-sf", str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert any(output.iterdir())


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--camera", "1,2,3/4,5,6"], "--camera: A camera is"),
        (["--camera", "1,2,3/4,5,6/0,0,1", "--azimuth", "10"], "drop --azimuth"),
    ],
)
def test_camera_misuse_is_rejected(case1_dir, runner, extra, message):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", *extra])

    assert result.exit_code != 0
    assert message in result.output


def test_interactive_window_prints_the_view_on_closing(case1_dir, runner, monkeypatch):
    # GridPlotter is stubbed out, as in test_animate_without_save_plays_instead_of_writing_a_file,
    # since a real interactive window would block until closed
    from opm_vis.pvplot.camera import Camera, ShownView  # pylint: disable=import-outside-toplevel

    fake_plotter = MagicMock()
    fake_plotter.__enter__.return_value = fake_plotter
    fake_plotter.case.report.report_steps.return_value = list(range(121))
    camera = Camera((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (0.0, 0.0, 1.0), 7.0)
    fake_plotter.show.return_value = ShownView(camera, (800, 600))
    monkeypatch.setattr(
        "opm_vis.cli.pvplot_cli.GridPlotter", MagicMock(return_value=fake_plotter)
    )

    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--camera", camera.to_text()],
    )

    assert result.exit_code == 0, result.output
    fake_plotter.set_camera.assert_called_once_with(camera)
    fake_plotter.show.assert_called_once_with(camera_overlay=True)
    assert "View: --camera 1,2,3/4,5,6/0,0,1/7 --window-size 800 600" in result.output


# ---------------------------------------------------------------------------
# --save-name
# ---------------------------------------------------------------------------


def test_save_name_replaces_the_generated_name(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "my plot", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["my plot.png"]


def test_save_name_already_ending_in_the_suffix_keeps_it_once(case1_dir, offscreen, runner, tmp_path):
    del offscreen
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "plot.png", "-sf", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert [f.name for f in tmp_path.iterdir()] == ["plot.png"]


def test_save_name_implies_save(data_dir, offscreen, runner, tmp_path):
    del offscreen
    # A writable copy of the case, since the default save folder goes inside -f/--folder
    for source in (data_dir / "SPE1CASE1").glob("SPE1CASE1.*"):
        shutil.copy(source, tmp_path / source.name)

    result = runner.invoke(main, ["-f", str(tmp_path), "-K", "SGAS", "-k", "1", "-r", "60", "-sn", "plot"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "pv-figs" / "plot.png").exists()


@pytest.mark.parametrize(("name", "message"), [("out/plot", "without a folder"), ("", "empty")])
def test_save_name_must_be_a_plain_file_name(case1_dir, runner, name, message):
    result = runner.invoke(main, ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "-sn", name])

    assert result.exit_code != 0
    assert message in result.output


# ---------------------------------------------------------------------------
# --colorbar-label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [["-r", "60"], ["-r", "0:2", "--animate"]])
def test_colorbar_label_with_math_writes_output_file(case1_dir, offscreen, runner, tmp_path, extra):
    del offscreen
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
    case1_dir, polygon_files, offscreen, runner, tmp_path, monkeypatch, args, expected
):
    del offscreen
    # Spy on the method, so the backend's own default width is untouched when the option is not
    # given, rather than the CLI imposing one
    seen = {}
    original = GridPlotter.add_polygons

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(GridPlotter, "add_polygons", spy)
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "PERMX", "-k", "1", "--polygon", polygon_files["line"],
            *args, "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen.get("line_width") == expected


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
    case1_dir, fault_file, offscreen, runner, tmp_path, monkeypatch, args, expected
):
    del offscreen
    seen = {}
    original = GridPlotter.add_faults

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(GridPlotter, "add_faults", spy)
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
# --well-name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [([], None), (["--well-name", "INJ"], ["INJ"]), (["--well-name", "INJ", "--well-name", "PROD"], ["INJ", "PROD"])],
)
def test_well_name_is_passed_on_only_when_given(
    case1_dir, offscreen, runner, tmp_path, monkeypatch, args, expected
):
    del offscreen
    seen = {}
    original = GridPlotter.add_wells

    def spy(self, *spy_args, **spy_kwargs):
        seen.update(spy_kwargs)
        return original(self, *spy_args, **spy_kwargs)

    monkeypatch.setattr(GridPlotter, "add_wells", spy)
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", *args, "-sf", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert seen.get("names") == expected


def test_unknown_well_name_is_a_clean_error(case1_dir, offscreen, runner, tmp_path):
    del offscreen
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


def test_well_name_with_no_wells_is_rejected(case1_dir, runner):
    result = runner.invoke(
        main,
        ["-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--no-wells", "--well-name", "INJ"],
    )

    assert result.exit_code != 0
    assert "--well-name has no wells to select with --no-wells" in result.output


def test_well_name_with_all_wells_draws_the_named_well_off_the_slice(
    case1_dir, offscreen, runner, tmp_path
):
    del offscreen
    result = runner.invoke(
        main,
        [
            "-f", case1_dir, "-K", "SGAS", "-k", "1", "-r", "60", "--all-wells",
            "--well-name", "PROD", "-sf", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
