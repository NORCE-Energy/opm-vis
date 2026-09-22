Fault traces
================

``--fault``
-------------

Path to a ``.DATA`` file or an include file holding ``FAULTS`` keyword(s); draws every fault
trace crossing the slice as a line, each annotated with its name. Independent of every other
option: combines freely with ``--keyword``, ``--grid-only``, ``--view 2d``/``3d``, and so on. A
fault whose own direction matches the slice's axis (e.g. an X/X- fault on an i-slice) is not
drawn - it lies flush in the slice's own plane rather than crossing it as a line.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d \
       --fault tests/data/SPE1CASE1_FAULTS.INC

``--fault-name``
-------------------

Only draws this fault (repeatable). Only used with ``--fault``.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 \
       --fault tests/data/SPE1CASE1_FAULTS.INC --fault-name FAULT1
