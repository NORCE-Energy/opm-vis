""" Plain-text unit labels and axis titles for VTK text rendering """
from __future__ import annotations

from opm_vis.utils.diff import diff_label
from opm_vis.utils.units import Label

# opm_vis.utils.units writes its unit labels as Matplotlib mathtext. VTK would render the
# delimiters literally, so the two patterns that occur are mapped to their Unicode
# equivalents. Unicode is preferred over VTK's own mathtext support because it also survives
# image export and font substitution.
_MATHTEXT = {"$^3$": "³", r"$^\circ$": "°"}

# Label returns this literal string when it does not recognise the unit convention itself
_UNKNOWN = "UNKNOWN"

# Axis names, in x, y, z order. z is depth, since the meshes keep OPM's depth-positive-down
# coordinates rather than flipping them to elevation.
_AXIS_NAMES = ("E(x)", "N(y)", "Depth")


def plain_text(label: str) -> str:
    """
    Replace Matplotlib mathtext in a unit label with plain Unicode

    Parameters
    ----------
    label : str
        Unit label, possibly containing mathtext such as ``kg/m$^3$``

    Returns
    -------
    str
        Label with no mathtext delimiters left in it

    Notes
    -----
    Any mathtext without a tabulated Unicode equivalent keeps its content but loses its ``$``
    delimiters, which stays readable instead of showing the raw markup.
    """
    for mathtext, replacement in _MATHTEXT.items():
        label = label.replace(mathtext, replacement)

    return label.replace("$", "")


def unit(label: Label, keyword: str) -> str:
    """
    Plain-text unit for one keyword

    Parameters
    ----------
    label : Label
        Unit label lookup for the case's unit convention
    keyword : str
        OPM keyword

    Returns
    -------
    str
        Unit, or an empty string if it is not tabulated

    Notes
    -----
    Label raises KeyError for mnemonics missing from its tables, and returns "UNKNOWN" when
    the unit convention itself is unrecognised. Neither is worth failing a plot over, and
    neither is more useful on an axis than no unit at all, so both give an empty string.
    """
    try:
        plain = plain_text(label(keyword))
    except KeyError:
        return ""

    return "" if plain == _UNKNOWN else plain


def scalar_bar_title(label: Label, keyword: str, *, diff_kind: str | None = None) -> str:
    """
    Title for the scalar bar of one keyword

    Parameters
    ----------
    label : Label
        Unit label lookup for the case's unit convention
    keyword : str
        OPM keyword
    diff_kind : str | None, optional
        One of opm_vis.utils.diff.DIFF_KINDS, by default None. When given, the keyword is
        shown as a difference (see opm_vis.utils.diff.diff_label) rather than its own value,
        and "relative" is always labelled in percent regardless of the keyword's own unit.

    Returns
    -------
    str
        Keyword (or its diff label) followed by its unit in brackets, e.g.
        ``PRESSURE [barsa]`` or ``ΔPRESSURE [barsa]``, or without brackets when no unit
        applies
    """
    name = keyword if diff_kind is None else diff_label(keyword, diff_kind)
    if diff_kind == "relative":
        return f"{name} [%]"

    unit_label = unit(label, keyword)
    return f"{name} [{unit_label}]" if unit_label else name


def axis_titles(label: Label) -> tuple[str, str, str]:
    """
    Titles for the x-, y- and z-axis

    Parameters
    ----------
    label : Label
        Unit label lookup for the case's unit convention

    Returns
    -------
    tuple[str, str, str]
        Easting, northing and depth titles, with the length unit in brackets

    Notes
    -----
    The length unit comes from the DEPTH entry of the unit table, so a field-units case is
    labelled in feet. opm_vis.plot hard-codes metres regardless of the unit convention.
    """
    length = unit(label, "DEPTH")
    if not length:
        return _AXIS_NAMES

    return (
        f"{_AXIS_NAMES[0]} [{length}]",
        f"{_AXIS_NAMES[1]} [{length}]",
        f"{_AXIS_NAMES[2]} [{length}]",
    )
