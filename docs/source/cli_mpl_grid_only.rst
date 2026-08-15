Grid-only mode
================

``--grid-only``
-----------------

Plots the slice in a solid colour instead of colouring by a keyword. ``--keyword``/``-K`` is
neither needed nor allowed in this mode, and ``--animate`` is not supported with it.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -k 1 --grid-only --save grid_k1.png

``--grid-color``
------------------

Solid fill colour for ``--grid-only``, e.g. a name or hex code. Defaults to the backend's own
fill colour. Only used with ``--grid-only``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -k 1 --grid-only --grid-color lightgrey --save grid_k1.png

Combined with ``--show-edges`` (see :doc:`cli_mpl_view`) to also draw cell outlines on top:

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -k 1 --grid-only --grid-color lightgrey --show-edges \
       --save grid_k1.png
