Command line
============

Four entry points work on a case without writing any Python. They all find the case the same
way: pass its folder with ``-f``/``--folder``, or leave it out to use the current folder. Every
case found in the folder - every name with an ``.EGRID``, ``.INIT``, ``.UNRST``, ``.X0000``,
``.SMSPEC`` or ``.UNSMRY`` file - is read as one run: the main run followed by its restarts,
ordered by the report step (or else the summary time) each one starts at. ``-f`` is
repeatable, for restarts kept in folders of their own.

:doc:`cli_pv` (PyVista backend) supports the full option set, including multiple slices, wells,
glyphs and 3D views. :doc:`cli_mpl` (Matplotlib backend) is the alternative tool, less developed
and covering a smaller subset. Both of those colour the grid; :doc:`cli_sum` plots the case's
summary vectors instead - the time series in its ``.SMSPEC``/``.UNSMRY`` files, such as ``FOPR``
or ``WBHP:PROD``. :doc:`cli_rdates` does not plot at all: it lists a case's report steps with
their dates and the time since the simulation started - handy for picking the ``--rstep`` to
pass to the two grid plotters.

``-i``/``-j``/``-k`` slice indices are 1-based (matching Eclipse-style indexing, e.g.
``COMPDAT``): the first cell along an axis is 1, not 0. The most common options also have short
forms - ``-K`` for ``--keyword``, ``-r`` for ``--rstep``, ``-d`` for ``--diff``, ``-c`` for
``--calculator`` - used throughout the examples on the program pages. ``-K`` is single-valued on
the grid plotters, which colour by one keyword at a time, and repeatable on :doc:`cli_sum`, where
several vectors share one plot.

.. toctree::
   :maxdepth: 1

   cli_pv
   cli_mpl
   cli_sum
   cli_rdates
