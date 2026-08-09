# opm-vis
Visualization tools for OPM simulation results.

## Install

```bash
pip install -e .                 # Matplotlib backend only
pip install -e ".[pyvista]"      # adds the PyVista/VTK backend
```

## Documentation

Usage guide and API reference: https://norce-energy.github.io/opm-vis/

## CLI

Plot a keyword on a grid slice without writing any Python:

```bash
opm-vis-pv tests/data/SPE1CASE1 --keyword SGAS -k 0 --rstep 60 --save sgas_k0.png
```

## API

The same plot, driven from Python with `opm_vis.pvplot`:

```python
from opm_vis.pvplot import GridPlotter

plotter = GridPlotter(["tests/data/SPE1CASE1"])
plotter.add_slice("k", 0)
plotter.set_scalars("SGAS", rstep=60)
plotter.show()
```

## Tests

```bash
python -m pytest -q
```

Tests for `pvplot` render off-screen and skip themselves if no OpenGL context is available, so
a headless machine needs `vtk-osmesa` or `xvfb-run` for those to run.
