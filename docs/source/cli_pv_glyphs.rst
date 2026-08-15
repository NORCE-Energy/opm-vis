Vector glyphs
==============

``--glyphs``
--------------

Adds vector glyphs (arrows) on every chosen slice from three keyword components, ``X Y Z``, e.g.
a displacement vector, alongside ``--keyword``'s scalar colouring.

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ

``--glyph-scale`` / ``--no-glyph-scale``
-------------------------------------------

Scales each arrow by its own vector's magnitude (default), or draws every arrow the same length.

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ \
       --no-glyph-scale

``--glyph-every-n``
----------------------

Draws only 1 arrow out of every N cells, to thin out a dense grid. Arrow size is unaffected.
Default: 1.

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ \
       --glyph-every-n 4

``--glyph-factor``
---------------------

Factor to multiply vectors by before glyphing. Defaults to a size that draws the largest vector
at about one grid cell's width, computed across every animated report step with ``--animate`` so
arrow length stays comparable.

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ \
       --glyph-factor 50

``--glyph-color``
--------------------

Arrow colour, or ``glyphscale`` (default) to colour by vector magnitude instead of a flat colour.
An explicit colour overrides magnitude colouring.

.. code-block:: bash

   opm-vis-pv tests/data/TPSA_LAGGED -K DISPZ -k 1 -r 15 --glyphs DISPX DISPY DISPZ \
       --glyph-color black
