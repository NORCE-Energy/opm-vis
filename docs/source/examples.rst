API examples
============

All of these use :mod:`opm_vis.pvplot`, the recommended backend; a Matplotlib example is at the
bottom for the alternative backend.

Basic slice with wells
-------------------------

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)

   plotter.add_slice("k", 0)          # map view of the top layer
   plotter.add_slice("j", 5)          # a cross-section through it
   plotter.add_wireframe()            # grid outline for context

   plotter.set_scalars("SGAS", rstep=60, clim=plotter.global_clim("SGAS"))
   plotter.add_wells(60)
   plotter.view_3d()
   plotter.show()

Whole grid instead of a slice
------------------------------

:meth:`~opm_vis.pvplot.GridPlotter.add_grid` adds every active cell instead of one slice.
Everything else - colouring, wells, glyphs - works the same as on a slice:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)
   plotter.add_grid()

   plotter.set_scalars("SGAS", rstep=60)
   plotter.add_wells(60)
   plotter.view_3d()
   plotter.show()

Difference plots
------------------

Pass ``diff_rstep`` (and optionally ``diff_kind``) to colour by how much a keyword has changed
since another report step, instead of its own values. ``diff_kind`` is one of ``"plain"``
(the default, current minus reference), ``"absolute"`` (the plain difference's magnitude), or
``"relative"`` (percent change from the reference):

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)
   plotter.add_slice("k", 0)

   plotter.set_scalars("PRESSURE", rstep=60, diff_rstep=0, diff_kind="relative")
   plotter.view_2d("k")
   plotter.show()

:meth:`~opm_vis.pvplot.GridPlotter.animate` takes the same ``diff_rstep``/``diff_kind``, always
differencing every animated frame against the same fixed reference step.

Vector glyphs
--------------

:meth:`~opm_vis.pvplot.GridPlotter.add_glyphs` overlays arrows from three keyword components
(e.g. a displacement vector) on top of a slice's own scalar colouring. ``every_n`` thins out a
dense grid by drawing only 1 arrow out of every N cells, without changing arrow size:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/TPSA_LAGGED"])
   plotter.add_slice("k", 0)
   plotter.add_glyphs("DISPX", "DISPY", "DISPZ", 15, slice_dim="k", slice_ind=0, every_n=4)

   plotter.set_scalars("DISPZ", rstep=15)
   plotter.view_2d("k")
   plotter.show()

Stepping through report steps
------------------------------

Geometry is added once with :meth:`~opm_vis.pvplot.GridPlotter.add_slice`; from then on,
:meth:`~opm_vis.pvplot.GridPlotter.set_scalars` just writes new values into what is already on
screen, so stepping through report steps costs one file read, not a rebuild:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)
   plotter.add_slice("k", 0)

   clim = plotter.global_clim("PRESSURE")
   for rstep in plotter.case.report.report_steps():
       plotter.set_scalars("PRESSURE", rstep, clim=clim)

Passing ``clim`` keeps the colours comparable between steps; without it each step is scaled to
its own range.

Thresholding and clipping
--------------------------

Only the PyVista backend can do these, since a flat quad has no volume to cut. Both keep their
mapping back to the grid, so :meth:`~opm_vis.pvplot.GridPlotter.set_scalars` can recolour them
afterwards:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"])
   plotter.add_threshold("SGAS", 120, 0.4)      # just the gas plume, at report step 120
   plotter.add_clip("x", crinkle=True)          # cut the grid open, keeping cells whole

   plotter.set_scalars("SGAS", rstep=120)
   plotter.view_3d()
   plotter.show()

Faster slices with quads
---------------------------

``add_slice(..., quads=True)`` builds the slice as flat quads instead of hexahedra, touching
only the cells on that slice rather than materialising the whole 3D mesh. It's faster on large
grids, at the cost of losing the volume a slice would otherwise have — no thresholding or
clipping on it:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], off_screen=True)
   plotter.add_slice("k", 0, quads=True)

   plotter.set_scalars("SGAS", rstep=60)
   plotter.view_2d("k")
   plotter.screenshot("sgas.png")

Saving a screenshot or animation
----------------------------------

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], off_screen=True)
   plotter.add_slice("k", 0)

   plotter.set_scalars("SGAS", rstep=60)
   plotter.view_2d("k")
   plotter.screenshot("sgas.png")

   plotter.animate("SGAS", "sgas.gif", rsteps=range(0, 121, 5), fps=4)

Use ``off_screen=True`` on a machine with no display, as above; ``GridPlotter`` is also a
context manager (``with GridPlotter(...) as plotter:``), which closes the render window on
exit.

Reading data directly
------------------------

``plotter.case`` is a :class:`~opm_vis.pvplot.CaseData`, which resolves a keyword against the
restart files first and the ``.INIT`` file second. It can also be used on its own, without a
plotter, e.g. to pull values into NumPy for your own analysis:

.. code-block:: python

   from opm_vis.pvplot import CaseData

   case = CaseData(["tests/data/SPE1CASE1"])
   sgas = case.read("SGAS", 60)                     # one value per active cell
   prange = case.value_range("PRESSURE", [0, 60])   # taken from the data, never clamped to zero

Alternative Matplotlib backend
---------------------------------

:mod:`opm_vis.plot` draws each cell as a flat quad instead of real geometry. It has no camera,
thresholding or clipping, but covers the same basic slice-and-colour workflow:

.. code-block:: python

   from opm_vis.plot.collections import SlicePoly2DCollection

   coll = SlicePoly2DCollection(["tests/data/SPE1CASE1"], "k", 0)
   coll.plot(60, "SGAS", cmap="viridis")
   coll.save_plot("sgas.png")
