Grid-only mode
================

``--grid-only``
-----------------

Plots the grid (or the chosen slice(s)) in a solid colour instead of colouring by a keyword.
``--keyword``/``-K`` is neither needed nor allowed in this mode, and ``--animate`` is not
supported with it.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --grid-only --view 3d --save grid.png

``--grid-color``
------------------

Solid fill colour for ``--grid-only``, e.g. a name or hex code. Defaults to the backend's own
fill colour. Only used with ``--grid-only``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --grid-only --grid-color lightgrey --view 3d --save grid.png

Combined with ``--show-edges`` (see :doc:`cli_pv_appearance`) to also draw cell outlines on top:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 --grid-only --grid-color lightgrey --show-edges \
       --view 3d --save grid.png
