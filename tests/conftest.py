""" Shared fixtures locating the datasets in tests/data """
from pathlib import Path

import pytest

# Test datasets live next to this file. Note that "path" arguments throughout opm_vis are
# filename prefixes rather than directories - every reader does glob(path + "*.EXT") - so the
# case fixtures below deliberately return a prefix with no extension.
_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """
    Directory holding the test datasets

    Returns
    -------
    Path
        Path to tests/data
    """
    return _DATA_DIR


@pytest.fixture(scope="session")
def case1() -> str:
    """
    Filename prefix of the SPE1CASE1 dataset

    Returns
    -------
    str
        Path prefix, as the glob() in every opm_vis reader expects

    Notes
    -----
    SPE1CASE1 is a fully active, standard-oriented 10x10x3 Cartesian box grid in field units,
    with 121 report steps (0-120) and two vertical wells (PROD, INJ). It has no inactive cells,
    no NaN corner points and no faults.
    """
    return str(_DATA_DIR / "SPE1CASE1")


@pytest.fixture(scope="session")
def mapaxes_case() -> str:
    """
    Filename prefix of the MAPAXES dataset

    Returns
    -------
    str
        Path prefix, as the glob() in every opm_vis reader expects

    Notes
    -----
    MAPAXES is an EGRID-only file (no INIT/UNRST/SMSPEC) whose grid carries a MAPAXES keyword:
    a translation with no rotation, from a local (x, y) origin at (0, 0) to a UTM-like origin
    at (527495.5, 6771119.0). Useful only for exercising the MAPAXES transform itself, not for
    anything that reads simulation results.
    """
    return str(_DATA_DIR / "MAPAXES")


@pytest.fixture(scope="session")
def tpsa_lagged() -> str:
    """
    Filename prefix of the TPSA_LAGGED dataset

    Returns
    -------
    str
        Path prefix, as the glob() in every opm_vis reader expects

    Notes
    -----
    TPSA_LAGGED is a fully active, standard-oriented 5x5x5 Cartesian box grid in metric units,
    with 16 report steps (0-15) and two vertical wells (INJE, PROD) completed through every
    layer. Unlike SPE1CASE1 it carries geomechanics output - DISPX, DISPY, DISPZ among
    others - which is what makes it useful for exercising vector glyphs.
    """
    return str(_DATA_DIR / "TPSA_LAGGED")


@pytest.fixture(scope="session")
def offscreen():
    """
    Force PyVista into off-screen rendering, skipping the test if it cannot render

    Returns
    -------
    module
        The pyvista module, already switched to off-screen mode

    Notes
    -----
    VTK needs an OpenGL context, which a bare CI container does not have unless it runs under
    xvfb or installs vtk-osmesa. Probing once with a tiny render and skipping keeps the
    data-layer tests runnable everywhere instead of erroring out on import.
    """
    pyvista = pytest.importorskip("pyvista")
    pyvista.OFF_SCREEN = True

    try:
        plotter = pyvista.Plotter(off_screen=True, window_size=(64, 48))
        plotter.add_mesh(pyvista.Cube())
        plotter.screenshot(return_img=True)
        plotter.close()
    # pylint: disable=broad-exception-caught
    # VTK reports a missing GL context in several unrelated ways, none of them a subclass we
    # can usefully name here.
    except Exception as exc:  # pragma: no cover - depends on the render environment
        pytest.skip(f"Off-screen VTK rendering is unavailable: {exc}")

    return pyvista
