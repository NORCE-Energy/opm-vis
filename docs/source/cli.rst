Command line
============

Two entry points plot or animate a case without writing any Python. Both take the same
filename-prefix ``PATHS`` convention as the Python API: the first path is the main run, any
further paths are restart runs, and the working directory is searched if none is given.

``opm-vis-pv`` (PyVista backend) supports the full option set, including multiple slices,
wells, glyphs and 3D views. ``opm-vis-mpl`` (Matplotlib backend) is the alternative tool, less
developed and covering a smaller subset.

Examples
--------

A single k-slice at report step 60, saved to a PNG instead of opened interactively:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --keyword SGAS -k 0 --rstep 60 --save sgas_k0.png

Several slices at once in a 3D view, with wells and the grid outline for context:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --keyword PRESSURE -k 0 -j 5 --rstep 60 \
       --view 3d --wells --wireframe --z-scale 15

Animate a keyword over every report step as a GIF:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --keyword SGAS -k 0 --gif --fps 4 --save sgas.gif

``--quads`` builds the slice as flat quads instead of hexahedra, touching only the cells on
that slice rather than materialising the whole 3D mesh. It's faster on large grids, whether for
a single static slice or a long ``--gif`` animation, at the cost of losing the volume a slice
would otherwise have (so thresholding/clipping aren't available on it):

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --keyword SGAS -k 0 --rstep 60 --quads --save sgas_k0.png
   opm-vis-pv tests/data/SPE1CASE1 --keyword SGAS -k 0 --gif --quads --save sgas.gif

Overlay vector glyphs from a displacement field on top of a scalar-coloured slice:

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED --keyword DISPZ -k 0 --rstep 15 --glyphs DISPX DISPY DISPZ

The same keyword and slice with the alternative Matplotlib backend:

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 --keyword SGAS -k 0 --rstep 60 --save sgas_k0.png

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
