Calculator
============

``-c``, ``--calculator``
--------------------------

Reduces ``--keyword`` across grid layers along the sliced dimension, from the given
``-i``/``-j``/``-k`` index to the grid's last layer (or ``--calc-count`` further layers).
``mean``/``sum`` aggregate every layer in that range; ``surface`` instead takes each position's
first active layer from the range's start, useful for a "top of reservoir" map through an eroded
or faulted structure. Needs ``--keyword``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c mean --save pressure_mean.png
   opm-vis-mpl tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -c surface --save pressure_top.png

``--calc-count``
-------------------

Limits ``--calculator`` to this many further layers after the given ``-i``/``-j``/``-k`` index
(which is always included itself), instead of continuing to the grid's last layer, e.g.
``--calc-count 1`` aggregates the given index plus the next one. Only used with ``--calculator``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -c sum --calc-count 2
