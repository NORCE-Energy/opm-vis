Slicing
========

``-i``, ``--i-index``
-----------------------

Slice on the i dimension at this 1-based index. Repeatable to plot several i-slices at once
(``--view 3d`` is then required).

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -i 5 -r 60 --view 3d

``-j``, ``--j-index``
-----------------------

Slice on the j dimension at this 1-based index. Repeatable.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -j 6 -r 60 --view 3d

``-k``, ``--k-index``
-----------------------

Slice on the k dimension at this 1-based index. Repeatable.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60

Leaving out ``-i``/``-j``/``-k`` entirely plots the whole active grid instead of a slice, which
needs ``--view 3d``:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 60 --view 3d --save sgas_grid.png

``--quads``
-------------

Builds the slice as flat quads instead of hexahedra, touching only the cells on that slice
rather than materialising the whole 3D mesh. Faster on large grids, whether for a single static
slice or a long ``--animate`` animation, at the cost of losing the volume a slice would otherwise
have (no thresholding/clipping on it). Needs ``-i``/``-j``/``-k``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --quads --save sgas_k1.png
   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate --quads --save sgas.gif
