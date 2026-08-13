Command line
============

Two entry points plot or animate a case without writing any Python. Both take the same
filename-prefix ``PATHS`` convention as the Python API: the first path is the main run, any
further paths are restart runs, and the working directory is searched if none is given.

``opm-vis-pv`` (PyVista backend) supports the full option set, including multiple slices,
wells, glyphs and 3D views. ``opm-vis-mpl`` (Matplotlib backend) is the alternative tool, less
developed and covering a smaller subset.

``-i``/``-j``/``-k`` slice indices are 1-based (matching Eclipse-style indexing, e.g.
``COMPDAT``): the first cell along an axis is 1, not 0. The most common options also have short
forms - ``-K`` for ``--keyword``, ``-r`` for ``--rstep``, ``-d`` for ``--diff``, ``-c`` for
``--calculator`` - used throughout the examples below.

Examples
--------

Two slices in a 3D view, with wells (shown by default):

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -j 6 -r 60 --view 3d --wells

A single k-slice at report step 60, saved to a PNG instead of opened interactively:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save sgas_k1.png

Several slices at once in a 3D view, with wells and the grid outline for context:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -j 6 -r 60 \
       --view 3d --wells --wireframe --z-scale 15

Leave out -i/-j/-k entirely to plot the whole active grid instead of a slice - this needs
``--view 3d``, since the 2D view (the default) has no whole-grid concept to look down onto:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 60 --view 3d --wells --save sgas_grid.png

Animate a keyword over every report step as a GIF:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate --fps 4 --save sgas.gif

``--quads`` builds the slice as flat quads instead of hexahedra, touching only the cells on
that slice rather than materialising the whole 3D mesh. It's faster on large grids, whether for
a single static slice or a long ``--animate`` animation, at the cost of losing the volume a
slice would otherwise have (so thresholding/clipping aren't available on it):

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --quads --save sgas_k1.png
   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate --quads --save sgas.gif

Overlay vector glyphs from a displacement field on top of a scalar-coloured slice.
``--glyph-every-n`` thins out a dense grid by drawing only 1 arrow out of every N cells,
without changing arrow size:

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ
   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ \
       --glyph-every-n 4

Plot how much a keyword has changed since report step 0 (the default), as a percentage:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d --diff-kind relative

``--diff``/``-d`` also works with ``--animate``, differencing every animated frame against the
same fixed ``--diff-rstep``:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate -d --save sgas_diff.gif

``--calculator``/``-c`` aggregates a keyword across grid layers along the sliced dimension,
from the given ``-i``/``-j``/``-k`` index to the grid's last layer, instead of colouring by the
slice's own values - e.g. the mean pressure from layer 1 down to the base of the model. It needs
exactly one of ``-i``/``-j``/``-k``, and needs ``--keyword``:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c mean --save pressure_mean.png

``--calc-count`` limits the aggregation to that many layers starting at the given index,
instead of continuing to the grid's last layer:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -c sum --calc-count 2

``--calculator`` combines with ``--diff``: the aggregate is computed separately at ``--rstep``
and at ``--diff-rstep``, and ``--diff`` differences the two aggregates - "how much did the mean
change between these two report steps":

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c mean -d --diff-rstep 0

Plot the grid itself in a solid colour instead of colouring by a keyword, with cell outlines
drawn on top - ``--keyword``/``-K`` is neither needed nor allowed with ``--grid-only``:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --grid-only --grid-color lightgrey --show-edges \
       --view 3d --save grid.png

``--threshold`` shows only the cells whose keyword value passes a bound - e.g. a gas plume -
instead of the whole grid. It needs ``--keyword``/``-K`` and works on the whole grid only, so
it is not compatible with -i/-j/-k:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --threshold 0.4 --view 3d --save plume.png

``--clip`` cuts the whole grid open with a plane instead of showing it whole, so it is also not
compatible with -i/-j/-k. Unlike ``--threshold`` it needs no keyword, so it combines freely with
``--grid-only`` or with ``--threshold`` itself (both subsets are then shown together):

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --clip x --clip-crinkle --view 3d \
       --save clip.png

The same keyword and slice with the alternative Matplotlib backend:

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save sgas_k1.png

Option reference
-----------------

opm-vis-pv
~~~~~~~~~~

.. click:: opm_vis.cli.pvplot_cli:main
   :prog: opm-vis-pv

opm-vis-mpl
~~~~~~~~~~~

.. click:: opm_vis.cli.plot_cli:main
   :prog: opm-vis-mpl
