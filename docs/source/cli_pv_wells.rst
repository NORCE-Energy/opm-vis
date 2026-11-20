Wells
======

``--wells`` / ``--no-wells``
-------------------------------

Draws (default) or hides wells with a completion on at least one chosen slice.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -j 6 -r 60 --view 3d --no-wells

``--all-wells``
-----------------

Draws every well in the grid, not just ones on a chosen slice. Takes priority over ``--wells``
if both are given.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --all-wells

``--well-name``
-----------------

Only draws this well (repeatable). Without it, every well is drawn. A name that is not a well
in the case is an error listing the wells it has. It narrows the wells ``--wells`` or
``--all-wells`` would draw, so a named well that is not completed on a chosen slice needs
``--all-wells`` to be shown; it is rejected together with ``--no-wells``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --all-wells --well-name PROD
