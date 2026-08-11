"""opm-vis-pv: plot a keyword on a grid slice with the PyVista backend"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
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
    parse_rstep,
    require_dynamic_keyword_error,
    resolve_animate_rsteps,
    resolve_diff_rstep,
    resolve_keyword,
    resolve_paths,
    resolve_slices,
)
from opm_vis.pvplot import GridPlotter

# --glyph-color's default: colour arrows by vector magnitude (add_glyphs' own "scalars" default)
# rather than a flat colour. Not a real colour name, so it can't collide with one.
_GLYPH_MAGNITUDE = "glyphscale"


def _glyph_color_kwargs(glyph_color: str) -> dict:
    """
    Build add_glyphs' colour kwarg, or none at all to keep its magnitude-colouring default

    Parameters
    ----------
    glyph_color : str
        Value of --glyph-color

    Returns
    -------
    dict
        {} to leave add_glyphs colouring by magnitude, or {"color": glyph_color} for a flat
        colour, which add_glyphs treats as overriding magnitude colouring
    """
    return {} if glyph_color.lower() == _GLYPH_MAGNITUDE else {"color": glyph_color}


def _parse_threshold(raw: str | None) -> float | tuple[float, float] | None:
    """
    Parse --threshold into add_threshold's value argument

    Parameters
    ----------
    raw : str | None
        Raw value of --threshold: "LOW" or "LOW:HIGH"

    Returns
    -------
    float | tuple[float, float] | None
        None if --threshold was not given; a bare lower bound (unbounded above) for "LOW", or
        a (low, high) range for "LOW:HIGH"

    Raises
    ------
    click.UsageError
        If the value is not one or two colon-separated numbers
    """
    if raw is None:
        return None

    parts = raw.split(":")
    if len(parts) not in (1, 2):
        raise click.UsageError(f"--threshold must be LOW or LOW:HIGH, got '{raw}'.")

    try:
        values = [float(part) for part in parts]
    except ValueError as exc:
        raise click.UsageError(f"--threshold values must be numbers, got '{raw}'.") from exc

    return values[0] if len(values) == 1 else (values[0], values[1])


def _resolve_actual_rstep(plotter: GridPlotter, keyword: str, rstep_value: int | None) -> int:
    """
    Resolve the report step to read keyword at, requiring one if it changes over time

    Parameters
    ----------
    plotter : GridPlotter
        Plotter whose case to check keyword's dynamism against
    keyword : str
        OPM keyword being plotted
    rstep_value : int | None
        Parsed value of --rstep

    Returns
    -------
    int
        rstep_value itself if given, otherwise the case's first report step - only once
        confirmed that keyword does not change over time, since defaulting silently would
        otherwise hide a keyword that actually needs an explicit --rstep

    Raises
    ------
    click.UsageError
        If rstep_value is None and keyword changes over time
    """
    if rstep_value is not None:
        return rstep_value

    probe_rstep = plotter.case.report.report_steps()[0]
    if not plotter.case.is_static(keyword, probe_rstep):
        raise require_dynamic_keyword_error(keyword)
    return probe_rstep


def _wells_slices(
    all_wells: bool, slices: list[tuple[str, int]]
) -> list[tuple[str, int]] | None:
    """
    Resolve which slices, if any, add_wells/animate should restrict wells to

    Parameters
    ----------
    all_wells : bool
        Value of --all-wells; takes priority over --wells since it is the broader request
    slices : list[tuple[str, int]]
        The plot's own slices, empty when plotting the whole grid

    Returns
    -------
    list[tuple[str, int]] | None
        None to draw every well in the grid - because --all-wells was given, or because there
        are no slices to restrict to in the first place - otherwise the plot's own slices, to
        restrict wells to those with a completion on at least one of them
    """
    return None if all_wells or not slices else slices


@click.command(**COMMAND_SETTINGS)
@PATHS_ARGUMENT
@KEYWORD_OPTION
@add_options(GRID_ONLY_OPTIONS)
@add_options(SLICE_OPTIONS)
@add_options(RSTEP_OR_ANIMATE_OPTIONS)
@add_options(DIFF_OPTIONS)
@SAVE_OPTION
@CMAP_OPTION
@CLIM_OPTION
@click.option(
    "--view",
    type=click.Choice(["2d", "3d"]),
    default="2d",
    show_default=True,
    help="Camera preset. 2d only supports one slice, and needs one - it has no whole-grid "
    "view.",
)
@click.option("--azimuth", type=float, default=30.0, show_default=True, help="--view 3d only.")
@click.option(
    "--elevation", type=float, default=45.0, show_default=True, help="--view 3d only."
)
@click.option(
    "--z-scale", type=float, default=5.0, show_default=True, help="Vertical exaggeration."
)
@click.option(
    "--axes/--no-axes",
    default=True,
    show_default=True,
    help="Show a labelled bounding box with axis titles and ticks.",
)
@click.option("--log-scale", is_flag=True, default=False, help="Map colours logarithmically.")
@click.option(
    "--wells/--no-wells",
    default=True,
    show_default=True,
    help="Draw wells with a completion on at least one chosen slice.",
)
@click.option(
    "--all-wells",
    is_flag=True,
    default=False,
    help="Draw every well in the grid, not just ones on a chosen slice. Takes priority "
    "over --wells if both are given.",
)
@click.option("--wireframe", is_flag=True, default=False, help="Add the grid outline for context.")
@SHOW_EDGES_OPTION
@click.option(
    "--quads",
    is_flag=True,
    default=False,
    help="Cheaper flat-quad slice instead of hexahedra. Needs -i/-j/-k.",
)
@click.option(
    "--opacity",
    type=click.FloatRange(0.0, 1.0),
    default=1.0,
    show_default=True,
    help="Opacity of the slice(s), from 0 (transparent) to 1 (opaque).",
)
@click.option(
    "--threshold",
    default=None,
    metavar="LOW[:HIGH]",
    help="Show only cells where --keyword's value is at least LOW (or within LOW:HIGH) at "
    "--rstep, instead of the whole grid. Needs --keyword and no -i/-j/-k.",
)
@click.option(
    "--threshold-invert",
    is_flag=True,
    default=False,
    help="Keep the cells that fail --threshold instead. Only used with --threshold.",
)
@click.option("--window-size", type=(int, int), default=None, metavar="WIDTH HEIGHT")
@click.option("--no-colorbar", is_flag=True, default=False, help="Hide the scalar bar.")
@click.option("--no-title", is_flag=True, default=False, help="Hide the report-date title.")
@click.option(
    "--glyphs",
    type=(str, str, str),
    default=None,
    metavar="X Y Z",
    help=(
        "Add vector glyphs (arrows) on every chosen slice from these three keyword "
        "components, e.g. DISPX DISPY DISPZ."
    ),
)
@click.option(
    "--glyph-scale/--no-glyph-scale",
    default=True,
    show_default=True,
    help="Scale each arrow by its own vector's magnitude.",
)
@click.option(
    "--glyph-every-n",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Draw only 1 arrow out of every this many, to thin out a dense grid. Arrow size is "
    "unaffected.",
)
@click.option(
    "--glyph-factor",
    type=float,
    default=None,
    help=(
        "Factor to multiply vectors by before glyphing. Defaults to a size that draws the "
        "largest vector at about one grid cell's width, computed across every animated report "
        "step with --animate so arrow length stays comparable."
    ),
)
@click.option(
    "--glyph-color",
    default=_GLYPH_MAGNITUDE,
    show_default=True,
    help=(
        'Arrow colour, or "glyphscale" (default) to colour by vector magnitude instead of a '
        "flat colour. An explicit colour overrides magnitude colouring."
    ),
)
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
    save: str | None,
    cmap: str,
    clim: tuple[float, float] | None,
    view: str,
    azimuth: float,
    elevation: float,
    z_scale: float,
    axes: bool,
    log_scale: bool,
    wells: bool,
    all_wells: bool,
    wireframe: bool,
    show_edges: bool,
    quads: bool,
    threshold: str | None,
    threshold_invert: bool,
    opacity: float,
    window_size: tuple[int, int] | None,
    no_colorbar: bool,
    no_title: bool,
    glyphs: tuple[str, str, str] | None,
    glyph_scale: bool,
    glyph_every_n: int,
    glyph_factor: float | None,
    glyph_color: str,
) -> None:
    """
    Plot --keyword on one or more grid slices with the PyVista backend, or animate it over
    report steps with --animate.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs.
    Defaults to searching the working directory (./) if not given.

    -i/-j/-k are repeatable (e.g. -k 1 -k 6 -j 3) to plot several slices at once, all coloured
    by the same --keyword; --view 3d is required whenever more than one is given. Leaving out
    -i/-j/-k entirely plots the whole active grid instead, which also needs --view 3d.

    --glyphs overlays vector arrows on every chosen slice, from three keyword components (e.g.
    a displacement vector), alongside --keyword's scalar colouring.

    --diff colours by the difference from --diff-rstep (default: report step 0) instead of
    --keyword's own values; --diff-kind picks plain/absolute/relative(%).

    --grid-only plots the grid (or the chosen slice(s)) in a solid colour instead - --keyword
    is not needed, and not allowed, in this mode. --animate is not supported with --grid-only.

    --threshold shows only the cells passing a bound on --keyword's own value (e.g. a gas
    plume), instead of the whole grid; it needs --keyword and works on the whole grid only, so
    it is not compatible with -i/-j/-k, --grid-only or --animate.
    """
    keyword = resolve_keyword(keyword, grid_only)
    if grid_only and animate:
        raise click.UsageError("--grid-only does not support --animate yet.")

    threshold_value = _parse_threshold(threshold)
    if threshold_value is not None:
        if keyword is None:
            raise click.UsageError(
                "--threshold needs --keyword; it has no effect with --grid-only."
            )
        if animate:
            raise click.UsageError("--threshold does not support --animate yet.")

    slices = resolve_slices(slice_i, slice_j, slice_k)
    if view == "2d" and len(slices) > 1:
        raise click.UsageError(
            "--view 2d only supports one slice; pass --view 3d for multiple slices."
        )
    if view == "2d" and not slices:
        raise click.UsageError(
            "--view 2d has no whole-grid view; pass -i/-j/-k to select a slice, or --view 3d "
            "to plot the whole grid."
        )
    if quads and not slices:
        raise click.UsageError(
            "--quads needs a slice; pass -i/-j/-k, or drop --quads to plot the whole grid."
        )
    if threshold_value is not None and slices:
        raise click.UsageError(
            "--threshold works on the whole grid; drop -i/-j/-k, or drop --threshold to plot "
            "a slice."
        )
    rstep_value = parse_rstep(rstep, animate)
    # --diff has no effect in --grid-only (there is no --keyword to difference), so it is
    # forced off here rather than left to silently do nothing while still showing up in the
    # default filename.
    resolved_diff_rstep = None if grid_only else resolve_diff_rstep(diff, diff_rstep)

    grid_kwargs = grid_color_kwargs(grid_color)

    with GridPlotter(
        resolve_paths(paths), off_screen=save is not None, window_size=window_size,
        z_scale=z_scale,
    ) as plotter:
        if threshold_value is not None:
            # Resolved here (rather than at the usual, later point) since add_threshold needs
            # to know which report step to read keyword at before it can decide which cells
            # pass the threshold at all; reused below instead of being resolved twice.
            threshold_rstep = _resolve_actual_rstep(plotter, keyword, rstep_value)
            plotter.add_threshold(
                keyword,
                threshold_rstep,
                threshold_value,
                invert=threshold_invert,
                opacity=opacity,
                show_edges=show_edges,
            )
        elif slices:
            for slice_dim, slice_index in slices:
                plotter.add_slice(
                    slice_dim,
                    slice_index,
                    quads=quads,
                    opacity=opacity,
                    show_edges=show_edges,
                    **grid_kwargs,
                )
        else:
            plotter.add_grid(opacity=opacity, show_edges=show_edges, **grid_kwargs)
        if wireframe:
            plotter.add_wireframe()

        if view == "2d":
            plotter.view_2d(slices[0][0])
        else:
            plotter.view_3d(azimuth=azimuth, elevation=elevation)

        if axes:
            plotter.show_axes_grid()

        if animate:
            steps = resolve_animate_rsteps(plotter.case.report.report_steps(), rstep_value)

            if glyphs is not None:
                x_kw, y_kw, z_kw = glyphs
                # (None, None) glyphs the whole grid, matching add_glyphs/global_glyph_factor's
                # own slice_dim=None default, when no -i/-j/-k was given
                for slice_dim, slice_index in slices or [(None, None)]:
                    factor = glyph_factor
                    if factor is None:
                        # Computed across every animated step, so arrow length stays
                        # comparable from frame to frame instead of each one rescaling to its
                        # own peak. Computed per slice, so each is scaled to its own vectors.
                        factor = plotter.global_glyph_factor(
                            x_kw,
                            y_kw,
                            z_kw,
                            steps,
                            slice_dim=slice_dim,
                            slice_ind=slice_index,
                            quads=quads,
                            scale=glyph_scale,
                        )
                    plotter.add_glyphs(
                        x_kw,
                        y_kw,
                        z_kw,
                        steps[0],
                        slice_dim=slice_dim,
                        slice_ind=slice_index,
                        quads=quads,
                        scale=glyph_scale,
                        factor=factor,
                        every_n=glyph_every_n,
                        **_glyph_color_kwargs(glyph_color),
                    )

            output = None
            if save is not None:
                output = Path(save) if save else default_output_name(
                    keyword,
                    slices,
                    rsteps=steps,
                    ext="gif",
                    diff_rstep=resolved_diff_rstep,
                    diff_kind=diff_kind,
                )
            plotter.animate(
                keyword,
                output,
                rsteps=steps,
                fps=fps,
                clim=clim,
                wells=wells or all_wells,
                wells_slices=_wells_slices(all_wells, slices),
                vectors=glyphs is not None,
                title=not no_title,
                cmap=cmap,
                log_scale=log_scale,
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
            )
            return

        if grid_only:
            # A solid-colour grid is time-invariant, so no report step is strictly needed;
            # one is still resolved for --wells/the title, defaulting to the first available.
            actual_rstep = (
                rstep_value
                if rstep_value is not None
                else plotter.case.report.report_steps()[0]
            )
        elif threshold_value is not None:
            actual_rstep = threshold_rstep  # already resolved above, before add_threshold
        else:
            actual_rstep = _resolve_actual_rstep(plotter, keyword, rstep_value)

        plotter.rstep = actual_rstep
        if not grid_only:
            plotter.set_scalars(
                keyword,
                actual_rstep,
                clim=clim,
                cmap=cmap,
                log_scale=log_scale,
                scalar_bar=not no_colorbar,
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
            )
        if wells or all_wells:
            plotter.add_wells(actual_rstep, slices=_wells_slices(all_wells, slices))
        if glyphs is not None:
            x_kw, y_kw, z_kw = glyphs
            # See the animate branch above for why slices or [(None, None)]
            for slice_dim, slice_index in slices or [(None, None)]:
                plotter.add_glyphs(
                    x_kw,
                    y_kw,
                    z_kw,
                    actual_rstep,
                    slice_dim=slice_dim,
                    slice_ind=slice_index,
                    quads=quads,
                    scale=glyph_scale,
                    factor=glyph_factor,
                    every_n=glyph_every_n,
                    **_glyph_color_kwargs(glyph_color),
                )
        if not no_title:
            plotter.set_title()

        if save is None:
            plotter.show()
        else:
            keyword_tag = keyword or "GRID"
            if threshold_value is not None:
                keyword_tag += "-threshold"
            output = Path(save) if save else default_output_name(
                keyword_tag,
                slices,
                rstep=actual_rstep,
                ext="png",
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
            )
            plotter.screenshot(output)


if __name__ == "__main__":
    main()
