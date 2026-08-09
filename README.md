# opm-vis
Visualization tools for OPM simulation results.

## Install

```bash
pip install -e .                 # Matplotlib backend only
pip install -e ".[pyvista]"      # adds the PyVista/VTK backend
```

## Documentation

Usage guide and API reference coming soon!

## Tests

```bash
python -m pytest -q
```

Tests for `pvplot` render off-screen and skip themselves if no OpenGL context is available, so
a headless machine needs `vtk-osmesa` or `xvfb-run` for those to run.
