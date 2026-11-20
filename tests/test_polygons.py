""" Unit tests for opm_vis.utils.polygons """
import json

import numpy as np
import pytest

from opm_vis.utils.polygons import Polygon, read_polygons, warn_outside

_SQUARE = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])


# ---------------------------------------------------------------------------
# NumPy
# ---------------------------------------------------------------------------


def test_npy_single_polygon_is_named_after_the_file_and_closed(tmp_path):
    path = tmp_path / "outline.npy"
    np.save(path, _SQUARE)

    (polygon,) = read_polygons(path)

    assert polygon.name == "outline"
    assert not polygon.has_depth
    assert polygon.points.shape == (5, 2)
    assert np.array_equal(polygon.points[0], polygon.points[-1])


def test_npy_already_closed_polygon_is_left_alone(tmp_path):
    path = tmp_path / "outline.npy"
    np.save(path, np.vstack([_SQUARE, _SQUARE[:1]]))

    (polygon,) = read_polygons(path)

    assert polygon.points.shape == (5, 2)


def test_npy_stack_gives_one_numbered_polygon_each(tmp_path):
    path = tmp_path / "areas.npy"
    np.save(path, np.stack([_SQUARE, _SQUARE + 20]))

    polygons = read_polygons(path)

    assert [p.name for p in polygons] == ["areas_1", "areas_2"]


def test_npz_names_each_polygon_by_its_key(tmp_path):
    path = tmp_path / "polygons.npz"
    np.savez(path, north=_SQUARE, deep=np.array([[0, 0, 100], [10, 10, 200]]))

    polygons = {p.name: p for p in read_polygons(path)}

    assert set(polygons) == {"north", "deep"}
    assert polygons["deep"].has_depth
    # A 2-point line is not closed into a degenerate ring
    assert polygons["deep"].points.shape == (2, 3)


def test_npy_with_the_wrong_shape_is_rejected(tmp_path):
    path = tmp_path / "bad.npy"
    np.save(path, np.zeros((4, 4)))

    with pytest.raises(ValueError, match=r"shape \(n, 2\)"):
        read_polygons(path)


def test_npy_with_nan_is_rejected(tmp_path):
    path = tmp_path / "bad.npy"
    np.save(path, np.array([[0.0, 0.0], [np.nan, 1.0], [1.0, 1.0]]))

    with pytest.raises(ValueError, match="finite"):
        read_polygons(path)


def test_corrupt_npy_is_a_clean_error(tmp_path):
    path = tmp_path / "bad.npy"
    path.write_bytes(b"not numpy")

    with pytest.raises(ValueError, match="not a valid NumPy .npy file"):
        read_polygons(path)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def test_text_splits_polygons_on_blank_lines_and_skips_header_and_comments(tmp_path):
    path = tmp_path / "areas.csv"
    path.write_text("x,y,z\n# first\n0,0,100\n10,0,100\n10,10,100\n\n\n5 5 50\n6 6 60\n")

    first, second = read_polygons(path)

    assert (first.name, second.name) == ("areas_1", "areas_2")
    assert first.has_depth and first.points.shape == (4, 3)  # closed
    assert second.points.shape == (2, 3)


def test_text_with_mixed_column_counts_is_rejected(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("0 0\n1 1 1\n2 2\n")

    with pytest.raises(ValueError, match="mixes rows"):
        read_polygons(path)


def test_text_with_a_non_number_after_the_first_point_names_the_line(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("0 0\n1 one\n")

    with pytest.raises(ValueError, match="line 2"):
        read_polygons(path)


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def _feature(geometry, name=None):
    return {"type": "Feature", "properties": {"name": name} if name else {}, "geometry": geometry}


def test_geojson_reads_named_polygons_with_holes_and_lines(tmp_path):
    path = tmp_path / "licence.geojson"
    ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 4]]
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    _feature({"type": "Polygon", "coordinates": [ring, hole]}, name="Licence A"),
                    _feature({"type": "LineString", "coordinates": [[0, 0, 5], [1, 1, 6]]}),
                    _feature({"type": "Point", "coordinates": [0, 0]}),
                ],
            }
        )
    )

    polygons = read_polygons(path)

    # The polygon's outer ring and hole share its name; the unnamed line is named after the file
    assert [p.name for p in polygons] == ["Licence A", "Licence A", "licence"]
    assert polygons[2].has_depth
    assert polygons[2].points.shape == (2, 3)  # line strings stay open


