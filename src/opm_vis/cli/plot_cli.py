"""opm-vis-mpl: plot a keyword on a grid slice with the alternative Matplotlib backend"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
    CALCULATOR_OPTIONS,
    CLIM_OPTION,
    CMAP_OPTION,
    COMMAND_SETTINGS,
    DIFF_OPTIONS,
    GRID_ONLY_OPTIONS,
    KEYWORD_OPTION,
    PATHS_ARGUMENT,
    RSTEP_OR_ANIMATE_OPTIONS,
    SAVE_OPTION,
    SHOW_EDGES_OPTION,
    SLICE_OPTIONS,
    add_options,
    default_output_name,
    grid_color_kwargs,
    handle_errors,
    is_static_keyword,
    parse_rstep,
    require_dynamic_keyword_error,
    resolve_animate_rsteps,
    resolve_calculator,
    resolve_diff_rstep,
    resolve_keyword,
    resolve_paths,
    resolve_slices,
)
from opm_vis.plot.collections import SlicePoly2DCollection, SlicePoly3DCollection


@click.command(**COMMAND_SETTINGS)
@PATHS_ARGUMENT
@KEYWORD_OPTION
@add_options(GRID_ONLY_OPTIONS)
@add_options(SLICE_OPTIONS)
@add_options(RSTEP_OR_ANIMATE_OPTIONS)
@add_options(DIFF_OPTIONS)
@add_options(CALCULATOR_OPTIONS)
@SAVE_OPTION
@CMAP_OPTION
@CLIM_OPTION
@click.option(
    "--view",
    type=click.Choice(["2d", "3d"]),
    default="2d",
    show_default=True,
    help="Camera preset.",
)
@click.option("--no-colorbar", is_flag=True, default=False, help="Hide the colorbar.")
@SHOW_EDGES_OPTION
@handle_errors
# pylint: disable=too-many-arguments,too-many-locals
def main(
    paths: tuple[str, ...],
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
    save: str | None,
    cmap: str,
    clim: tuple[float, float] | None,
    view: str,
    no_colorbar: bool,
    show_edges: bool,
) -> None:
    """
    Plot --keyword on one grid slice with the Matplotlib backend, or animate it over report
    steps with --animate.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs.
    Defaults to searching the working directory (./) if not given.

    This is the alternative backend, with fewer figure/animation options and less development
    effort than opm-vis-pv (PyVista); opm-vis-pv also supports multiple slices at once.

    --diff colours by the difference from --diff-rstep (default: report step 0) instead of
    --keyword's own values; --diff-kind picks plain/absolute/relative(%).

    --calculator aggregates --keyword across grid layers along the sliced dimension, from the
    given -i/-j/-k index to the grid's last layer (or --calc-count layers), instead of colouring
    by the slice's own values; it needs --keyword (so it is not compatible with --grid-only). It
    combines with --diff: the aggregate is computed separately at --rstep and at --diff-rstep,
    and --diff differences the two aggregates.

    --grid-only plots the slice in a solid colour instead - --keyword is not needed, and not
    allowed, in this mode. --animate is not supported with --grid-only.
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
    slice_dim, slice_index = slices[0]
    rstep_value = parse_rstep(rstep, animate)
    # --diff has no effect in --grid-only (there is no --keyword to difference); see the
    # matching note in pvplot_cli.py.
    resolved_diff_rstep = None if grid_only else resolve_diff_rstep(diff, diff_rstep)
    resolve_calculator(calc_kind, calc_count, slices)

    # PolyCollection/Poly3DCollection draw no visible edge by default; an explicit edgecolor is
    # what --show-edges needs, unlike PyVista's own boolean show_edges kwarg.
    edge_kwargs = {"edgecolor": "black"} if show_edges else {}

    poly_kwargs = {"cmap": cmap, **edge_kwargs}
    if clim is not None:
        poly_kwargs["clim"] = clim

    resolved_paths = resolve_paths(paths)
    if view == "3d":
        coll = SlicePoly3DCollection(resolved_paths, [(slice_dim, slice_index)])
    else:
        coll = SlicePoly2DCollection(resolved_paths, slice_dim, slice_index)

    if animate:
        steps = resolve_animate_rsteps(coll.report.report_steps(), rstep_value)
        coll.animate(
            keyword,
            rstep_list=steps,
            diff_rstep=resolved_diff_rstep,
            diff_kind=diff_kind,
            calc_kind=calc_kind,
            calc_count=calc_count,
            **poly_kwargs,
        )

        if save is None:
            coll.show()
        else:
            coll.save_gif(
                Path(save)
                if save
                else default_output_name(
                    keyword,
                    slices,
                    rsteps=steps,
                    ext="gif",
                    diff_rstep=resolved_diff_rstep,
                    diff_kind=diff_kind,
                    calc_kind=calc_kind,
                ),
                fps=fps,
            )
        return

    if grid_only:
        # Time-invariant: unlike a keyword's own values, the bare grid has no report step to
        # pick, so plot_grid()/save_grid_plot() need none either.
        coll.plot_grid(**grid_color_kwargs(grid_color), **edge_kwargs)

        if save is None:
            coll.show()
        else:
            coll.save_grid_plot(
                Path(save) if save else default_output_name("GRID", slices, ext="png")
            )
        return

    if rstep_value is None:
        probe_rstep = coll.report.report_steps()[0]
        if not is_static_keyword(coll.slice_coll[0].restart, keyword, probe_rstep):
            raise require_dynamic_keyword_error(keyword)
        actual_rstep = probe_rstep
    else:
        actual_rstep = rstep_value

    coll.plot(
        actual_rstep,
        keyword,
        colorbar=not no_colorbar,
        diff_rstep=resolved_diff_rstep,
        diff_kind=diff_kind,
        calc_kind=calc_kind,
        calc_count=calc_count,
        **poly_kwargs,
    )

    if save is None:
        coll.show()
    else:
        coll.save_plot(
            Path(save)
            if save
            else default_output_name(
                keyword,
                slices,
                rstep=actual_rstep,
                ext="png",
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
                calc_kind=calc_kind,
            )
        )


if __name__ == "__main__":
    main()
