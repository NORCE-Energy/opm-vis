""" Unit tests for opm_vis.pvplot.camera """
import pytest

pytest.importorskip("pyvista")  # the pvplot backend is an optional extra

from opm_vis.pvplot.camera import Camera, ShownView  # noqa: E402


def test_text_round_trips_with_and_without_a_parallel_scale():
    perspective = Camera((527495.5, 6771119.0, -8300.25), (1.0, 2.0, 3.0), (0.0, 0.0, 1.0))
    parallel = Camera((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (0.0, 1.0, 0.0), 1234.5)

    assert Camera.from_text(perspective.to_text()) == perspective
    assert Camera.from_text(parallel.to_text()) == parallel
    assert parallel.to_text() == "1,2,3/4,5,6/0,1,0/1234.5"


def test_text_keeps_utm_coordinates_to_the_decimetre():
    camera = Camera((527495.53, 6771119.07, -3333.7), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    assert Camera.from_text(camera.to_text()).position == pytest.approx(camera.position)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1,2,3/4,5,6", "optional /SCALE"),
        ("1,2/4,5,6/0,0,1", "3 comma-separated numbers"),
        ("1,2,x/4,5,6/0,0,1", "not a number"),
        ("1,2,3/4,5,6/0,0,0", "view-up vector cannot be zero"),
        ("1,2,3/4,5,6/0,0,1/-2", "must be positive"),
    ],
)
def test_invalid_text_is_rejected(text, message):
    with pytest.raises(ValueError, match=message):
        Camera.from_text(text)


def test_shown_view_prints_the_options_that_reproduce_it():
    shown = ShownView(Camera((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (0.0, 0.0, 1.0)), (800, 600))

    assert shown.cli_options() == "--camera 1,2,3/4,5,6/0,0,1 --window-size 800 600"