def test_geojson_bare_geometry_is_accepted(tmp_path):
    path = tmp_path / "area.json"
    path.write_text(json.dumps({"type": "MultiPolygon", "coordinates": [[_SQUARE.tolist()]]}))

    (polygon,) = read_polygons(path)

    assert polygon.name == "area"


def test_geojson_without_lines_is_rejected(tmp_path):
    path = tmp_path / "points.geojson"
    path.write_text(json.dumps({"type": "Point", "coordinates": [0, 0]}))

    with pytest.raises(ValueError, match="No Polygon"):
        read_polygons(path)


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------


def test_several_files_are_read_in_order(tmp_path):
    first = tmp_path / "a.npy"
    second = tmp_path / "b.txt"
    np.save(first, _SQUARE)
    second.write_text("0 0\n1 1\n")

    assert [p.name for p in read_polygons([first, second])] == ["a", "b"]


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "area.shp"
    path.write_bytes(b"")

    with pytest.raises(ValueError, match="Unsupported polygon file"):
        read_polygons(path)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_polygons(tmp_path / "missing.npy")


def test_label_point_is_the_vertex_mean_of_a_closed_polygon():
    closed = Polygon("a", np.vstack([_SQUARE, _SQUARE[:1]]))
    line = Polygon("b", np.array([[3.0, 4.0], [5.0, 6.0]]))

    assert np.allclose(closed.label_point(), [5.0, 5.0])
    assert np.allclose(line.label_point(), [3.0, 4.0])


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def test_labels_rename_every_polygon_of_their_file(tmp_path):
    first = tmp_path / "areas.npz"
    second = tmp_path / "b.npy"
    np.savez(first, north=_SQUARE, south=_SQUARE + 20)
    np.save(second, _SQUARE)

    polygons = read_polygons([first, second], labels=["Areas", None])

    assert [p.name for p in polygons] == ["Areas", "Areas", "b"]
    assert [p.source for p in polygons] == [str(first), str(first), str(second)]


def test_empty_label_leaves_a_file_unlabelled(tmp_path):
    path = tmp_path / "a.npy"
    np.save(path, _SQUARE)

    (polygon,) = read_polygons(path, labels=[""])

    assert polygon.name == ""
    assert polygon.describe() == "a.npy"


def test_labels_must_match_the_number_of_files(tmp_path):
    path = tmp_path / "a.npy"
    np.save(path, _SQUARE)

    with pytest.raises(ValueError, match="one label per file"):
        read_polygons(path, labels=["x", "y"])


# ---------------------------------------------------------------------------
# warn_outside
# ---------------------------------------------------------------------------


def test_warn_outside_names_polygons_missing_the_plotted_region():
    inside = Polygon("in", _SQUARE, "in.npy")
    partly = Polygon("partly", _SQUARE + 95, "partly.npy")
    outside = Polygon("km", _SQUARE / 1000 + 500, "km.npy")
    polygons = [inside, partly, outside]

    with pytest.warns(UserWarning, match=r"1 polygon\(s\) lie entirely outside.*km \(km\.npy\)"):
        warn_outside(polygons, [p.points for p in polygons], np.zeros(2), np.full(2, 100.0))


def test_warn_outside_is_silent_when_everything_overlaps(recwarn):
    polygon = Polygon("in", _SQUARE)

    warn_outside([polygon], [polygon.points], np.zeros(2), np.full(2, 100.0))

    assert not recwarn.list
