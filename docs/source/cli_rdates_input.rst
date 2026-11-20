Input
======

``-f``, ``--folder``
--------------------

Folder with the case's output files, by default the current folder. Every case found there -
every name with an ``.EGRID``, ``.INIT``, ``.UNRST``, ``.X0000``, ``.SMSPEC`` or ``.UNSMRY``
file - is read as one run: the main run followed by its restarts, ordered by where each one
starts. Repeatable, for restarts kept in folders of their own; every case in every folder given
is still part of the one run. Unlike the plotting programs, which print their help when run with no
arguments at all, listing the case in the current folder is what a bare ``opm-vis-rdates``
does.

.. code-block:: bash

   opm-vis-rdates -f tests/data/SPE1CASE1
   opm-vis-rdates

A main run and a restart of it both report the step the restart branches from; that step is
listed once, with the date the main run gives it. ``tests/data/SPE1CASE2`` holds both
``SPE1CASE2`` and its restart ``SPE1CASE2_RESTART_60``:

.. code-block:: bash

   opm-vis-rdates -f tests/data/SPE1CASE2
