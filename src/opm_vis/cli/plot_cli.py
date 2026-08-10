"""opm-vis-mpl: plot a keyword on a grid slice with the alternative Matplotlib backend"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
    CLIM_OPTION,
    CMAP_OPTION,
    COMMAND_SETTINGS,
    DIFF_OPTIONS,
    KEYWORD_OPTION,
    PATHS_ARGUMENT,
    RSTEP_OR_GIF_OPTIONS,
    SAVE_OPTION,
    SLICE_OPTIONS,
    add_options,
    default_output_name,
    handle_errors,
    is_static_keyword,
    parse_rstep,
    require_dynamic_keyword_error,
    resolve_diff_rstep,
    resolve_gif_rsteps,
    resolve_paths,
    resolve_slices,
)
from opm_vis.plot.collections import SlicePoly2DCollection, SlicePoly3DCollection


@click.command(**COMMAND_SETTINGS)
@PATHS_ARGUMENT
@KEYWORD_OPTION
@add_options(SLICE_OPTIONS)
@add_options(RSTEP_OR_GIF_OPTIONS)
@add_options(DIFF_OPTIONS)
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
@handle_errors
# pylint: disable=too-many-arguments,too-many-locals
def main(
    paths: tuple[str, ...],
    keyword: str,
    slice_i: tuple[int, ...],
    slice_j: tuple[int, ...],
    slice_k: tuple[int, ...],
    rstep: str | None,
    gif: bool,
    fps: int,
    diff: bool,
    diff_rstep: int,
    diff_kind: str,
    save: str | None,
    cmap: str,
    clim: tuple[float, float] | None,
    view: str,
    no_colorbar: bool,
) -> None:
    """
    Plot --keyword on one grid slice with the Matplotlib backend, or animate it over report
    steps with --gif.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs.
    Defaults to searching the working directory (./) if not given.

    This is the alternative backend, with fewer figure/gif options and less development effort
    than opm-vis-pv (PyVista); opm-vis-pv also supports multiple slices at once.

    --diff colours by the difference from --diff-rstep (default: report step 0) instead of
    --keyword's own values; --diff-kind picks plain/absolute/relative(%).
    """
    slices = resolve_slices(slice_i, slice_j, slice_k)
    if len(slices) > 1:
        raise click.UsageError(
            "opm-vis-mpl only supports one slice; pass -i/-j/-k once. Use opm-vis-pv for "
            "multiple slices."
        )
    slice_dim, slice_index = slices[0]
    rstep_value = parse_rstep(rstep, gif)
    resolved_diff_rstep = resolve_diff_rstep(diff, diff_rstep)

    poly_kwargs = {"cmap": cmap}
    if clim is not None:
        poly_kwargs["clim"] = clim

    resolved_paths = resolve_paths(paths)
    if view == "3d":
        coll = SlicePoly3DCollection(resolved_paths, [(slice_dim, slice_index)])
    else:
        coll = SlicePoly2DCollection(resolved_paths, slice_dim, slice_index)

    if gif:
        steps = resolve_gif_rsteps(coll.report.report_steps(), rstep_value)
        coll.gif(
            keyword,
            rstep_list=steps,
            diff_rstep=resolved_diff_rstep,
            diff_kind=diff_kind,
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
                ),
                fps=fps,
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
            )
        )


if __name__ == "__main__":
    main()
