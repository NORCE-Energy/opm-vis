""" Tests for opm_vis.utils.cases, backed by the SPE1CASE2 main run and its restart """
import shutil

import pytest

from opm_vis.utils.cases import case_files, find_cases

# SPE1CASE2's restart files start at report step 0 and its summary TIME at day 1;
# SPE1CASE2_RESTART_60's at report step 61 and day 1856.
_EXTS = (".EGRID", ".INIT", ".SMSPEC", ".UNRST", ".UNSMRY")


def _copy_case(data_dir, source, target_dir, name, exts=_EXTS):
    for ext in exts:
        shutil.copy(data_dir / "SPE1CASE2" / f"{source}{ext}", target_dir / f"{name}{ext}")


def test_case_files_match_the_prefix_exactly(case2_dir):
    files = case_files(f"{case2_dir}/SPE1CASE2", ".UNRST")

    assert [f.rsplit("/", 1)[-1] for f in files] == ["SPE1CASE2.UNRST"]


def test_case_files_of_a_directory_match_every_case_in_it(case2_dir):
    assert len(case_files(case2_dir, ".UNRST")) == 2


def test_case_files_find_numbered_x_files_in_order(tmp_path):
    for step in (2, 0, 1):
        (tmp_path / f"CASE.X{step:04d}").touch()
    (tmp_path / "CASE.XYZ").touch()

    files = case_files(str(tmp_path / "CASE"), ".X")

    assert [f[-5:] for f in files] == ["X0000", "X0001", "X0002"]


def test_find_cases_puts_the_main_run_first(case2_dir):
    cases = find_cases([case2_dir])

    assert [c.rsplit("/", 1)[-1] for c in cases] == ["SPE1CASE2", "SPE1CASE2_RESTART_60"]


def test_find_cases_orders_by_report_step_not_name(data_dir, tmp_path):
    _copy_case(data_dir, "SPE1CASE2", tmp_path, "Z_MAIN")
    _copy_case(data_dir, "SPE1CASE2_RESTART_60", tmp_path, "A_RESTART")

    cases = find_cases([str(tmp_path)])

    assert [c.rsplit("/", 1)[-1] for c in cases] == ["Z_MAIN", "A_RESTART"]


def test_find_cases_falls_back_to_summary_time(data_dir, tmp_path):
    _copy_case(data_dir, "SPE1CASE2", tmp_path, "Z_MAIN", (".SMSPEC", ".UNSMRY"))
    _copy_case(data_dir, "SPE1CASE2_RESTART_60", tmp_path, "A_RESTART", (".SMSPEC", ".UNSMRY"))

    cases = find_cases([str(tmp_path)])

    assert [c.rsplit("/", 1)[-1] for c in cases] == ["Z_MAIN", "A_RESTART"]


def test_find_cases_orders_across_folders(data_dir, tmp_path):
    main_dir = tmp_path / "main"
    restart_dir = tmp_path / "restart"
    main_dir.mkdir()
    restart_dir.mkdir()
    _copy_case(data_dir, "SPE1CASE2", main_dir, "CASE")
    _copy_case(data_dir, "SPE1CASE2_RESTART_60", restart_dir, "CASE")

    cases = find_cases([str(restart_dir), str(main_dir)])

    assert cases == [str(main_dir / "CASE"), str(restart_dir / "CASE")]


def test_find_cases_warns_when_two_cases_start_together(data_dir, tmp_path):
    _copy_case(data_dir, "SPE1CASE2", tmp_path, "B")
    _copy_case(data_dir, "SPE1CASE2", tmp_path, "A")

    with pytest.warns(UserWarning, match="start at the same point"):
        cases = find_cases([str(tmp_path)])

    assert [c.rsplit("/", 1)[-1] for c in cases] == ["A", "B"]


def test_find_cases_counts_a_folder_given_twice_once(case2_dir):
    assert len(find_cases([case2_dir, case2_dir + "/"])) == 2


def test_find_cases_ignores_non_output_files(tmp_path):
    (tmp_path / "CASE.DATA").touch()
    (tmp_path / "CASE_FAULTS.INC").touch()

    assert find_cases([str(tmp_path)]) == []


def test_find_cases_rejects_a_missing_folder(tmp_path):
    with pytest.raises(NotADirectoryError):
        find_cases([str(tmp_path / "MISSING")])
