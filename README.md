# opm-vis
Visualization tools for OPM results

## Install

```bash
pip install -e .                 # Matplotlib backend only
pip install -e ".[pyvista]"      # adds the PyVista/VTK backend
```

Paths passed to opm-vis are **filename prefixes, not directories**: give it
`/runs/case/SPE1CASE1` and it finds `SPE1CASE1.EGRID`, `SPE1CASE1.UNRST` and so on. The first
path is the main run; any further paths are restart runs.

## Two plotting backends

`opm_vis.pvplot` renders the grid as real VTK geometry — one hexahedron per active cell — which
gives an interactive camera, correct depth sorting, thresholding, clipping and cheap animation.
`opm_vis.plot` is the older Matplotlib backend, which draws each cell as a flat quad. New work
should use `pvplot`.

### PyVista backend

```python
from opm_vis.pvplot import GridPlotter

plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)

plotter.add_slice("k", 0)          # map view of the top layer
plotter.add_slice("j", 5)          # a cross-section through it
plotter.add_wireframe()            # grid outline for context

plotter.set_scalars("SGAS", rstep=60, clim=plotter.global_clim("SGAS"))
plotter.add_wells(60)
plotter.view_3d()
plotter.show_axes_grid()           # after choosing the view
plotter.set_title()                # report date of the step being shown

plotter.show()
```

`z_scale` is vertical exaggeration; reservoirs are far wider than they are thick, so some is
usually needed before layering is visible.

**Swapping the field.** Geometry is added once, then `set_scalars` writes new values into what
is already on screen. Stepping through report steps costs one file read, not a rebuild:

```python
for rstep in plotter.case.report.report_steps():
    plotter.set_scalars("PRESSURE", rstep, clim=plotter.global_clim("PRESSURE"))
```

Passing `clim` keeps the colours comparable between steps. Without it each step is scaled to
its own range.

**Views.** `view_3d(azimuth=..., elevation=...)` looks down at the model from an angle.
`view_2d("i" | "j" | "k")` looks straight at a slice with parallel projection: cross-sections
come out with depth increasing downwards, and a k-slice as a map with easting right and
northing up.

**Output.**

```python
plotter.screenshot("sgas.png")
plotter.animate("SGAS", "sgas.gif", rsteps=range(0, 121, 5), fps=4)
plotter.animate("SGAS", "sgas.mp4")          # any non-.gif suffix writes a movie
```

Use `GridPlotter(..., off_screen=True)` on a machine with no display. `GridPlotter` is also a
context manager, which closes the render window on exit.

**Subsets.** Only the PyVista backend can do these, since a flat quad has no volume to cut:

```python
plotter.add_threshold("SGAS", 120, 0.4)      # just the gas plume
plotter.add_clip("x", crinkle=True)          # cut the grid open, keeping cells whole
```

Both keep their mapping back to the grid, so `set_scalars` can recolour them afterwards.

**Reading data directly.** `plotter.case` is a `CaseData`, which resolves a keyword against the
restart files first and the `.INIT` file second:

```python
from opm_vis.pvplot import CaseData

case = CaseData(["tests/data/SPE1CASE1"])
case.read("SGAS", 60)                  # one value per active cell
case.value_range("PRESSURE", [0, 60])  # taken from the data, never clamped to zero
```

`opm_vis.pvplot.GridMesh` exposes the mesh itself (`.mesh`, `.extract_slice`, `.quad_slice`) if
you would rather drive PyVista yourself.

## Tests

```bash
python -m pytest -q
```

Tests for `pvplot` render off-screen and skip themselves if no OpenGL context is available, so
a headless machine needs `vtk-osmesa` or `xvfb-run` for those to run.
