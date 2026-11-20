Output
=======

``-F``, ``--format``
----------------------

Output format: ``table`` (the default), ``csv`` or ``json``. The table is aligned for reading
and dates it ``dd.mm.yyyy``, the same way the plot titles do; ``csv`` and ``json`` are meant for
piping into other tools and use ISO-8601 dates instead.

.. code-block:: bash

   opm-vis-rdates -f tests/data/SPE1CASE1 -F csv
   opm-vis-rdates -f tests/data/SPE1CASE1 -F json -r 120

.. code-block:: text

   rstep,date,days,years
   0,2015-01-01,0,0.000000
   ...
   120,2024-12-29,3650,9.993155

``--save``, ``-s``
--------------------

Writes the output to a file instead of printing it. Unlike the plotting programs' ``--save``,
this one always needs a path - there is no keyword or slice to generate a name from.

.. code-block:: bash

   opm-vis-rdates -f tests/data/SPE1CASE1 -F csv --save timeline.csv
