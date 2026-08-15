Input and keywords
===================

``PATHS``
---------

Filename prefixes: the first is the main run, any further ones are restart runs, read as a
single stitched time series. Defaults to searching the working directory (``./``) if not given.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR

A restart run re-simulates everything from the point it branched off, so where the two overlap
the restart's values win and the result stays strictly chronological.

.. code-block:: bash

   opm-vis-sum runs/base/CASE runs/base_restart/CASE -K FOPR

``--compare``
-------------

Reads each ``PATHS`` entry as a case of its own instead of as one restart chain, drawing one
line per case and vector. At least two paths are needed - a single path is already read as one
case with its restarts.

.. code-block:: bash

   opm-vis-sum --compare runs/base/CASE runs/high_rate/CASE -K FOPR

Each run has to live in its own directory. Prefixes are matched with a trailing wildcard, so two
runs named ``CASE`` and ``CASE_RESTART`` in one directory would both be found by the prefix
``CASE`` - separate directories with the same case name inside them avoid that, and are how
runs are normally organised anyway.

The legend names each case after its ``.SMSPEC`` file. When those names collide, as they do when
every run is called ``CASE``, the containing directory is added to all of them.

``-K``, ``--keyword``
-----------------------

Summary vector to plot. Repeatable, once per vector, and the vectors appear in the order given.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR

A value containing ``*``, ``?`` or ``[`` is an fnmatch pattern, expanded against the vectors the
case actually has; its own matches are sorted, and a vector matched twice is drawn once. Quote
the pattern, or the shell expands it against file names before ``opm-vis-sum`` ever sees it.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K 'WOPR:*'
   opm-vis-sum tests/data/SPE1CASE1 -K 'W*:PROD'

Matching is case sensitive, and summary mnemonics are upper case - ``-K fopr`` finds nothing. A
pattern matching nothing and a plain name the case does not have are both errors, with different
advice: the first is too narrow, the second is probably a misspelling.

``--list-keywords``
---------------------

Prints the summary vectors the case has, one per line and sorted, then exits without plotting.
Summary files carry hundreds of mnemonics on a real field, so this is the way to find out what
``-K`` can be given.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 --list-keywords

It cannot be combined with the plotting options - it either lists or plots, and an invocation
asking for both is a mistake worth catching. ``TIME`` and ``YEARS`` appear in the list like any
other vector; they are what ``--x-axis days`` and ``--x-axis years`` measure, so there is rarely
a reason to plot them against themselves.
