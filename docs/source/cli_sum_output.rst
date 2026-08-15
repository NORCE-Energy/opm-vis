Output
=======

``--save``, ``-s``
--------------------

Saves to file instead of opening an interactive window. Given a path, the plot is written there;
given with no path at all, a name is generated from the selected vectors, ``--compare`` and
``--x-axis``.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --save rates.png
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --save

The generated name spells out at most three vectors and then counts the rest, and replaces the
``:`` and ``,`` in a mnemonic with ``-`` - they are ordinary characters in a summary mnemonic but
poor ones in a file name, and ``:`` is invalid on Windows. So a wildcard still gives a usable
name:

.. code-block:: text

   -K FOPR                          FOPR_date.png
   -K 'WOPR:*' --x-axis years       WOPR-INJ_WOPR-PROD_years.png
   -K FOPR --compare                FOPR_compare_date.png
   -K '*'                           BGSAT-1-1-1_BGSAT-1-1-2_BGSAT-1-1-3_and39more_date.png

``--subplots``, ``--layout`` and the axis limits are deliberately not part of the name: they
change how the same data is laid out, not what it is.

The file format follows the extension, as Matplotlib reads it - ``.png``, ``.pdf`` and ``.svg``
all work.

``--export``, ``-e``
-----------------------

Exports the plotted data as CSV, independently of ``--save``: give both to get a plot and its
data from one invocation, or ``--export`` alone to skip the image entirely.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR --export rates.csv
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --export --save rates.png

Given with no path at all, the CSV is printed to standard output instead of being written to a
file - useful for piping straight into another tool:

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --export | column -s, -t

.. code-block:: text

   date,FOPR
   2015-01-02T00:00:00,20000
   2015-01-05T00:00:00,20000
   ...
   2024-12-29T00:00:00,5558.12

The first column follows ``--x-axis``, with dates as ISO-8601. One column follows per vector, or
one per case and vector under ``--compare`` (``case:vector``). Numbers are rounded to 6
significant digits - this accompanies a plot, not a full-precision export of the run.

Cases being compared do not have to share a report frequency or a start date: rows are the union
of every case's own timesteps, and a case with no value at a given row leaves that cell blank
rather than forcing every case onto one grid.

``--subplots``, ``--layout``, the axis limits and the appearance options have no effect on
``--export`` - they only change how the plot is drawn.
