Appearance
===========

``--title``
-----------

Figure title. Left out, a single case is titled with its own name, and a ``--compare`` figure is
left untitled - its legend already names the cases.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --title "Field oil production"

With ``--subplots`` this is the figure's overall title; each subplot keeps its own vector name on
its y axis.

``--grid``, ``--no-grid``
---------------------------

Draws faint grid lines behind the curves. On by default.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --no-grid

``--legend``, ``--no-legend``
-------------------------------

Labels each curve. On by default.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K 'WOPR:*' --no-legend

What a label says is whatever actually varies inside that axes: the vector name when several
vectors share it, the case name when several cases do, and ``case - vector`` when both do. An
axes with only one curve gets no legend at all, since its y axis already names what it shows -
which is also why ``--subplots`` without ``--compare`` never draws one.

``--no-legend`` is worth reaching for when a wildcard matched a lot of wells: long legends are
split into further columns rather than one very tall one, but at some point they cover the
curves regardless.

``--linewidth``, ``--lw``
---------------------------

Line width of every curve. Defaults to Matplotlib's own default.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K 'WOPR:*' --lw 1

Thinner lines are worth reaching for alongside ``--no-legend`` on a busy wildcard selection,
where the default width can make overlapping curves hard to tell apart.

``--linestyle``, ``--ls``
---------------------------

Line style: ``solid`` (the default), ``dashed``, ``dashdot``, ``dotted``, or ``none``. Left out,
several keywords sharing one axes under ``--compare`` instead get a dash pattern per keyword, so
the same vector can be told apart across cases.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --ls dashed

Repeatable: given once, it applies to every curve; given once per ``-K``/``--keyword`` (in the
same order, after any wildcard is expanded), each vector gets its own style.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR --ls dashed --ls dotted

Any other count is an error naming both the count given and the vectors selected. ``none`` needs
``--marker`` as well for that vector - a curve with neither a line nor a marker would not be
drawn at all, so this combination is rejected before anything is plotted.

``--marker``
-------------

Matplotlib marker for every data point, e.g. ``o``, ``s`` or ``^`` - see `Matplotlib's marker
reference <https://matplotlib.org/stable/api/markers_api.html>`_ for the full set. Repeatable in
the same way as ``--linestyle``: once for every curve, or once per ``-K``/``--keyword`` for one
marker per vector.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --marker o
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR --marker o --marker s

Given alone for a vector, its marker replaces the line rather than joining it - the usual way to
plot a handful of report steps as discrete points instead of a continuous curve. Add
``--linestyle`` to draw both:

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --marker o --linestyle solid
