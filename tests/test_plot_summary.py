""" Unit tests for opm_vis.plot.plot_summary, backed by the SPE1CASE1/SPE1CASE2 test datasets """
import shutil

import matplotlib
import pytest

matplotlib.use("Agg")  # headless: never try to open a GUI window while testing

import matplotlib.pyplot as plt  # noqa: E402

from opm_vis.plot.plot_summary import (  # noqa: E402
    SummaryPlot,
    axes_ylabel,
    curve_label,
    default_figsize,
    subplot_grid,
    unique_case_labels,
    x_axis_values,
)
from opm_vis.utils.summary import SummaryReader  # noqa: E402

# The case1/data_dir fixtures come from conftest.py: SPE1CASE1 has 123 summary timesteps from
# 2015-01-02 to 2024-12-29, in field units, with FOPR, FGOR, WBHP:PROD and one vector per well.


@pytest.fixture(autouse=True)
def close_figures():
    # Only show()/save_plot() close the figure they made, and most tests here call neither, so
    # without this the module leaks a figure per test and Matplotlib warns past twenty of them
    yield
    plt.close("all")


@pytest.fixture(scope="module")
def compare_paths(tmp_path_factory, data_dir):
    # SPE1CASE2 and SPE1CASE2_RESTART_60 share the "SPE1CASE2" filename prefix in tests/data, so
    # glob("...SPE1CASE2*.SMSPEC") would ambiguously match both - each is copied into its own
    # directory, which is also how separate runs are kept in practice. Both end up named CASE,
    # which is exactly the collision unique_case_labels has to resolve.
    base = tmp_path_factory.mktemp("compare_data")
    first = base / "runA"
    second = base / "runB"
    first.mkdir()
    second.mkdir()

    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / f"SPE1CASE2{ext}", first / f"CASE{ext}")
        shutil.copy(data_dir / f"SPE1CASE2_RESTART_60{ext}", second / f"CASE{ext}")

    return [str(first / "CASE"), str(second / "CASE")]


# ---------------------------------------------------------------------------
# subplot_grid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n_axes, expected",
    [(1, (1, 1)), (2, (1, 2)), (3, (2, 2)), (4, (2, 2)), (5, (2, 3)), (8, (3, 3)), (12, (3, 4))],
)
def test_grid_spreads_sideways(n_axes, expected):
    assert subplot_grid(n_axes) == expected


def test_grid_keeps_an_explicit_layout():
    assert subplot_grid(3, (3, 1)) == (3, 1)


def test_grid_rejects_a_layout_with_no_room():
    with pytest.raises(ValueError, match="room for 2"):
        subplot_grid(3, (1, 2))


def test_grid_rejects_a_non_positive_layout():
    with pytest.raises(ValueError, match="must be positive"):
        subplot_grid(1, (0, 2))


def test_grid_rejects_an_empty_figure():
    with pytest.raises(ValueError, match="at least one subplot"):
        subplot_grid(0)


# ---------------------------------------------------------------------------
# default_figsize
# ---------------------------------------------------------------------------


def test_a_single_axes_keeps_matplotlibs_own_size():
    assert default_figsize(1, 1) is None


def test_a_grid_gets_a_size_scaled_to_its_shape():
    assert default_figsize(2, 3) == (12.0, 5.6)


def test_a_large_grid_is_capped():
    width, height = default_figsize(8, 8)

    assert (width, height) == (16.0, 11.0)


# ---------------------------------------------------------------------------
# x_axis_values
# ---------------------------------------------------------------------------


def test_x_values_are_dates_by_default(case1):
    values = x_axis_values(SummaryReader([case1]), "date")

    assert len(values) == 123
    assert values[-1].year == 2024


def test_x_values_can_be_elapsed_days(case1):
    assert x_axis_values(SummaryReader([case1]), "days")[0] == pytest.approx(1.0)


def test_x_values_can_be_elapsed_years(case1):
    assert x_axis_values(SummaryReader([case1]), "years")[-1] == pytest.approx(9.993, abs=1e-3)


def test_x_values_reject_an_unknown_axis(case1):
    with pytest.raises(ValueError, match="x_axis must be one of"):
        x_axis_values(SummaryReader([case1]), "hours")


# ---------------------------------------------------------------------------
# unique_case_labels / curve_label / axes_ylabel
# ---------------------------------------------------------------------------


def test_case_labels_use_the_file_name(case1):
    assert unique_case_labels([SummaryReader([case1])]) == ["SPE1CASE1"]


