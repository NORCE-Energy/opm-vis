"""opm-vis-pv: plot a keyword on a grid slice with the PyVista backend"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
    CLIM_OPTION,
    CMAP_OPTION,
    COMMAND_SETTINGS,
    KEYWORD_OPTION,
    PATHS_ARGUMENT,
    RSTEP_OR_GIF_OPTIONS,
    SAVE_OPTION,
    SLICE_OPTIONS,
    add_options,
    default_output_name,
    handle_errors,
    parse_rstep,
    require_dynamic_keyword_error,
    resolve_gif_rsteps,
    resolve_paths,
    resolve_slice,
)
from opm_vis.pvplot import GridPlotter


@click.command(**COMMAND_SETTINGS)
@PATHS_ARGUMENT
@KEYWORD_OPTION
@add_options(SLICE_OPTIONS)
@add_options(RSTEP_OR_GIF_OPTIONS)
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
@click.option("--azimuth", type=float, default=30.0, show_default=True, help="--view 3d only.")
@click.option(
    "--elevation", type=float, default=45.0, show_default=True, help="--view 3d only."
)
@click.option(
    "--z-scale", type=float, default=5.0, show_default=True, help="Vertical exaggeration."
)
@click.option("--log-scale", is_flag=True, default=False, help="Map colours logarithmically.")
@click.option(
    "--wells",
    is_flag=True,
    default=False,
    help="Draw wells present at the report step(s) shown.",
)
@click.option("--wireframe", is_flag=True, default=False, help="Add the grid outline for context.")
@click.option(
    "--quads",
    is_flag=True,
    default=False,
    help="Cheaper flat-quad slice instead of hexahedra.",
)
@click.option("--window-size", type=(int, int), default=None, metavar="WIDTH HEIGHT")
@click.option("--no-colorbar", is_flag=True, default=False, help="Hide the scalar bar.")
@click.option("--no-title", is_flag=True, default=False, help="Hide the report-date title.")
@handle_errors
# pylint: disable=too-many-arguments,too-many-locals
def main(
    paths: tuple[str, ...],
    keyword: str,
    slice_i: int | None,
    slice_j: int | None,
    slice_k: int | None,
    rstep: str | None,
    gif: bool,
    fps: int,
    save: str | None,
    cmap: str,
    clim: tuple[float, float] | None,
    view: str,
    azimuth: float,
    elevation: float,
    z_scale: float,
    log_scale: bool,
    wells: bool,
    wireframe: bool,
    quads: bool,
    window_size: tuple[int, int] | None,
    no_colorbar: bool,
    no_title: bool,
) -> None:
    """
    Plot --keyword on one grid slice with the PyVista backend, or animate it over report steps
    with --gif.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs.
    Defaults to searching the working directory (./) if not given.
    """
    slice_dim, slice_index = resolve_slice(slice_i, slice_j, slice_k)
    rstep_value = parse_rstep(rstep, gif)

    with GridPlotter(
        resolve_paths(paths), off_screen=save is not None or gif, window_size=window_size,
        z_scale=z_scale,
    ) as plotter:
        plotter.add_slice(slice_dim, slice_index, quads=quads)
        if wireframe:
            plotter.add_wireframe()

        if view == "2d":
            plotter.view_2d(slice_dim)
        else:
            plotter.view_3d(azimuth=azimuth, elevation=elevation)

        if gif:
            # There is no interactive animation playback in this backend, so --gif always
            # writes a file regardless of --save.
            steps = resolve_gif_rsteps(plotter.case.report.report_steps(), rstep_value)
            output = Path(save) if save else default_output_name(
                keyword, slice_dim, slice_index, rsteps=steps, ext="gif"
            )
            plotter.animate(
                keyword,
                output,
                rsteps=steps,
                fps=fps,
                clim=clim,
                wells=wells,
                title=not no_title,
                cmap=cmap,
                log_scale=log_scale,
            )
            return

        if rstep_value is None:
            probe_rstep = plotter.case.report.report_steps()[0]
            if not plotter.case.is_static(keyword, probe_rstep):
                raise require_dynamic_keyword_error(keyword)
            actual_rstep = probe_rstep
        else:
            actual_rstep = rstep_value

        plotter.set_scalars(
            keyword,
            actual_rstep,
            clim=clim,
            cmap=cmap,
            log_scale=log_scale,
            scalar_bar=not no_colorbar,
        )
        if wells:
            plotter.add_wells(actual_rstep)
        if not no_title:
            plotter.set_title()

        if save is None:
            plotter.show()
        else:
            output = Path(save) if save else default_output_name(
                keyword, slice_dim, slice_index, rstep=actual_rstep, ext="png"
            )
            plotter.screenshot(output)


if __name__ == "__main__":
    main()
