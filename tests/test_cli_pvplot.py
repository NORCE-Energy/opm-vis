""" Tests for the opm-vis-pv CLI, backed by the SPE1CASE1 test dataset """
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

pv = pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.cli.pvplot_cli import main  # noqa: E402

# The case1, data_dir and offscreen fixtures come from conftest.py.


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_single_frame_writes_output_file(case1, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "0", "--rstep", "60", "-s", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_gif_writes_output_file(case1, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [case1, "--keyword", "SGAS", "-k", "0", "--gif", "--rstep", "0:20", "-s", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_gif_range_with_step(case1, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "sgas.gif"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "0",
            "--gif",
            "--rstep",
            "0:60:10",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_gif_without_save_plays_instead_of_writing_a_file(case1, runner, monkeypatch):
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
        main, [case1, "--keyword", "SGAS", "-k", "0", "--gif", "--rstep", "0:20"]
    )

    assert result.exit_code == 0, result.output
    fake_plotter.animate.assert_called_once()
    args, kwargs = fake_plotter.animate.call_args
    assert args[0] == "SGAS"
    assert args[1] is None
    assert kwargs["rsteps"] == list(range(21))


def test_static_keyword_does_not_need_rstep(case1, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "poro.png"

    result = runner.invoke(main, [case1, "--keyword", "PORO", "-k", "0", "-s", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_dynamic_keyword_without_rstep_or_gif_is_rejected(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "-k", "0"])

    assert result.exit_code != 0
    assert "changes over time" in result.output


def test_save_with_no_path_generates_a_name(case1, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main, [case1, "--keyword", "SGAS", "-k", "0", "--rstep", "60", "--save"]
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k0_60.png").exists()


def test_paths_default_to_the_working_directory(data_dir, offscreen, runner, tmp_path, monkeypatch):
    del offscreen

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    for source in data_dir.glob("SPE1CASE1.*"):
        shutil.copy(source, case_dir / source.name)

    monkeypatch.chdir(case_dir)
    result = runner.invoke(main, ["--keyword", "SGAS", "-k", "0", "--rstep", "60", "-s"])

    assert result.exit_code == 0, result.output
    assert (case_dir / "SGAS_k0_60.png").exists()


def test_at_least_one_slice_dimension_is_required(case1, runner):
    result = runner.invoke(main, [case1, "--keyword", "SGAS", "--rstep", "60"])

    assert result.exit_code != 0
    assert "at least one of -i, -j, or -k" in result.output


def test_multiple_slices_with_default_2d_view_is_rejected(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "0", "-i", "0", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "2d only supports one slice" in result.output


def test_duplicate_slice_is_rejected(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "0", "-k", "0", "--rstep", "60"]
    )

    assert result.exit_code != 0
    assert "Slice given more than once" in result.output


def test_multiple_slices_with_3d_view_writes_output_file(case1, offscreen, runner, tmp_path):
    del offscreen
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "0",
            "-j",
            "5",
            "--rstep",
            "60",
            "--view",
            "3d",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.stat().st_size > 0


def test_default_output_name_joins_multiple_slice_tags(case1, offscreen, runner):
    del offscreen

    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                case1,
                "--keyword",
                "SGAS",
                "-k",
                "0",
                "-k",
                "2",
                "--rstep",
                "60",
                "--view",
                "3d",
                "-s",
            ],
        )

        assert result.exit_code == 0, result.output
        assert Path("SGAS_k0_k2_60.png").exists()


def test_wells_union_across_multiple_slices(case1, offscreen, runner, tmp_path):
    # SPE1CASE1's INJ is completed at k=0, PROD at k=2 - requesting both slices should draw
    # both wells, not just whichever slice happens to be checked first
    del offscreen
    output = tmp_path / "sgas.png"

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "SGAS",
            "-k",
            "0",
            "-k",
            "2",
            "--rstep",
            "60",
            "--view",
            "3d",
            "-s",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()


def test_rstep_range_requires_gif(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "0", "--rstep", "0:60"]
    )

    assert result.exit_code != 0
    assert "only valid with --gif" in result.output


def test_gif_requires_a_range_not_a_single_step(case1, runner):
    result = runner.invoke(
        main, [case1, "--keyword", "SGAS", "-k", "0", "--gif", "--rstep", "60"]
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


def test_unknown_keyword_is_a_clean_error(case1, offscreen, runner, tmp_path):
    del offscreen

    result = runner.invoke(
        main,
        [
            case1,
            "--keyword",
            "NOPE",
            "-k",
            "0",
            "--rstep",
            "60",
            "-s",
            str(tmp_path / "x.png"),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
