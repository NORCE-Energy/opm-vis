Command line
============

Four entry points work on a case without writing any Python. They all take the same
filename-prefix ``PATHS`` convention as the Python API: the first path is the main run, any
further paths are restart runs, and the working directory is searched if none is given.

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
