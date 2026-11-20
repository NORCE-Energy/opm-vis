Camera and view
=================

``--view``
------------

Camera preset, ``2d`` (default) or ``3d``. ``2d`` only supports one slice and needs one, since it
has no whole-grid view; ``3d`` is required for multiple slices or the whole grid.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -j 6 -r 60 --view 3d

``--azimuth``
---------------

Camera azimuth in degrees. Default: 30.0. Only used with ``--view 3d``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --azimuth 60

``--elevation``
------------------

Camera elevation in degrees. Default: 45.0. Only used with ``--view 3d``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --elevation 20

``--camera``
--------------

Places the camera exactly, instead of ``--azimuth``/``--elevation``: its position, the point it
looks at and its view-up direction, plus its zoom with ``--view 2d``, as
``X,Y,Z/FX,FY,FZ/UX,UY,UZ[/SCALE]``. Giving it together with ``--azimuth`` or ``--elevation``
is an error. ``--view`` still picks the projection.

The values don't have to be worked out by hand. The interactive window (run without
``--save``) shows the current camera in its lower left corner, updated whenever the view stops
moving, and prints it on closing together with the window size:

.. code-block:: text

   View: --camera 19487.12505,-281.7061122,-34882.97983/5800,4700,-41675/0.059,0.146,0.988 --window-size 1024 768

Rotate, pan and zoom to the view you want, close the window, and paste the printed options
into the same command with ``--save``:

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d
   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --save \
       --camera 19487.12505,-281.7061122,-34882.97983/5800,4700,-41675/0.059,0.146,0.988 \
       --window-size 1024 768

The values are in the scene's own coordinates, which ``--z-scale`` stretches vertically, so
they reproduce the view only with the same ``--z-scale``. The window size matters too: the
same camera frames a bit more or less at the sides in a window of another shape, which is
why it is printed alongside.

``--z-scale``
---------------

Vertical exaggeration. Default: 5.0.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -j 6 -r 60 --view 3d --z-scale 15

``--axes`` / ``--no-axes``
-----------------------------

Shows (default) or hides a labelled bounding box with axis titles and ticks.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-axes
