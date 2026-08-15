Grid rendering and appearance
================================

``--wireframe``
------------------

Adds the grid outline for context around the plotted slice(s).

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -j 6 -r 60 --view 3d --wireframe

``--show-edges``
-------------------

Draws each cell's outline on top of its fill colour.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --grid-only --show-edges --view 3d --save grid.png

``--opacity``
---------------

Opacity of the slice(s)/grid, from 0 (transparent) to 1 (opaque, the default).

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --opacity 0.5

``--cmap``
------------

Matplotlib colour map name. Default: ``viridis``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --cmap plasma

``--clim``
------------

Colour limits ``MIN MAX``. Defaults to the data range of the report step(s) shown.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --clim 0.0 0.8

``--log-scale``
------------------

Maps colours logarithmically instead of linearly.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 --log-scale

``--window-size``
--------------------

Render window size in pixels, ``WIDTH HEIGHT``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --window-size 1600 1200 --save sgas.png

``--no-colorbar``
--------------------

Hides the scalar bar.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-colorbar

``--no-title``
-----------------

Hides the report-date title.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-title