def test_case_labels_gain_their_directory_when_names_collide(compare_paths):
    readers = [SummaryReader([path]) for path in compare_paths]

    assert unique_case_labels(readers) == ["runA/CASE", "runB/CASE"]


def test_curve_label_names_the_keyword_for_one_case():
    assert curve_label("FOPR", "BASE", multi_keyword=True, multi_case=False) == "FOPR"


def test_curve_label_names_the_case_when_only_it_varies():
    assert curve_label("FOPR", "BASE", multi_keyword=False, multi_case=True) == "BASE"


def test_curve_label_names_both_when_both_vary():
    assert (
        curve_label("FOPR", "BASE", multi_keyword=True, multi_case=True) == "BASE - FOPR"
    )


def test_ylabel_names_a_single_keyword_with_its_unit():
    assert axes_ylabel(["FOPR"], ["STB/DAY"]) == "FOPR [stb/day]"


def test_ylabel_names_a_few_keywords_sharing_a_unit():
    assert axes_ylabel(["FOPR", "FWPR"], ["STB/DAY", "STB/DAY"]) == "FOPR, FWPR [stb/day]"


def test_ylabel_drops_the_names_of_many_keywords():
    keywords = ["A", "B", "C", "D"]

    assert axes_ylabel(keywords, ["STB/DAY"] * 4) == "[stb/day]"


def test_ylabel_warns_when_the_units_differ():
    with pytest.warns(UserWarning, match="different units"):
        label = axes_ylabel(["FOPR", "FGOR"], ["STB/DAY", "MSCF/STB"])

    assert label == "stb/day / Mscf/stb"


# ---------------------------------------------------------------------------
# SummaryPlot - construction
# ---------------------------------------------------------------------------


def test_plot_rejects_no_paths():
    with pytest.raises(ValueError, match="No paths given"):
        SummaryPlot([])


def test_plot_rejects_a_path_without_a_summary_file(tmp_path):
    with pytest.warns(UserWarning, match="No .SMSPEC found"):
        with pytest.raises(ValueError, match="No .SMSPEC file was found"):
            SummaryPlot([str(tmp_path / "MISSING")])


def test_plot_names_the_offending_case_when_comparing(case1, tmp_path):
    with pytest.warns(UserWarning, match="No .SMSPEC found"):
        with pytest.raises(ValueError, match="MISSING"):
            SummaryPlot([case1, str(tmp_path / "MISSING")], compare=True)


def test_available_keywords_are_sorted(case1):
    keywords = SummaryPlot([case1]).available_keywords()

    assert "FOPR" in keywords
    assert keywords == sorted(keywords)


def test_available_keywords_union_the_cases(compare_paths):
    plot = SummaryPlot(compare_paths, compare=True)

    assert "FOPR" in plot.available_keywords()


# ---------------------------------------------------------------------------
# SummaryPlot.plot - one axes
# ---------------------------------------------------------------------------


def test_plot_draws_one_curve_per_keyword(case1):
    plot = SummaryPlot([case1])
    plot.plot(["WOPR:PROD", "WOPR:INJ"])

    assert len(plot.axes) == 1
    assert len(plot.lines) == 2


