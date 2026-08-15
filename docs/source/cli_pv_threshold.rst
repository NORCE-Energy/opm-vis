Thresholding
=============

``--threshold``
------------------

Shows only cells where ``--keyword``'s value is at least ``LOW`` (or within ``LOW:HIGH``) at
``--rstep``, instead of the whole grid - e.g. a gas plume. Needs ``--keyword`` and no
``-i``/``-j``/``-k``; not compatible with ``--animate``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --threshold 0.4 --view 3d --save plume.png
   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --threshold 0.2:0.6 --view 3d

``--threshold-invert``
-------------------------

Keeps the cells that fail ``--threshold`` instead. Only used with ``--threshold``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -r 120 --threshold 0.4 --threshold-invert --view 3d
