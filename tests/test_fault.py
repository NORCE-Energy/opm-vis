""" Unit tests for opm_vis.utils.fault, backed by synthetic deck files """
import pytest

from opm_vis.utils.fault import FaultFace, FaultReader

# ---------------------------------------------------------------------------
# Single file, single FAULTS keyword
# ---------------------------------------------------------------------------


def test_reads_fault_names_and_faces(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
  'FAULT2'  3 3 2 2 1 3 'Y-' /
/
"""
    )

    reader = FaultReader(str(data))

    assert reader.names() == ["FAULT1", "FAULT2"]
    assert reader.faces("FAULT1") == [FaultFace(0, 0, 0, 4, 0, 2, "X")]
    assert reader.faces("FAULT2") == [FaultFace(2, 2, 1, 1, 0, 2, "Y-")]


def test_normalizes_ijk_face_aliases_to_xyz(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'F'  1 1 1 1 1 1 'I-' /
  'F'  1 1 1 1 1 1 'J' /
  'F'  1 1 1 1 1 1 'K-' /
/
"""
    )

    faces = FaultReader(str(data)).faces("F")

    assert [f.face for f in faces] == ["X-", "Y", "Z-"]


def test_accumulates_multiple_records_for_the_same_fault_name(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
  'FAULT1'  2 2 1 5 1 3 'J' /
/
"""
    )

    faces = FaultReader(str(data)).faces("FAULT1")

    assert len(faces) == 2
    assert faces[0].face == "X"
    assert faces[1].face == "Y"


def test_accumulates_across_repeated_faults_keyword(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
/

FAULTS
  'FAULT1'  2 2 1 5 1 3 'J' /
/
"""
    )

    faces = FaultReader(str(data)).faces("FAULT1")

    assert len(faces) == 2
    assert faces[0].face == "X"
    assert faces[1].face == "Y"


# ---------------------------------------------------------------------------
# INCLUDE resolution: a full .DATA file pulling in a standalone include file
# ---------------------------------------------------------------------------


def test_reads_faults_from_an_included_file(tmp_path):
    (tmp_path / "FAULTS.INC").write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
/
"""
    )
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        """
RUNSPEC

GRID

INCLUDE
 'FAULTS.INC' /

FAULTS
 'FAULT2' 4 4 1 5 1 3 'X' /
/
"""
    )

    reader = FaultReader(str(main))

    assert reader.names() == ["FAULT1", "FAULT2"]


def test_reads_faults_from_a_standalone_include_file_directly(tmp_path):
    include = tmp_path / "FAULTS.INC"
    include.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
/
"""
    )

    reader = FaultReader(str(include))

    assert reader.names() == ["FAULT1"]


# ---------------------------------------------------------------------------
# No FAULTS keyword / error cases
# ---------------------------------------------------------------------------


def test_has_faults_false_when_no_faults_keyword_present(tmp_path):
    data = tmp_path / "NOFAULTS.DATA"
    data.write_text("RUNSPEC\n")

    reader = FaultReader(str(data))

    assert reader.has_faults() is False
    assert reader.names() == []


def test_has_faults_true_when_faults_keyword_present(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
/
"""
    )

    assert FaultReader(str(data)).has_faults() is True


def test_faces_raises_for_unknown_fault_name(tmp_path):
    data = tmp_path / "FAULTS.DATA"
    data.write_text(
        """
FAULTS
  'FAULT1'  1 1 1 5 1 3 'I' /
/
"""
    )
    reader = FaultReader(str(data))

    with pytest.raises(KeyError, match="UNKNOWN"):
        reader.faces("UNKNOWN")


def test_missing_file_raises():
    with pytest.raises(RuntimeError):
        FaultReader("/no/such/file.DATA")
