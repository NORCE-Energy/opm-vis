"""
PyVista/VTK plotting backend for OPM results

This package is an alternative to the Matplotlib backend in :mod:`opm_vis.plot`. It renders
the simulation grid as real VTK geometry, which gives an interactive camera, depth-correct
3D views, thresholding and clipping, and cheap animation over report steps.

Notes
-----
PyVista is an optional dependency. Install it with ``pip install "opm-vis[pyvista]"``.
"""
try:
    import pyvista  # noqa: F401  (imported for the availability check only)
except ImportError as exc:  # pragma: no cover - depends on the install environment
    raise ImportError(
        "The opm_vis.pvplot backend requires PyVista, which is an optional dependency. "
        'Install it with: pip install "opm-vis[pyvista]"'
    ) from exc

# Imported after the availability check above, since both of these import pyvista themselves
from opm_vis.pvplot.data import CaseData  # noqa: E402
from opm_vis.pvplot.mesh import GridMesh  # noqa: E402
from opm_vis.pvplot.plotter import GridPlotter  # noqa: E402

__all__ = ["CaseData", "GridMesh", "GridPlotter"]
