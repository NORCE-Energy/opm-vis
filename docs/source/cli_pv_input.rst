Input and keyword
==================

``PATHS``
---------

Filename prefixes: the first is the main run, any further ones are restart runs. Defaults to
searching the working directory (``./``) if not given.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60

``-K``, ``--keyword``
----------------------

OPM keyword to plot, e.g. ``SGAS`` or ``PRESSURE``. Required unless ``--grid-only`` is given.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60
