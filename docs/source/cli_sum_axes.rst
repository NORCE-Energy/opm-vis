Axes
=====

``--x-axis``
------------

What to plot against: ``date`` (the default) uses the report dates the summary file records,
while ``days`` and ``years`` use the time since the simulation started.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --x-axis days
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --x-axis years

Elapsed time is measured from the deck's ``START``, not from the first reported timestep, so the
values are the ``TIME`` and ``YEARS`` vectors themselves. A year is 365.25 days, the same
convention :doc:`cli_rdates` reports in.

The choice matters with ``--compare``: ``date`` puts the cases on a common calendar, while
``days`` and ``years`` align them all at zero. Runs of the same field that started on different
dates are usually meant to be compared at the same elapsed time, and runs of the same forecast
at the same calendar date.

``--log-y``
-----------

Uses a logarithmic y axis, on every subplot.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K WGPR:PROD --log-y

Matplotlib drops non-positive values on a logarithmic axis, so a rate that is zero until its
well opens simply starts later. A vector that is never positive cannot be drawn at all, and
says so with a warning rather than leaving an unexplained gap in the legend.

``--xlim``
----------

X axis limits, as ``MIN MAX``, applied to every subplot. Defaults to the span of the data. The
values follow ``--x-axis``: ISO dates (``YYYY-MM-DD``) on the default date axis, plain numbers
on ``days`` and ``years``.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --xlim 2016-01-01 2020-01-01
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --x-axis days --xlim 0 1000

Giving a number on a date axis, or a date on a numeric one, is an error naming the form that
axis expects. ``MIN`` must be less than ``MAX``.

``--ylim``
----------

Y axis limits, as ``MIN MAX``, always numbers. Defaults to the range of the data.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --ylim 0 25000

Applied to every subplot, which with ``--subplots`` means vectors measuring different things
share one y range. That is rarely what is wanted, so limits and ``--subplots`` are usually worth
keeping apart.
