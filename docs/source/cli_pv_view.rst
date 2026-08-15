Camera and view
=================

``--view``
------------

Camera preset, ``2d`` (default) or ``3d``. ``2d`` only supports one slice and needs one, since it
has no whole-grid view; ``3d`` is required for multiple slices or the whole grid.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -j 6 -r 60 --view 3d

``--azimuth``
---------------

Camera azimuth in degrees. Default: 30.0. Only used with ``--view 3d``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --azimuth 60

``--elevation``
------------------

Camera elevation in degrees. Default: 45.0. Only used with ``--view 3d``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --elevation 20

``--z-scale``
---------------

Vertical exaggeration. Default: 5.0.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -j 6 -r 60 --view 3d --z-scale 15

``--axes`` / ``--no-axes``
-----------------------------

Shows (default) or hides a labelled bounding box with axis titles and ticks.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-axes
