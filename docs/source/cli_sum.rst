opm-vis-sum
===========

Plots summary vectors - the time series in a case's ``.SMSPEC``/``.UNSMRY`` files - instead of
anything on the grid: field and well rates, totals, pressures, block values. Matplotlib only;
there is no PyVista equivalent. See :doc:`cli` for the shared ``PATHS`` convention.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR --subplots --save rates.png

``-K``/``--keyword`` is repeatable and takes fnmatch patterns, so a whole family of vectors can
be picked at once - ``-K 'WOPR:*'`` plots the oil rate of every well. Quote the pattern, or the
shell tries to expand it against file names first.

``--list-keywords`` prints what the case actually has, without plotting anything:

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 --list-keywords

.. code-block:: text

   BGSAT:1,1,1
   BPR:1,1,1
   ...
   FGOR
   FOPR
   TIME
   WBHP:INJ
   WBHP:PROD
   ...
   YEARS

Every vector is drawn in one axes by default, which is what makes two rates directly comparable;
``--subplots`` gives each its own axes instead, sharing the x axis. Vectors measuring different
things do not share a y axis meaningfully, so mixing units in one axes warns and points at
``--subplots``.

By default every ``PATHS`` entry belongs to one case - a main run and its restarts, stitched into
a single non-overlapping series. ``--compare`` reads each path as a case of its own instead,
drawing one line per case and vector.

Each option group below has its own page with a description and a runnable example of every
option in it: :doc:`cli_sum_input`, :doc:`cli_sum_layout`, :doc:`cli_sum_axes`,
:doc:`cli_sum_appearance`, :doc:`cli_sum_output`.

The same data is available from Python through :class:`~opm_vis.utils.summary.SummaryReader`,
and the same plot through :class:`~opm_vis.plot.plot_summary.SummaryPlot` - see :doc:`examples`.

Option reference
----------------

.. click:: opm_vis.cli.summary_cli:main
   :prog: opm-vis-sum

.. toctree::
   :maxdepth: 1
   :caption: Option reference
   :hidden:

   cli_sum_input
   cli_sum_layout
   cli_sum_axes
   cli_sum_appearance
   cli_sum_output
