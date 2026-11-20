View and appearance
=====================

``--view``
------------

Camera preset, ``2d`` (default) or ``3d``.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d

``--cmap``
------------

Matplotlib colour map name. Default: ``viridis``.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --cmap plasma

``--clim``
------------

Colour limits ``MIN MAX``. Defaults to the data range of the report step(s) shown.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --clim 0.0 0.8

``--log-scale``
-----------------

Maps colours logarithmically, with decade ticks on the colorbar - useful for values spanning
orders of magnitude, such as permeability. A log scale can only colour positive values: cells
that are zero or negative are left blank, with a warning saying how many, and a plot with no
positive value at all is an error. With ``--clim`` the lower limit must be above 0.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K PERMX -i 5 --log-scale

``--no-colorbar``
--------------------

Hides the colorbar.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-colorbar

``--no-title``
-----------------

Hides the report-date title above the plot, in a still image and in every frame of an
animation. A saved still image is then also cropped without the room the title took.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-title

``--colorbar-label``, ``-clabel``
-----------------------------------

Label for the colorbar instead of the generated keyword and unit. Text between ``$`` signs is
rendered as math, LaTeX-style, by Matplotlib's mathtext: subscripts and superscripts,
Greek letters, ``\frac``, ``\bar`` and so on. Single-quote the label so the shell leaves the
``$`` alone. Invalid math is reported as an error before anything is plotted, and the option
is rejected with ``--no-colorbar`` or ``--grid-only``, which have no colorbar to label.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -clabel '$S_g$ [-]'
   opm-vis-mpl -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d -clabel '$\Delta p$ [psi]'

``--figsize``
---------------

Figure size in inches. A saved image is about this size at Matplotlib's 100 dpi, cropped to
the plot itself so there is no empty margin around it. With ``--view 2d`` the default follows
the slice's own proportions, so a square map view gets square axes. The ratio is clamped
between 1:2 and 2.5:1, so a cross-section, which is often 100 times wider than it is deep,
still gets a usable height. With ``--view 3d`` the default is Matplotlib's own figure size.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -i 5 -r 60 --figsize 12 4

``--show-edges``
-------------------

Draws each cell's outline on top of its fill colour.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --show-edges

``--font-scale``
------------------

Scales every text size by this factor: the title, axis labels and ticks, the colorbar, and the
well, fault and polygon labels. Default: 1.0.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --font-scale 1.5
