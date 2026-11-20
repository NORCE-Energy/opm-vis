Report step and animation
===========================

``-r``, ``--rstep``
---------------------

Report step to plot. Not needed at all for a keyword that does not change over time, such as
``PERMX``, ``PORO`` or ``DEPTH`` from the ``.INIT`` file. Those can be plotted even for a case
that has only ``.EGRID`` and ``.INIT`` files, e.g. a dry run; the plot then has no date title
and no wells, since both come from the restart files.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60
   opm-vis-mpl -f tests/data/SPE1CASE1 -K PERMX -k 1

``--animate``
---------------

Animates over report steps instead of plotting a single one. With ``-r``/``--rstep`` given as
``START:END`` or ``START:END:STEP``, only that range is animated; left out, every report step in
the case is used.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 --animate --save
   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 0:120:10 --animate --save

``--fps``
-----------

Frames per second for ``--animate``. Default: 3.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 --animate --fps 4 --save
