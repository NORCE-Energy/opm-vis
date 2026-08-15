Clipping
=========

``--clip``
------------

Cuts the whole grid with a plane normal to this axis (``x``, ``-x``, ``y``, ``-y``, ``z`` or
``-z``), instead of showing it whole. Needs no ``-i``/``-j``/``-k``; combines freely with
``--grid-only`` or with ``--threshold`` (both subsets are then shown together).

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --clip x --view 3d --save clip.png

``--clip-origin``
--------------------

Point ``--clip``'s plane passes through, ``X Y Z``. Defaults to the centre of the grid. Only used
with ``--clip``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --clip x --clip-origin 2317 4600 8325 --view 3d

``--clip-invert`` / ``--no-clip-invert``
-------------------------------------------

Keeps the side ``--clip``'s normal points away from (default), or the side it points towards.
Only used with ``--clip``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --clip x --no-clip-invert --view 3d

``--clip-crinkle``
---------------------

Keeps whole cells at the ``--clip`` boundary instead of cutting through them. Only used with
``--clip``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --clip x --clip-crinkle --view 3d
