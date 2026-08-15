Command line
============

Two entry points plot or animate a case without writing any Python. Both take the same
filename-prefix ``PATHS`` convention as the Python API: the first path is the main run, any
further paths are restart runs, and the working directory is searched if none is given.

:doc:`cli_pv` (PyVista backend) supports the full option set, including multiple slices, wells,
glyphs and 3D views. :doc:`cli_mpl` (Matplotlib backend) is the alternative tool, less developed
and covering a smaller subset.

``-i``/``-j``/``-k`` slice indices are 1-based (matching Eclipse-style indexing, e.g.
``COMPDAT``): the first cell along an axis is 1, not 0. The most common options also have short
forms - ``-K`` for ``--keyword``, ``-r`` for ``--rstep``, ``-d`` for ``--diff``, ``-c`` for
``--calculator`` - used throughout the examples on both program pages.

.. toctree::
   :maxdepth: 1

   cli_pv
   cli_mpl
