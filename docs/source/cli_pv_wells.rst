Wells
======

``--wells`` / ``--no-wells``
-------------------------------

Draws (default) or hides wells with a completion on at least one chosen slice.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -j 6 -r 60 --view 3d --no-wells

``--all-wells``
-----------------

Draws every well in the grid, not just ones on a chosen slice. Takes priority over ``--wells``
if both are given.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d --all-wells
