API examples
============

Most of these use :mod:`opm_vis.pvplot`, the recommended backend; the report-date, summary and
Matplotlib examples at the bottom cover the timeline helpers, the summary vectors and the
alternative backend.

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

Calculator
------------------

Pass ``calc_kind`` (one of ``opm_vis.utils.calc.CALC_KINDS``: ``"mean"`` or ``"sum"``) together
with ``slice_dim``/``slice_ind`` to aggregate a keyword across a range of grid layers along that
dimension - from ``slice_ind`` to the grid's last layer, or ``calc_count`` further layers after
it (``slice_ind`` is always included itself) - instead of colouring by the slice's own values:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)
   plotter.add_slice("k", 0)

   plotter.set_scalars("PRESSURE", rstep=60, slice_dim="k", slice_ind=0, calc_kind="mean")
   plotter.view_2d("k")
   plotter.show()

``calc_kind`` combines with ``diff_rstep`` as "diff first, then aggregate": the per-cell
difference between ``rstep`` and ``diff_rstep`` is computed first, then ``calc_kind`` aggregates
that difference across the layer range - "the mean/sum of how much each cell changed between
these two report steps", not the difference between the two report steps' own means/sums.
:meth:`~opm_vis.pvplot.GridPlotter.animate` takes the same four parameters.

``calc_kind="surface"`` is different from ``"mean"``/``"sum"``: instead of aggregating every
layer in the range into one number, it shows each lateral position's *first active* cell from
``slice_ind`` onwards, draping the slice over whichever cells are actually active rather than
leaving gaps where ``slice_ind`` itself is inactive/pinched-out. Because that changes which
cells the slice is *made of*, not just how they are coloured, ``surface`` also needs
``add_slice`` itself to be given ``surface=True`` (and the same ``calc_count``, if any) - not
only ``set_scalars``:

.. code-block:: python

   from opm_vis.pvplot import GridPlotter

   plotter = GridPlotter(["tests/data/SPE1CASE1"], z_scale=15.0)
   plotter.add_slice("k", 0, surface=True)

   plotter.set_scalars("PRESSURE", rstep=60, slice_dim="k", slice_ind=0, calc_kind="surface")
   plotter.view_2d("k")
   plotter.show()

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

Report dates and time since simulation start
---------------------------------------------

:class:`~opm_vis.utils.restart.Report` reads the date of every report step from the restart
files, and measures the time from the start of the simulation to any of them - the same data
the ``opm-vis-rdates`` command prints:

.. code-block:: python

   from opm_vis.utils.restart import Report

   report = Report(["tests/data/SPE1CASE1"])

   print(report)                      # aligned table: report step, date, days, years
   report.report_steps()              # [0, 1, ..., 120]
   report.start_date()                # datetime(2015, 1, 1)
   report.report_date(60)             # datetime(2019, 12, 31)
   report.elapsed_days(60)            # 1825
   report.elapsed_years(60)           # 4.9965...  (365.25-day years, as in the YEARS vector)

:meth:`~opm_vis.utils.restart.Report.timeline` returns the whole thing as plain dicts, ready to
feed into your own code (or a ``pandas.DataFrame``), and
:meth:`~opm_vis.utils.restart.Report.format_timeline` renders it as a table, CSV or JSON. Both
take an optional list of report steps to restrict the output to:

.. code-block:: python

   report.timeline([0, 60, 120])
   # [{'rstep': 0, 'date': datetime.datetime(2015, 1, 1, 0, 0), 'days': 0, 'years': 0.0}, ...]

   print(report.format_timeline("csv", [0, 120]))
   # rstep,date,days,years
   # 0,2015-01-01,0,0.000000
   # 120,2024-12-29,3650,9.993155

Summary vectors
----------------

:class:`~opm_vis.utils.summary.SummaryReader` reads the time series in a case's ``.SMSPEC``/
``.UNSMRY`` files, stitching a main run and any restarts into one non-overlapping series:

.. code-block:: python

   from opm_vis.utils.summary import SummaryReader

   summary = SummaryReader(["tests/data/SPE1CASE1"])

   summary.available_keywords()       # ['BGSAT:1,1,1', ..., 'FOPR', 'TIME', 'WBHP:PROD', ...]
   summary.read("FOPR")               # one value per timestep
   summary.unit("FOPR")               # 'STB/DAY', as the summary file records it
   summary.summary_dates()            # one datetime per timestep, ministeps included
   summary.elapsed_days()             # the same values as the TIME vector
   summary.elapsed_years()            # the same values as the YEARS vector

:class:`~opm_vis.plot.plot_summary.SummaryPlot` draws them - the same plot the ``opm-vis-sum``
command makes. Several vectors share one axes by default, or get one subplot each with
``subplots=True``:

.. code-block:: python

   from opm_vis.plot.plot_summary import SummaryPlot

   plot = SummaryPlot(["tests/data/SPE1CASE1"])
   plot.plot(["FOPR", "FGOR"], x_axis="years", subplots=True)
   plot.save_plot("rates.png")

``compare=True`` reads every path as a case of its own rather than as a restart chain, drawing
one line per case:

.. code-block:: python

   plot = SummaryPlot(["runs/base/CASE", "runs/high_rate/CASE"], compare=True)
   plot.plot(["FOPR"])
   plot.show()

:meth:`~opm_vis.plot.plot_summary.SummaryPlot.export_csv` renders the same data as CSV instead of
drawing it - the same export ``opm-vis-sum --export`` writes. Cases being compared do not need
matching timesteps: rows are the union of every case's own, and a case missing a value at a row
leaves that cell blank.

.. code-block:: python

   plot = SummaryPlot(["tests/data/SPE1CASE1"])
   print(plot.export_csv(["FOPR", "FGOR"]))
   # date,FOPR,FGOR
   # 2015-01-02T00:00:00,20000,1.27
   # ...

Alternative Matplotlib backend
---------------------------------

:mod:`opm_vis.plot` draws each cell as a flat quad instead of real geometry. It has no camera,
thresholding or clipping, but covers the same basic slice-and-colour workflow:

.. code-block:: python

   from opm_vis.plot.collections import SlicePoly2DCollection

   coll = SlicePoly2DCollection(["tests/data/SPE1CASE1"], "k", 0)
   coll.plot(60, "SGAS", cmap="viridis")
   coll.save_plot("sgas.png")

``plot``/``animate`` take the same ``diff_rstep``/``diff_kind`` and ``calc_kind``/``calc_count``
as the PyVista backend, e.g. ``coll.plot(60, "PRESSURE", calc_kind="mean")``.

``calc_kind="surface"`` needs the same care here as with PyVista's ``add_slice``: since it
changes which cells the slice is built from rather than just how they are coloured, it (and
``calc_count``, if any) must be given to ``SlicePoly2DCollection``/``SlicePoly3DCollection``
themselves, not to ``plot``/``animate``:

.. code-block:: python

   coll = SlicePoly2DCollection(["tests/data/SPE1CASE1"], "k", 0, surface=True)
   coll.plot(60, "PRESSURE", calc_kind="surface")
   coll.save_plot("pressure_top.png")
