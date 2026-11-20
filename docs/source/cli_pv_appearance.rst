Grid rendering and appearance
================================

``--wireframe``
------------------

Adds the grid outline for context around the plotted slice(s).

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -j 6 -r 60 --view 3d --wireframe

``--show-edges``
-------------------

Draws each cell's outline on top of its fill colour.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 --grid-only --show-edges --view 3d --save

``--opacity``
---------------

Opacity of the slice(s)/grid, from 0 (transparent) to 1 (opaque, the default).

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --opacity 0.5

``--cmap``
------------

Matplotlib colour map name. Default: ``viridis``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --cmap plasma

``--clim``
------------

Colour limits ``MIN MAX``. Defaults to the data range of the report step(s) shown.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --clim 0.0 0.8

``--log-scale``
------------------

Maps colours logarithmically instead of linearly.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 --log-scale

``--window-size``
--------------------

Render window size in pixels, ``WIDTH HEIGHT``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --window-size 1600 1200 --save

``--no-colorbar``
--------------------

Hides the scalar bar.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-colorbar

``--colorbar-label``, ``-clabel``
-----------------------------------

Label for the scalar bar instead of the generated keyword and unit. Text between ``$`` signs is
rendered as math, LaTeX-style, by VTK's MathText, which uses Matplotlib's mathtext: subscripts and superscripts,
Greek letters, ``\frac``, ``\bar`` and so on. Single-quote the label so the shell leaves the
``$`` alone. Invalid math is reported as an error before anything is plotted, and the option
is rejected with ``--no-colorbar`` or ``--grid-only``, which have no scalar bar to label.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -clabel '$S_g$ [-]'
   opm-vis-pv -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d -clabel '$\Delta p$ [psi]'

``--no-title``
-----------------

Hides the report-date title.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-title

``--font-scale``
------------------

Scales every text size by this factor: the title, axis labels and ticks, the scalar bar, and the
well, fault and polygon labels. Default: 1.0. pvplot places its scalar bars and axes at fixed
positions, so a large factor can push text past the window's edge; a larger ``--window-size``
makes room for it.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --font-scale 1.5
