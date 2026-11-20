"""opm-vis-mpl: plot a keyword on a grid slice with the alternative Matplotlib backend"""
from __future__ import annotations

from typing import Any

import click

from opm_vis.cli.common import (
    CALCULATOR_OPTIONS,
    CLIM_OPTION,
    CMAP_OPTION,
    COLORBAR_LABEL_OPTION,
    COMMAND_SETTINGS,
    DIFF_OPTIONS,
    GRID_ONLY_OPTIONS,
    KEYWORD_OPTION,
    FAULT_LABELS_OPTION,
    FOLDER_OPTION,
    FONT_SCALE_OPTION,
    POLYGON_OPTIONS,
    RSTEP_OR_ANIMATE_OPTIONS,
    SAVE_NAME_OPTION,
    SAVE_OPTION,
    SHOW_EDGES_OPTION,
    SLICE_OPTIONS,
    WELL_NAME_OPTION,
    add_options,
    check_colorbar_label,
    check_figsize,
    default_output_name,
    grid_color_kwargs,
    handle_errors,
    matplotlib_font_scale,
    parse_rstep,
    polygon_labels_arg,
    resolve_animate_rsteps,
    resolve_calculator,
    resolve_diff_rstep,
    resolve_keyword,
    resolve_keyword_rstep,
    resolve_paths,
    resolve_slices,
    save_folder_option,
    save_path,
    wants_save,
)
from opm_vis.plot.collections import SlicePoly2DCollection, SlicePoly3DCollection
from opm_vis.utils.calc import resolve_calc_range
from opm_vis.utils.grid import slice_dimension_size


# Default --save-folder names, inside the first -f/--folder
_FIGURE_FOLDER = "mpl-figs"
_ANIMATION_FOLDER = "mpl-gifs"


