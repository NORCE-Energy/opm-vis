Input and keywords
===================

``-f``, ``--folder``
--------------------

Folder with the case's output files, by default the current folder. Every case found there -
every name with an ``.EGRID``, ``.INIT``, ``.UNRST``, ``.X0000``, ``.SMSPEC`` or ``.UNSMRY``
file - is read as one run - the main run followed by its restarts, stitched into a single time series - ordered by where each one
starts. Repeatable, for restarts kept in folders of their own; every case in every folder given
is still part of the one run.

.. code-block:: bash

   opm-vis-sum -f tests/data/SPE1CASE1 -K FOPR

A restart run re-simulates everything from the point it branched off, so where the two overlap
the restart's values win and the result stays strictly chronological.

.. code-block:: bash

   opm-vis-sum -f tests/data/SPE1CASE2 -K FOPR
   opm-vis-sum -f runs/base -f runs/base_restart -K FOPR

``--compare``
-------------

Reads each ``-f``/``--folder`` as a case of its own - with any restarts in that folder -
instead of stitching every folder into one restart chain, drawing one line per case and vector.
At least two folders are needed - a single folder is already read as one case with its
restarts.

.. code-block:: bash

   opm-vis-sum --compare -f tests/data/SPE1CASE1 -f tests/data/SPE1CASE2 -K FOPR
   opm-vis-sum --compare -f runs/base -f runs/high_rate -K FOPR

The legend names each case after its ``.SMSPEC`` file. When those names collide, as they do when
every run is called ``CASE``, the containing directory is added to all of them.

``-K``, ``--keyword``
-----------------------

Summary vector to plot. Repeatable, once per vector, and the vectors appear in the order given.

.. code-block:: bash

   opm-vis-sum -f tests/data/SPE1CASE1 -K FOPR
   opm-vis-sum -f tests/data/SPE1CASE1 -K FOPR -K FGOR

A value containing ``*``, ``?`` or ``[`` is an fnmatch pattern, expanded against the vectors the
case actually has; its own matches are sorted, and a vector matched twice is drawn once. Quote
the pattern, or the shell expands it against file names before ``opm-vis-sum`` ever sees it.

.. code-block:: bash

   opm-vis-sum -f tests/data/SPE1CASE1 -K 'WOPR:*'
   opm-vis-sum -f tests/data/SPE1CASE1 -K 'W*:PROD'

Matching is case sensitive, and summary mnemonics are upper case - ``-K fopr`` finds nothing. A
pattern matching nothing and a plain name the case does not have are both errors, with different
advice: the first is too narrow, the second is probably a misspelling.

``--list-keywords``
---------------------

Prints the summary vectors the case has, one per line and sorted, then exits without plotting.
Summary files carry hundreds of mnemonics on a real field, so this is the way to find out what
``-K`` can be given.

.. code-block:: bash

   opm-vis-sum -f tests/data/SPE1CASE1 --list-keywords

It cannot be combined with the plotting options - it either lists or plots, and an invocation
asking for both is a mistake worth catching. ``TIME`` and ``YEARS`` appear in the list like any
other vector; they are what ``--x-axis days`` and ``--x-axis years`` measure, so there is rarely
a reason to plot them against themselves.
