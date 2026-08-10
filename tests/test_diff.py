""" Unit tests for opm_vis.utils.diff, shared by the pvplot and plot backends """
import warnings

import numpy as np
import pytest

from opm_vis.utils.diff import compute_diff, diff_label

# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------


def test_plain_is_current_minus_reference():
    current = np.array([5.0, 2.0, -1.0])
    reference = np.array([3.0, 2.0, 1.0])

    np.testing.assert_allclose(compute_diff(current, reference, "plain"), [2.0, 0.0, -2.0])


def test_absolute_is_the_plain_difference_magnitude():
    current = np.array([5.0, 2.0, -1.0])
    reference = np.array([3.0, 2.0, 1.0])

    np.testing.assert_allclose(compute_diff(current, reference, "absolute"), [2.0, 0.0, 2.0])


def test_relative_is_percent_change_from_reference():
    current = np.array([120.0, 50.0])
    reference = np.array([100.0, 50.0])

    np.testing.assert_allclose(compute_diff(current, reference, "relative"), [20.0, 0.0])


def test_relative_does_not_warn_when_reference_is_zero():
    current = np.array([1.0, 0.0])
    reference = np.array([0.0, 0.0])

    # NumPy's own divide-by-zero/invalid warnings are expected here and suppressed by
    # compute_diff; turning warnings into errors catches a regression if that ever slips.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = compute_diff(current, reference, "relative")

    assert np.isinf(result[0])
    assert np.isnan(result[1])  # 0/0


def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="plain"):
        compute_diff(np.array([1.0]), np.array([0.0]), "bogus")


# ---------------------------------------------------------------------------
# diff_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, expected",
    [("plain", "ΔSGAS"), ("relative", "ΔSGAS"), ("absolute", "|ΔSGAS|")],
)
def test_diff_label_by_kind(kind, expected):
    assert diff_label("SGAS", kind) == expected


def test_diff_label_rejects_an_unknown_kind():
    with pytest.raises(ValueError, match="plain"):
        diff_label("SGAS", "bogus")
