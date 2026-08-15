Difference plots
==================

``-d``, ``--diff``
--------------------

Plots the difference from ``--diff-rstep`` instead of ``--keyword``'s own values.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d

``--diff-rstep``
-------------------

Report step to difference against. Default: 0. Only used with ``--diff``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d --diff-rstep 30

``--diff-kind``
------------------

One of ``plain`` (value minus reference, the default), ``absolute`` (the plain difference's
magnitude) or ``relative`` (percent change from the reference). Only used with ``--diff``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K PRESSURE -k 1 -r 60 -d --diff-kind relative
