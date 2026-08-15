opm-vis
=======

Visualization tools for `OPM <https://opm-project.org/>`_ (Open Porous Media) reservoir
simulation results — grids, restarts and summaries — from Python or the command line.

Paths passed to opm-vis are **filename prefixes, not directories**: give it
``/runs/case/SPE1CASE1`` and it finds ``SPE1CASE1.EGRID``, ``SPE1CASE1.UNRST`` and so on. The
first path is the main run; any further paths are restart runs.

Features
--------

- **Two plotting backends.** :mod:`opm_vis.pvplot` renders the grid as real VTK geometry — one
  hexahedron per active cell — with an interactive camera, correct depth sorting, thresholding,
  clipping and cheap animation. :mod:`opm_vis.plot` is an alternative, less developed
  Matplotlib backend, drawing each cell as a flat quad.
- **Grid slicing.** Cut i-, j- or k-slices through the 3D grid, alone or several at once, coloured
  by any keyword (``SGAS``, ``PRESSURE``, ...).
- **Wells.** Overlay wells with a completion on the chosen slice(s), or every well in the grid.
- **Vector glyphs.** Arrow overlays from three keyword components (e.g. a displacement vector),
  scaled by magnitude and comparable across report steps.
- **Subsets.** Threshold or clip the grid to a region of interest (PyVista backend only, since a
  flat quad has no volume to cut).
- **Whole grid or solid fill.** Plot every active cell at once, optionally in a single solid
  colour with cell outlines drawn on top, instead of colouring by a keyword.
- **Difference plots.** Colour by how much a keyword has changed since another report step -
  plain, absolute magnitude, or percent change.
- **Calculator.** Aggregate a keyword (mean, sum) across a range of grid layers along the sliced
  dimension, from the chosen slice to the grid's last layer or a limited number of layers -
  combines with difference plots.
- **Animation.** Step through report steps and export a GIF or MP4, or step interactively while
  reusing the same on-screen geometry.
- **Restart-aware.** Point at a main run plus any number of restarts and read across them as one
  time series.
- **MAPAXES-aware.** Grids with a MAPAXES transform are read in real-world coordinates, not raw
  grid-local ones.
- **Report dates.** List every report step with its date and the time since the simulation
  started, in days and years, as a table, CSV or JSON.
- **Command-line tools.** ``opm-vis-pv`` and ``opm-vis-mpl`` plot or animate a case, and
  ``opm-vis-rdates`` lists its report dates, without writing any Python.

Install
-------

.. code-block:: bash

   pip install -e .                 # Matplotlib backend only
   pip install -e ".[pyvista]"      # adds the PyVista/VTK backend

.. toctree::
   :maxdepth: 2
   :caption: Contents

   examples
   cli
   api
