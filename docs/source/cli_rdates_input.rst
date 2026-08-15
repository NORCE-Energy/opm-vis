Input
======

``PATHS``
---------

Filename prefixes: the first is the main run, any further ones are restart runs. Defaults to
searching the working directory (``./``) if not given - unlike the plotting programs, which
print their help when run with no arguments at all, listing the case in the working directory
is what a bare ``opm-vis-rdates`` does.

.. code-block:: bash

   opm-vis-rdates tests/data/SPE1CASE1
   opm-vis-rdates

A main run and a restart of it both report the step the restart branches from; that step is
listed once, with the date the main run gives it.

.. code-block:: bash

   opm-vis-rdates tests/data/SPE1CASE2 tests/data/SPE1CASE2_RESTART_60
