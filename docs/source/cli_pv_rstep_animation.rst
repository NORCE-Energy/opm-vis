Report step and animation
===========================

``-r``, ``--rstep``
---------------------

Report step to plot. Not needed at all for a keyword that does not change over time.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60

``--animate``
---------------

Animates over report steps instead of plotting a single one. With ``-r``/``--rstep`` given as
``START:END`` or ``START:END:STEP``, only that range is animated; left out, every report step in
the case is used.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate --save sgas.gif
   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 0:120:10 --animate --save sgas.gif

``--fps``
-----------

Frames per second for ``--animate``. Default: 3.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 --animate --fps 4 --save sgas.gif
