View and appearance
=====================

``--view``
------------

Camera preset, ``2d`` (default) or ``3d``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d

``--cmap``
------------

Matplotlib colour map name. Default: ``viridis``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --cmap plasma

``--clim``
------------

Colour limits ``MIN MAX``. Defaults to the data range of the report step(s) shown.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --clim 0.0 0.8

``--no-colorbar``
--------------------

Hides the colorbar.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-colorbar

``--show-edges``
-------------------

Draws each cell's outline on top of its fill colour.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --show-edges
