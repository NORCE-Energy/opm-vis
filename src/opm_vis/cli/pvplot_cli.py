"""opm-vis-pv: plot a keyword on a grid slice with the PyVista backend"""
from __future__ import annotations

from typing import Any, Literal

import click
from click.core import ParameterSource

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
    default_output_name,
    grid_color_kwargs,
    handle_errors,
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
from opm_vis.pvplot import GridPlotter
from opm_vis.pvplot.camera import Camera
from opm_vis.utils.calc import resolve_calc_range
from opm_vis.utils.grid import slice_dimension_size

# Default --save-folder names, inside the first -f/--folder
_FIGURE_FOLDER = "pv-figs"
_ANIMATION_FOLDER = "pv-gifs"

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


class _OneOrThreeOption(click.Option):
    """
    Option taking either one value or three, e.g. --glyphs DISP or --glyphs DISPX DISPY DISPZ

    Click's options take a fixed number of values, so this greedily takes up to two more
    values after the first one, stopping at the next option. The raw tuple of one to three
    values is passed on as is, for the option's callback to validate and expand.
    """

    def add_to_parser(self, parser, ctx: click.Context) -> None:
        super().add_to_parser(parser, ctx)
        # pylint: disable=protected-access
        for opt in self.opts:
            opts = parser._long_opt if opt in parser._long_opt else parser._short_opt
            parser_opt = opts[opt]
            parser_opt.process = self._make_greedy(parser_opt.process)

    @staticmethod
    def _make_greedy(process):
        def greedy_process(value, state) -> None:
            values = [value]
            while len(values) < 3 and state.rargs and not state.rargs[0].startswith("-"):
                values.append(state.rargs.pop(0))
            process(tuple(values), state)

        return greedy_process


def _expand_glyphs(
    _ctx: click.Context, _param: click.Parameter, value: tuple[str, ...] | None
) -> tuple[str, str, str] | None:
    """
    Expand --glyphs into its three vector-component keywords

    Parameters
    ----------
    value : tuple[str, ...] | None
        One to three raw values of --glyphs, or None if it was not given

    Returns
    -------
    tuple[str, str, str] | None
        The three keywords as given, or BASE expanded to BASEX BASEY BASEZ if only
        one was given; None if --glyphs was not given

    Raises
    ------
    click.BadParameter
        If two values were given
    """
    if value is None:
        return None
    if len(value) == 1:
        base = value[0]
        return (f"{base}X", f"{base}Y", f"{base}Z")
    if len(value) == 3:
        return value
    raise click.BadParameter(
        f"takes one keyword base (e.g. DISP) or three keywords (e.g. DISPX DISPY DISPZ), "
        f"got {' '.join(value)}."
    )


def _parse_camera(camera_text: str | None) -> Camera | None:
    """
    Parse --camera, rejecting it together with --azimuth/--elevation

    Parameters
    ----------
    camera_text : str | None
        Value of --camera

    Returns
    -------
    Camera | None
        None if --camera was not given

    Raises
    ------
    click.UsageError
        If the value is not a valid camera, or --azimuth/--elevation was also given
    """
    if camera_text is None:
        return None

    ctx = click.get_current_context()
    given = [
        f"--{name}"
        for name in ("azimuth", "elevation")
        if ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE
    ]
    if given:
        raise click.UsageError(
            f"--camera places the camera exactly; drop {' and '.join(given)}, or drop --camera."
        )

    try:
        return Camera.from_text(camera_text)
    except ValueError as exc:
        raise click.UsageError(f"--camera: {exc}") from exc


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


