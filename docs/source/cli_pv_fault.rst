Fault surfaces
================

``--fault``
-------------

Path to a ``.DATA`` file or an include file holding ``FAULTS`` keyword(s); draws the fault
surface(s) on top of the plot, each annotated with its name. Independent of every other option:
combines freely with ``--keyword``, ``--grid-only``, any slice, ``--view 2d``/``3d``, ``--wells``,
``--wireframe``, and so on. Without ``--fault-name``, every fault on the chosen ``-i``/``-j``/``-k``
slice(s) is drawn, or every fault in the file if no slice was given.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d \
       --fault tests/data/SPE1CASE1_FAULTS.INC

``--fault-name``
-------------------

Only draws this fault (repeatable). Only used with ``--fault``.

.. code-block:: bash

   opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d \
       --fault tests/data/SPE1CASE1_FAULTS.INC --fault-name FAULT1
