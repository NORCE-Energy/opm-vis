Input and keyword
==================

``-f``, ``--folder``
--------------------

Folder with the case's output files, by default the current folder. Every case found there -
every name with an ``.EGRID``, ``.INIT``, ``.UNRST``, ``.X0000``, ``.SMSPEC`` or ``.UNSMRY``
file - is read as one run: the main run followed by its restarts, ordered by where each one
starts. Repeatable, for restarts kept in folders of their own; every case in every folder given
is still part of the one run.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60
   opm-vis-pv -f runs/base -f runs/base_restart -K SGAS -k 1 -r 60

``-K``, ``--keyword``
----------------------

OPM keyword to plot, e.g. ``SGAS`` or ``PRESSURE``. Required unless ``--grid-only`` is given.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60
