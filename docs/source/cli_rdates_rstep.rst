Report step
============

``-r``, ``--rstep``
---------------------

Report step, or range of report steps, to list. Left out, every report step in the case is
listed. A single value lists just that step; ``START:END`` or ``START:END:STEP`` lists a range,
where ``END`` is included.

.. code-block:: bash

   opm-vis-rdates tests/data/SPE1CASE1 -r 60
   opm-vis-rdates tests/data/SPE1CASE1 -r 0:120
   opm-vis-rdates tests/data/SPE1CASE1 -r 0:120:30

Report steps missing from the case are skipped, so a range does not have to line up with the
case's own output frequency. A single report step the case does not have is an error instead,
since it would otherwise print nothing at all.

Elapsed time is always measured from the case's first report step, whether or not it is in the
selection - ``-r 60:120`` still reports the days and years since the start of the simulation,
not since report step 60.
