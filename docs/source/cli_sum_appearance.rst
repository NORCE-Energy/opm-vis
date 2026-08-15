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