def test_plot_labels_the_axes(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"])

    assert plot.axes[0].get_ylabel() == "FOPR [stb/day]"
    assert plot.axes[0].get_xlabel() == "Date"


def test_plot_labels_the_x_axis_per_kind(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"], x_axis="years")

    assert plot.axes[0].get_xlabel() == "Time [years]"


def test_plot_titles_the_figure_with_the_case_name(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"])

    assert plot.fig is not None
    assert plot.fig.get_suptitle() == "SPE1CASE1"


def test_plot_takes_an_explicit_title(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"], title="Field rates")

    assert plot.fig is not None
    assert plot.fig.get_suptitle() == "Field rates"


def test_plot_rejects_no_keywords(case1):
    with pytest.raises(ValueError, match="No keywords given"):
        SummaryPlot([case1]).plot([])


def test_plot_rejects_an_unknown_x_axis(case1):
    with pytest.raises(ValueError, match="x_axis must be one of"):
        SummaryPlot([case1]).plot(["FOPR"], x_axis="hours")


# ---------------------------------------------------------------------------
# SummaryPlot.plot - legend
# ---------------------------------------------------------------------------


def test_a_single_curve_gets_no_legend(case1):
    # Its y label already names it
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"])

    assert plot.axes[0].get_legend() is None


def test_several_keywords_get_a_legend_of_keyword_names(case1):
    plot = SummaryPlot([case1])
    plot.plot(["WOPR:PROD", "WOPR:INJ"])

    labels = [text.get_text() for text in plot.axes[0].get_legend().get_texts()]
    assert labels == ["WOPR:PROD", "WOPR:INJ"]


def test_comparing_cases_gives_a_legend_of_case_names(compare_paths):
    plot = SummaryPlot(compare_paths, compare=True)
    plot.plot(["FOPR"])

    labels = [text.get_text() for text in plot.axes[0].get_legend().get_texts()]
    assert labels == ["runA/CASE", "runB/CASE"]


def test_comparing_several_keywords_names_both(compare_paths):
    plot = SummaryPlot(compare_paths, compare=True)
    plot.plot(["WOPR:PROD", "WOPR:INJ"])

    labels = [text.get_text() for text in plot.axes[0].get_legend().get_texts()]
    assert labels == [
        "runA/CASE - WOPR:PROD",
        "runB/CASE - WOPR:PROD",
        "runA/CASE - WOPR:INJ",
        "runB/CASE - WOPR:INJ",
    ]


def test_the_legend_can_be_turned_off(case1):
    plot = SummaryPlot([case1])
    plot.plot(["WOPR:PROD", "WOPR:INJ"], legend=False)

    assert plot.axes[0].get_legend() is None


# ---------------------------------------------------------------------------
# SummaryPlot.plot - subplots
# ---------------------------------------------------------------------------


def test_subplots_give_each_keyword_its_own_axes(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR", "FGOR", "WBHP:PROD"], subplots=True)

    assert len(plot.axes) == 3
    assert [ax_.get_ylabel() for ax_ in plot.axes] == [
        "FOPR [stb/day]",
        "FGOR [Mscf/stb]",
        "WBHP:PROD [psia]",
    ]


def test_subplots_label_the_x_axis_at_the_bottom_of_each_column(case1):
    # Three keywords fill a 2x2 grid, so the left column ends at row 2 and the right at row 1;
    # sharex hid the labels of the axes above them, and only those two should get one back
    plot = SummaryPlot([case1])
    plot.plot(["FOPR", "FGOR", "WBHP:PROD"], subplots=True)

    assert [bool(ax_.get_xlabel()) for ax_ in plot.axes] == [False, True, True]


def test_subplots_remove_the_unused_axes_of_a_partial_grid(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR", "FGOR", "WBHP:PROD"], subplots=True)

    assert plot.fig is not None
    assert len(plot.fig.axes) == 3


def test_subplots_take_an_explicit_layout(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR", "FGOR"], subplots=True, layout=(2, 1))

    assert plot.fig is not None
    assert plot.axes[0].get_subplotspec().get_gridspec().get_geometry() == (2, 1)


def test_subplots_reject_a_layout_with_no_room(case1):
    with pytest.raises(ValueError, match="room for 2"):
        SummaryPlot([case1]).plot(["FOPR", "FGOR", "WBHP:PROD"], subplots=True, layout=(1, 2))


def test_a_case_keeps_one_colour_across_subplots(compare_paths):
    # Each axes restarts Matplotlib's own property cycle, so the colours have to be set
    # explicitly for the legend of one subplot to mean anything in the next
    plot = SummaryPlot(compare_paths, compare=True)
    plot.plot(["FOPR", "FGOR"], subplots=True)

    first, second = plot.axes[0].get_lines(), plot.axes[1].get_lines()
    assert [line.get_color() for line in first] == [line.get_color() for line in second]


# ---------------------------------------------------------------------------
# SummaryPlot - presentation and output
# ---------------------------------------------------------------------------


def test_log_y_switches_the_scale(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"], log_y=True)

    assert plot.axes[0].get_yscale() == "log"


def test_log_y_warns_about_a_curve_that_cannot_be_drawn(case1):
    # WOPR:INJ is zero throughout, so a logarithmic axis simply drops it
    with pytest.warns(UserWarning, match="no positive values"):
        SummaryPlot([case1]).plot(["WOPR:INJ"], log_y=True)


def test_limits_are_applied(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"], x_axis="days", xlim=(0.0, 1000.0), ylim=(0.0, 25000.0))

    assert plot.axes[0].get_xlim() == (0.0, 1000.0)
    assert plot.axes[0].get_ylim() == (0.0, 25000.0)


def test_grid_can_be_turned_off(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"], grid=False)

    assert not plot.axes[0].xaxis.get_gridlines()[0].get_visible()


def test_linewidth_is_applied_to_every_curve(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR", "FGOR"], linewidth=3.0)

    assert [line.get_linewidth() for line in plot.lines] == [3.0, 3.0]


def test_linewidth_defaults_to_matplotlibs_own(case1):
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"])

    assert plot.lines[0].get_linewidth() == plt.rcParams["lines.linewidth"]


def test_linewidth_rejects_a_non_positive_value(case1):
    with pytest.raises(ValueError, match="linewidth must be positive"):
        SummaryPlot([case1]).plot(["FOPR"], linewidth=0)


def test_save_plot_writes_a_file(case1, tmp_path):
    out = tmp_path / "fopr.png"
    plot = SummaryPlot([case1])
    plot.plot(["FOPR"])
    plot.save_plot(out)

    assert out.stat().st_size > 0


def test_save_plot_generates_a_name_next_to_the_case(data_dir, tmp_path):
    # The generated name is built from the input prefix, so it lands beside the case rather than
    # in the working directory - hence a copy of the case in tmp_path, not a chdir into it
    for ext in (".SMSPEC", ".UNSMRY"):
        shutil.copy(data_dir / f"SPE1CASE1{ext}", tmp_path / f"SPE1CASE1{ext}")

    plot = SummaryPlot([str(tmp_path / "SPE1CASE1")])
    plot.plot(["FOPR", "WOPR:PROD"])
    plot.save_plot()

    assert (tmp_path / "SPE1CASE1FOPR_WOPR-PROD.png").exists()


def test_save_plot_refuses_before_anything_is_drawn(case1, tmp_path):
    with pytest.raises(RuntimeError, match="No plot to save"):
        SummaryPlot([case1]).save_plot(tmp_path / "nothing.png")


# ---------------------------------------------------------------------------
# SummaryPlot.export_csv
# ---------------------------------------------------------------------------


def test_export_csv_has_one_column_per_keyword(case1):
    lines = SummaryPlot([case1]).export_csv(["FOPR", "FGOR"]).splitlines()

    assert lines[0] == "date,FOPR,FGOR"
    assert len(lines) == 124  # header + 123 timesteps


def test_export_csv_dates_are_iso_8601(case1):
    lines = SummaryPlot([case1]).export_csv(["FOPR"]).splitlines()

    assert lines[1].startswith("2015-01-02T00:00:00,")
    assert lines[-1].startswith("2024-12-29T00:00:00,")


def test_export_csv_can_use_days_or_years(case1):
    days = SummaryPlot([case1]).export_csv(["FOPR"], x_axis="days").splitlines()
    years = SummaryPlot([case1]).export_csv(["FOPR"], x_axis="years").splitlines()

    assert days[0] == "days,FOPR"
    assert days[1].startswith("1,")
    assert years[0] == "years,FOPR"


def test_export_csv_rounds_values_to_six_significant_digits(case1):
    lines = SummaryPlot([case1]).export_csv(["FOPR"]).splitlines()

    assert lines[1] == "2015-01-02T00:00:00,20000"


def test_export_csv_prefixes_columns_with_the_case_under_compare(compare_paths):
    lines = SummaryPlot(compare_paths, compare=True).export_csv(["FOPR"]).splitlines()

    assert lines[0] == "date,runA/CASE:FOPR,runB/CASE:FOPR"


def test_export_csv_aligns_mismatched_cases_and_blanks_missing_cells(compare_paths):
    # runA is the full run, runB restarts it from report step 60: rows before runB started only
    # have a value in runA's column, and both share every row after that
    rows = SummaryPlot(compare_paths, compare=True).export_csv(["FOPR"]).splitlines()[1:]

    first_row = rows[0].split(",")
    assert first_row[1] != ""
    assert first_row[2] == ""

    last_row = rows[-1].split(",")
    assert last_row[1] != ""
    assert last_row[2] != ""


def test_export_csv_rejects_no_keywords(case1):
    with pytest.raises(ValueError, match="No keywords given"):
        SummaryPlot([case1]).export_csv([])


def test_export_csv_rejects_an_unknown_x_axis(case1):
    with pytest.raises(ValueError, match="x_axis must be one of"):
        SummaryPlot([case1]).export_csv(["FOPR"], x_axis="hours")


def test_export_csv_does_not_require_plot_to_have_been_called(case1):
    # Export is independent of the figure: it should work even if plot() was never run
    text = SummaryPlot([case1]).export_csv(["FOPR"])

    assert text.startswith("date,FOPR")
