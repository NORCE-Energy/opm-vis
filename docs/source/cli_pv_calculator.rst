Calculator
============

``-c``, ``--calculator``
--------------------------

Reduces ``--keyword`` across grid layers along the sliced dimension, from the given
``-i``/``-j``/``-k`` index to the grid's last layer (or ``--calc-count`` further layers).
``mean``/``sum`` aggregate every layer in that range; ``surface`` instead takes each position's
first active layer from the range's start, useful for a "top of reservoir" map through an eroded
or faulted structure. Requires exactly one of ``-i``/``-j``/``-k``, and needs ``--keyword``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c mean --save pressure_mean.png
   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c surface --save pressure_top.png

``--calc-count``
-------------------

Limits ``--calculator`` to this many further layers after the given ``-i``/``-j``/``-k`` index
(which is always included itself), instead of continuing to the grid's last layer, e.g.
``--calc-count 1`` aggregates the given index plus the next one. Only used with ``--calculator``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -c sum --calc-count 2

``--calculator`` combines with ``--diff`` as "diff first, then aggregate": the per-cell
difference between ``--rstep`` and ``--diff-rstep`` is computed first, then ``--calculator``
aggregates that difference across the layer range:

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c mean -d --diff-rstep 0