def _resolve_actual_rstep(
    plotter: GridPlotter, keyword: str, rstep_value: int | None
) -> int | None:
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
    int | None
        See resolve_keyword_rstep: None only for an .INIT keyword in a case with no restart
        files
    """
    case = plotter.case
    return resolve_keyword_rstep(
        keyword, rstep_value, case.report.report_steps(), case.restart, case.static
    )


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
    help="Camera preset. 2d only supports one slice, and needs one - it has no whole-grid "
    "view.",
)
@click.option("--azimuth", type=float, default=30.0, show_default=True, help="--view 3d only.")
@click.option(
    "--elevation", type=float, default=45.0, show_default=True, help="--view 3d only."
)
@click.option(
    "--camera",
    "camera_text",
    default=None,
    metavar="X,Y,Z/FX,FY,FZ/UX,UY,UZ[/SCALE]",
    help="Place the camera exactly: its position, the point it looks at, its view-up "
    "direction and, for --view 2d, its zoom. The interactive window shows these values in its "
    "lower left corner and prints them on closing, ready to paste. Reproduces the same view "
    "only with the same --z-scale and --window-size. Replaces --azimuth/--elevation.",
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
@click.option(
    "--fault",
    "fault_path",
    default=None,
    metavar="PATH",
    help="Path to a .DATA file or an include file with FAULTS keyword(s); draws the fault "
    "surface(s) on top of the plot.",
)
@click.option(
    "--fault-name",
    "fault_names",
    multiple=True,
    metavar="NAME",
    help="Only draw this fault (repeatable). Only used with --fault. Without it, every fault "
    "on the chosen -i/-j/-k slice(s) is drawn, or every fault in the file if no slice was "
    "given.",
)
@FAULT_LABELS_OPTION
@WELL_NAME_OPTION
@add_options(POLYGON_OPTIONS)
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
@click.option(
    "--clip",
    type=click.Choice(["x", "-x", "y", "-y", "z", "-z"]),
    default=None,
    metavar="AXIS",
    help="Cut the whole grid with a plane normal to this axis, instead of showing it whole. "
    "Needs no -i/-j/-k.",
)
@click.option(
    "--clip-origin",
    type=(float, float, float),
    default=None,
    metavar="X Y Z",
    help="Point the --clip plane passes through, by default the centre of the grid. Only "
    "used with --clip.",
)
@click.option(
    "--clip-invert/--no-clip-invert",
    default=True,
    show_default=True,
    help="Keep the side --clip's normal points away from. Only used with --clip.",
)
@click.option(
    "--clip-crinkle",
    is_flag=True,
    default=False,
    help="Keep whole cells at the --clip boundary instead of cutting through them. Only used "
    "with --clip.",
)
@click.option("--window-size", type=(int, int), default=None, metavar="WIDTH HEIGHT")
@click.option("--no-colorbar", is_flag=True, default=False, help="Hide the scalar bar.")
@COLORBAR_LABEL_OPTION
@click.option("--no-title", is_flag=True, default=False, help="Hide the report-date title.")
@click.option(
    "--glyphs",
    cls=_OneOrThreeOption,
    type=click.UNPROCESSED,
    callback=_expand_glyphs,
    default=None,
    metavar="X Y Z | BASE",
    help=(
        "Add vector glyphs (arrows) on every chosen slice from these three keyword "
        "components, e.g. DISPX DISPY DISPZ, or one BASE expanded to BASEX BASEY "
        "BASEZ, e.g. DISP."
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
@FONT_SCALE_OPTION
@handle_errors
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
    azimuth: float,
    elevation: float,
    camera_text: str | None,
    z_scale: float,
    axes: bool,
    log_scale: bool,
    wells: bool,
    all_wells: bool,
    wireframe: bool,
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
    quads: bool,
    threshold: str | None,
    threshold_invert: bool,
    clip: Literal["x", "-x", "y", "-y", "z", "-z"] | None,
    clip_origin: tuple[float, float, float] | None,
    clip_invert: bool,
    clip_crinkle: bool,
    opacity: float,
    window_size: tuple[int, int] | None,
    no_colorbar: bool,
    colorbar_label: str | None,
    no_title: bool,
    glyphs: tuple[str, str, str] | None,
    glyph_scale: bool,
    glyph_every_n: int,
    glyph_factor: float | None,
    glyph_color: str,
    font_scale: float,
) -> None:
    """
    Plot --keyword on one or more grid slices with the PyVista backend, or animate it over
    report steps with --animate.

    The case is found in -f/--folder, by default the current folder. Several cases found
    there are read as one run: the main run followed by its restarts.

    See the documentation for the full option reference with examples.
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
    if clip is not None and slices:
        raise click.UsageError(
            "--clip works on the whole grid; drop -i/-j/-k, or drop --clip to plot a slice."
        )
    if calc_kind is not None and grid_only:
        raise click.UsageError(
            "--calculator needs --keyword; it has no effect with --grid-only."
        )
    if fault_names and fault_path is None:
        raise click.UsageError("--fault-name needs --fault.")
    if well_names and not (wells or all_wells):
        raise click.UsageError("--well-name has no wells to select with --no-wells.")
    check_colorbar_label(colorbar_label, no_colorbar=no_colorbar, grid_only=grid_only)
    camera = _parse_camera(camera_text)
    polygon_labels_value = polygon_labels_arg(
        polygon_paths, polygon_labels, show_polygon_labels
    )
    rstep_value = parse_rstep(rstep, animate)
    # --diff has no effect in --grid-only (there is no --keyword to difference), so it is
    # forced off here rather than left to silently do nothing while still showing up in the
    # default filename.
    resolved_diff_rstep = None if grid_only else resolve_diff_rstep(diff, diff_rstep)
    calc_slice = resolve_calculator(calc_kind, calc_count, slices)
    calc_slice_dim, calc_slice_ind = calc_slice if calc_slice is not None else (None, None)

    grid_kwargs = grid_color_kwargs(grid_color)

    with GridPlotter(
        resolve_paths(folders),
        off_screen=wants_save(save, save_folder, save_name),
        window_size=window_size,
        z_scale=z_scale,
        font_scale=font_scale,
    ) as plotter:
        calc_end = None
        if calc_slice is not None:
            assert calc_slice_dim is not None and calc_slice_ind is not None
            n_slice = slice_dimension_size(plotter.grid.egrid, calc_slice_dim)
            _, calc_end = resolve_calc_range(calc_slice_ind, n_slice, calc_count)

        # Set below, only reachable when threshold_value is not None (--threshold and slices
        # are mutually exclusive, checked above, so that always takes the "else" branch below)
        threshold_rstep: int | None = None

        if slices:
            for slice_dim, slice_index in slices:
                # --calculator requires exactly one of -i/-j/-k (see resolve_calculator), so at
                # most one iteration here ever matches calc_slice.
                is_calc_slice = calc_slice is not None and (slice_dim, slice_index) == calc_slice
                plotter.add_slice(
                    slice_dim,
                    slice_index,
                    quads=quads,
                    surface=is_calc_slice and calc_kind == "surface",
                    calc_count=calc_count if is_calc_slice else None,
                    opacity=opacity,
                    show_edges=show_edges,
                    **grid_kwargs,
                )
        else:
            # --threshold and --clip each add their own subset of the whole grid instead of
            # it, and can be combined (both subsets shown together); the whole grid itself is
            # only added when neither was asked for.
            added_subset = False

            if threshold_value is not None:
                # keyword is required whenever --threshold is given (checked above), and
                # --animate is rejected together with --threshold (checked above), so --rstep
                # was parsed with animate=False: a bare int or None, never a range
                assert keyword is not None
                assert rstep_value is None or isinstance(rstep_value, int)
                # Resolved here (rather than at the usual, later point) since add_threshold
                # needs to know which report step to read keyword at before it can decide
                # which cells pass the threshold at all; reused below instead of being
                # resolved twice.
                threshold_rstep = _resolve_actual_rstep(plotter, keyword, rstep_value)
                plotter.add_threshold(
                    keyword,
                    threshold_rstep,
                    threshold_value,
                    invert=threshold_invert,
                    opacity=opacity,
                    show_edges=show_edges,
                )
                added_subset = True

            if clip is not None:
                plotter.add_clip(
                    clip,
                    origin=clip_origin,
                    invert=clip_invert,
                    crinkle=clip_crinkle,
                    opacity=opacity,
                    show_edges=show_edges,
                    **grid_kwargs,
                )
                added_subset = True

            if not added_subset:
                plotter.add_grid(opacity=opacity, show_edges=show_edges, **grid_kwargs)
        if wireframe:
            plotter.add_wireframe()

        if fault_path is not None:
            plotter.add_faults(
                fault_path,
                names=list(fault_names) or None,
                slices=slices or None,
                labels=fault_labels,
            )
        if polygon_paths:
            # A flat x,y outline at the top of the grid is only seen edge-on in a 2D view of an
            # i- or j-slice, so it is left out there
            line_kwargs: dict[str, Any] = {}
            if polygon_linewidth is not None:
                line_kwargs["line_width"] = polygon_linewidth
            plotter.add_polygons(
                list(polygon_paths),
                outlines=not (view == "2d" and slices[0][0] != "k"),
                labels=polygon_labels_value,
                color=polygon_color,
                **line_kwargs,
            )

        if view == "2d":
            plotter.view_2d(slices[0][0])
        else:
            plotter.view_3d(azimuth=azimuth, elevation=elevation)
        if camera is not None:
            plotter.set_camera(camera)

        if axes:
            plotter.show_axes_grid()

        if animate:
            # grid_only+animate already raised above, so resolve_keyword guarantees a keyword
            # here, and --rstep was parsed with animate=True (see parse_rstep): a range or
            # None, never a bare int
            assert keyword is not None
            assert rstep_value is None or isinstance(rstep_value, tuple)
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
            if wants_save(save, save_folder, save_name):
                output = save_path(
                    save_folder,
                    default_output_name(
                        f"{keyword}-clip" if clip is not None else keyword,
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
                )
            plotter.animate(
                keyword,
                output,
                rsteps=steps,
                fps=fps,
                clim=clim,
                wells=wells or all_wells,
                wells_slices=_wells_slices(all_wells, slices),
                wells_names=list(well_names) or None,
                vectors=glyphs is not None,
                title=not no_title,
                cmap=cmap,
                log_scale=log_scale,
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
                slice_dim=calc_slice_dim,
                slice_ind=calc_slice_ind,
                calc_kind=calc_kind,
                calc_count=calc_count,
                scalar_bar_title=colorbar_label,
            )
            return

        # Reached only when not animate (the branch above returns), so --rstep was parsed
        # with animate=False (see parse_rstep): a bare int or None, never a range
        assert rstep_value is None or isinstance(rstep_value, int)

        actual_rstep: int | None
        if grid_only:
            # A solid-colour grid is time-invariant, so no report step is strictly needed;
            # one is still resolved for --wells/the title, defaulting to the first available.
            # A dry run with no restart files has none at all, and then both are skipped.
            report_steps = plotter.case.report.report_steps()
            if rstep_value is not None:
                actual_rstep = rstep_value
            else:
                actual_rstep = report_steps[0] if report_steps else None
        elif threshold_value is not None:
            # Resolved above, before add_threshold; None for an .INIT keyword in a case with no
            # restart files
            actual_rstep = threshold_rstep
        else:
            # Not grid_only, so resolve_keyword guarantees a keyword here
            assert keyword is not None
            actual_rstep = _resolve_actual_rstep(plotter, keyword, rstep_value)

        plotter.rstep = actual_rstep
        if not grid_only:
            # keyword is required unless grid_only (checked by resolve_keyword). actual_rstep
            # is None for a case with no restart files, which is fine for an .INIT keyword
            assert keyword is not None
            if actual_rstep is None and resolved_diff_rstep is not None:
                raise click.UsageError(
                    "--diff needs restart data, but this case has no report steps."
                )
            plotter.set_scalars(
                keyword,
                actual_rstep,
                clim=clim,
                cmap=cmap,
                log_scale=log_scale,
                scalar_bar=not no_colorbar,
                scalar_bar_title=colorbar_label,
                diff_rstep=resolved_diff_rstep,
                diff_kind=diff_kind,
                slice_dim=calc_slice_dim,
                slice_ind=calc_slice_ind,
                calc_kind=calc_kind,
                calc_count=calc_count,
            )
        if (wells or all_wells) and actual_rstep is not None:
            plotter.add_wells(
                actual_rstep,
                slices=_wells_slices(all_wells, slices),
                names=list(well_names) or None,
            )
        if glyphs is not None:
            if actual_rstep is None:
                raise click.UsageError(
                    "--glyphs needs restart data, but this case has no report steps."
                )
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
        if not no_title and actual_rstep is not None:
            plotter.set_title()

        if not wants_save(save, save_folder, save_name):
            shown = plotter.show(camera_overlay=True)
            if shown is not None:
                click.echo(f"View: {shown.cli_options()}")
        else:
            keyword_tag = keyword or "GRID"
            if threshold_value is not None:
                keyword_tag += "-threshold"
            if clip is not None:
                keyword_tag += "-clip"
            output = save_path(
                save_folder,
                default_output_name(
                    keyword_tag,
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
            plotter.screenshot(output)


if __name__ == "__main__":
    main()