@click.command(**COMMAND_SETTINGS)
@FOLDER_OPTION
@KEYWORD_OPTION
@add_options(GRID_ONLY_OPTIONS)
@add_options(SLICE_OPTIONS)
@add_options(RSTEP_OR_ANIMATE_OPTIONS)
@add_options(DIFF_OPTIONS)
@add_options(CALCULATOR_OPTIONS)
@SAVE_OPTION
@SAVE_NAME_OPTION
@save_folder_option(_FIGURE_FOLDER, _ANIMATION_FOLDER)
@CMAP_OPTION
@CLIM_OPTION
@click.option(
    "--view",
    type=click.Choice(["2d", "3d"]),
    default="2d",
    show_default=True,
    help="Camera preset.",
)
@click.option("--log-scale", is_flag=True, default=False, help="Map colours logarithmically.")
@click.option("--no-colorbar", is_flag=True, default=False, help="Hide the colorbar.")
@COLORBAR_LABEL_OPTION
@click.option("--no-title", is_flag=True, default=False, help="Hide the report-date title.")
@click.option(
    "--figsize",
    type=(float, float),
    default=None,
    metavar="WIDTH HEIGHT",
    help="Figure size in inches. Defaults to a size following the slice's own proportions "
    "with --view 2d (clamped, so a thin cross-section still gets a usable height), and to "
    "Matplotlib's own figure size with --view 3d.",
)
@click.option(
    "--fault",
    "fault_path",
    default=None,
    metavar="PATH",
    help="Path to a .DATA file or an include file with FAULTS keyword(s); draws the fault "
    "trace(s) crossing the slice as lines, each annotated with its name. A fault whose own "
    "direction matches the slice's axis (e.g. an X/X- fault on an i-slice) is not drawn: it "
    "lies flush in the slice's own plane rather than crossing it as a line.",
)
@click.option(
    "--fault-name",
    "fault_names",
    multiple=True,
    metavar="NAME",
    help="Only draw this fault (repeatable). Only used with --fault. Without it, every fault "
    "crossing the slice is drawn.",
)
@FAULT_LABELS_OPTION
@WELL_NAME_OPTION
@add_options(POLYGON_OPTIONS)
@SHOW_EDGES_OPTION
@FONT_SCALE_OPTION
@handle_errors
@matplotlib_font_scale
# pylint: disable=too-many-arguments,too-many-locals
def main(
    folders: tuple[str, ...],
    keyword: str | None,
    grid_only: bool,
    grid_color: str | None,
    slice_i: tuple[int, ...],
    slice_j: tuple[int, ...],
    slice_k: tuple[int, ...],
    rstep: str | None,
    animate: bool,
    fps: int,
    diff: bool,
    diff_rstep: int,
    diff_kind: str,
    calc_kind: str | None,
    calc_count: int | None,
    save: bool,
    save_folder: str | None,
    save_name: str | None,
    cmap: str,
    clim: tuple[float, float] | None,
    view: str,
    log_scale: bool,
    no_colorbar: bool,
    colorbar_label: str | None,
    no_title: bool,
    figsize: tuple[float, float] | None,
    fault_path: str | None,
    fault_names: tuple[str, ...],
    fault_labels: bool,
    well_names: tuple[str, ...],
    polygon_paths: tuple[str, ...],
    polygon_color: str,
    polygon_linewidth: float | None,
    polygon_labels: tuple[str, ...],
    show_polygon_labels: bool,
    show_edges: bool,
    font_scale: float,
) -> None:
    """
    Plot --keyword on one grid slice with the Matplotlib backend, or animate it over report
    steps with --animate.

    The case is found in -f/--folder, by default the current folder. Several cases found
    there are read as one run: the main run followed by its restarts.

    This is the alternative backend, with fewer options and less development effort than
    opm-vis-pv (PyVista). See the documentation for the full option reference with examples.
    """
    keyword = resolve_keyword(keyword, grid_only)
    if grid_only and animate:
        raise click.UsageError("--grid-only does not support --animate yet.")

    slices = resolve_slices(slice_i, slice_j, slice_k)
    if not slices:
        raise click.UsageError(
            "Pass at least one of -i, -j, or -k to select a slice. opm-vis-mpl has no "
            "whole-grid view; use opm-vis-pv for that."
        )
    if len(slices) > 1:
        raise click.UsageError(
            "opm-vis-mpl only supports one slice; pass -i/-j/-k once. Use opm-vis-pv for "
            "multiple slices."
        )
    if calc_kind is not None and grid_only:
        raise click.UsageError(
            "--calculator needs --keyword; it has no effect with --grid-only."
        )
    if fault_names and fault_path is None:
        raise click.UsageError("--fault-name needs --fault.")
    check_colorbar_label(colorbar_label, no_colorbar=no_colorbar, grid_only=grid_only)
    polygon_labels_value = polygon_labels_arg(
        polygon_paths, polygon_labels, show_polygon_labels
    )
    slice_dim, slice_index = slices[0]
    rstep_value = parse_rstep(rstep, animate)
    # --diff has no effect in --grid-only (there is no --keyword to difference); see the
    # matching note in pvplot_cli.py.
    resolved_diff_rstep = None if grid_only else resolve_diff_rstep(diff, diff_rstep)
    resolve_calculator(calc_kind, calc_count, slices)

    # PolyCollection/Poly3DCollection draw no visible edge by default; an explicit edgecolor is
    # what --show-edges needs, unlike PyVista's own boolean show_edges kwarg.
    edge_kwargs = {"edgecolor": "black"} if show_edges else {}

    poly_kwargs: dict[str, Any] = {"cmap": cmap, **edge_kwargs}
    if clim is not None:
        poly_kwargs["clim"] = clim

    check_figsize(figsize)

    resolved_paths = resolve_paths(folders)
    surface = calc_kind == "surface"
    if view == "3d":
        coll = SlicePoly3DCollection(
            resolved_paths,
            [(slice_dim, slice_index)],
            calc_count=calc_count,
            surface=surface,
            figsize=figsize,
        )
    else:
        coll = SlicePoly2DCollection(
            resolved_paths,
            slice_dim,
            slice_index,
            calc_count=calc_count,
            surface=surface,
            figsize=figsize,
        )

    if fault_path is not None:
        coll.plot_faults(fault_path, names=list(fault_names) or None, labels=fault_labels)
    if polygon_paths:
        line_kwargs: dict[str, Any] = {}
        if polygon_linewidth is not None:
            line_kwargs["linewidth"] = polygon_linewidth
        coll.plot_polygons(
            list(polygon_paths),
            labels=polygon_labels_value,
            color=polygon_color,
            **line_kwargs,
        )

    calc_end = None
    if calc_kind is not None:
        n_slice = slice_dimension_size(coll.slice_coll[0].egrid, slice_dim)
        _, calc_end = resolve_calc_range(slice_index, n_slice, calc_count)

    if animate:
        # grid_only+animate already raised above, so resolve_keyword guarantees a keyword here
        assert keyword is not None
        # --animate always parses --rstep with animate=True (see parse_rstep), so this is a
        # range or None, never a bare int
        assert rstep_value is None or isinstance(rstep_value, tuple)
        steps = resolve_animate_rsteps(coll.report.report_steps(), rstep_value)
        coll.animate(
            keyword,
            rstep_list=steps,
            diff_rstep=resolved_diff_rstep,
            diff_kind=diff_kind,
            calc_kind=calc_kind,
            calc_count=calc_count,
            colorbar_label=colorbar_label,
            title=not no_title,
            well_names=list(well_names) or None,
            log_scale=log_scale,
            **poly_kwargs,
        )

        if not wants_save(save, save_folder, save_name):
            coll.show()
        else:
            coll.save_gif(
                save_path(
                    save_folder,
                    default_output_name(
                        keyword,
                        slices,
                        rsteps=steps,
                        ext="gif",
                        diff_rstep=resolved_diff_rstep,
                        diff_kind=diff_kind,
                        calc_kind=calc_kind,
                        calc_end=calc_end,
                    ),
                    folders=folders,
                    default=_ANIMATION_FOLDER,
                    save_name=save_name,
                ),
                fps=fps,
            )
        return

    if grid_only:
        # Time-invariant: unlike a keyword's own values, the bare grid has no report step to
        # pick, so plot_grid()/save_grid_plot() need none either.
        coll.plot_grid(**grid_color_kwargs(grid_color), **edge_kwargs)

        if not wants_save(save, save_folder, save_name):
            coll.show()
        else:
            coll.save_grid_plot(
                save_path(
                    save_folder,
                    default_output_name("GRID", slices, ext="png"),
                    folders=folders,
                    default=_FIGURE_FOLDER,
                    save_name=save_name,
                )
            )
        return

    # Reached only when not animate (the branch above returns), so --rstep was parsed with
    # animate=False (see parse_rstep): a bare int or None, never a range
    assert rstep_value is None or isinstance(rstep_value, int)
    # Reached only when not grid_only (the branch above returns), so resolve_keyword
    # guarantees a keyword here
    assert keyword is not None

    first_slice = coll.slice_coll[0]
    actual_rstep = resolve_keyword_rstep(
        keyword, rstep_value, coll.report.report_steps(), first_slice.restart, first_slice.static
    )
    if actual_rstep is None and resolved_diff_rstep is not None:
        raise click.UsageError("--diff needs restart data, but this case has no report steps.")

    coll.plot(
        actual_rstep,
        keyword,
        colorbar=not no_colorbar,
        colorbar_label=colorbar_label,
        title=not no_title,
        well_names=list(well_names) or None,
        log_scale=log_scale,
        diff_rstep=resolved_diff_rstep,
        diff_kind=diff_kind,
        calc_kind=calc_kind,
        calc_count=calc_count,
        **poly_kwargs,
    )

    if not wants_save(save, save_folder, save_name):
        coll.show()
    else:
        coll.save_plot(
            save_path(
                save_folder,
                default_output_name(
                    keyword,
                    slices,
                    rstep=actual_rstep,
                    ext="png",
                    diff_rstep=resolved_diff_rstep,
                    diff_kind=diff_kind,
                    calc_kind=calc_kind,
                    calc_end=calc_end,
                ),
                folders=folders,
                default=_FIGURE_FOLDER,
                save_name=save_name,
            )
        )


if __name__ == "__main__":
    main()
