""" Shared fixtures locating the datasets in tests/data """
from pathlib import Path

import numpy as np
import pytest

# Test datasets live next to this file, one folder per case (SPE1CASE2 shares its folder with
# its restart run SPE1CASE2_RESTART_60). The library's "path" arguments are case path prefixes
# rather than directories - every reader looks for path + ".EXT" - so the case fixtures below
# return a prefix with no extension. The CLIs take the folder instead (-f/--folder), which the
# *_dir fixtures return.
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
        Case path prefix, as every opm_vis reader expects

    Notes
    -----
    SPE1CASE1 is a fully active, standard-oriented 10x10x3 Cartesian box grid in field units,
    with 121 report steps (0-120) and two vertical wells (PROD, INJ). It has no inactive cells,
    no NaN corner points and no faults.
    """
    return str(_DATA_DIR / "SPE1CASE1" / "SPE1CASE1")


@pytest.fixture(scope="session")
def mapaxes_case() -> str:
    """
    Filename prefix of the MAPAXES dataset

    Returns
    -------
    str
        Case path prefix, as every opm_vis reader expects

    Notes
    -----
    MAPAXES is an EGRID-only file (no INIT/UNRST/SMSPEC) whose grid carries a MAPAXES keyword:
    a translation with no rotation, from a local (x, y) origin at (0, 0) to a UTM-like origin
    at (527495.5, 6771119.0). Useful only for exercising the MAPAXES transform itself, not for
    anything that reads simulation results.
    """
    return str(_DATA_DIR / "MAPAXES" / "MAPAXES")


@pytest.fixture(scope="session")
def tpsa_lagged() -> str:
    """
    Filename prefix of the TPSA_LAGGED dataset

    Returns
    -------
    str
        Case path prefix, as every opm_vis reader expects

    Notes
    -----
    TPSA_LAGGED is a fully active, standard-oriented 5x5x5 Cartesian box grid in metric units,
    with 16 report steps (0-15) and two vertical wells (INJE, PROD) completed through every
    layer. Unlike SPE1CASE1 it carries geomechanics output - DISPX, DISPY, DISPZ among
    others - which is what makes it useful for exercising vector glyphs.
    """
    return str(_DATA_DIR / "TPSA_LAGGED" / "TPSA_LAGGED")


@pytest.fixture(scope="session")
def case1_dir() -> str:
    """
    Folder of the SPE1CASE1 dataset, as -f/--folder takes it

    Returns
    -------
    str
        Path to tests/data/SPE1CASE1
    """
    return str(_DATA_DIR / "SPE1CASE1")


@pytest.fixture(scope="session")
def case2_dir() -> str:
    """
    Folder of the SPE1CASE2 dataset together with its restart run, as -f/--folder takes it

    Returns
    -------
    str
        Path to tests/data/SPE1CASE2

    Notes
    -----
    Holds SPE1CASE2 (report steps 0-60) and SPE1CASE2_RESTART_60, which restarts it from
    report step 60 and carries on to 120.
    """
    return str(_DATA_DIR / "SPE1CASE2")


@pytest.fixture(scope="session")
def tpsa_lagged_dir() -> str:
    """
    Folder of the TPSA_LAGGED dataset, as -f/--folder takes it

    Returns
    -------
    str
        Path to tests/data/TPSA_LAGGED
    """
    return str(_DATA_DIR / "TPSA_LAGGED")


@pytest.fixture
def polygon_files(tmp_path) -> dict[str, str]:
    """
    Polygon files inside SPE1CASE1's 10000 ft square grid, 8325-8425 ft deep

    Returns
    -------
    dict[str, str]
        "outline": an x,y-only square (.npy); "line": a 2-point x,y,z line at 8350 ft (.npz,
        key "deep")
    """
    outline = tmp_path / "outline.npy"
    line = tmp_path / "line.npz"
    np.save(outline, np.array([[1000, 1000], [9000, 1000], [9000, 9000], [1000, 9000]]))
    np.savez(line, deep=np.array([[500, 500, 8350], [9500, 9500, 8350]]))
    return {"outline": str(outline), "line": str(line)}


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
