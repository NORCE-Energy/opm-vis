Layout
=======

``--subplots``
--------------

Gives each vector its own subplot instead of drawing them all in one axes. The subplots share
the x axis, so the time axis is only labelled along the bottom of each column.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR -K WBHP:PROD --subplots

This is the answer to vectors that do not share a unit. A single axes holding a rate and a
pressure has no meaningful y label, and says so with a warning; one vector per subplot always
has, and each subplot's y axis is scaled to its own data.

With ``--compare``, every subplot keeps the same case-to-colour mapping, so a legend read in one
of them holds in the rest.

``--layout``
------------

Shape of the ``--subplots`` grid, as ``ROWS COLS``. Left out, the squarest grid that fits every
vector is used, spread sideways rather than downwards - two vectors give one row of two, three
or four give a 2x2, five or six a 2x3.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR -K WBHP:PROD --subplots --layout 3 1
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K FGOR --subplots --layout 2 1

A single column stacks the vectors above one another over a shared time axis, which is the usual
way to read rates against each other. The grid may have room to spare - the unused cells are
removed rather than drawn empty - but not too little: a layout with fewer cells than there are
vectors is an error naming both counts. ``--layout`` only shapes a ``--subplots`` grid, and is
an error without it.

``--figsize``
-------------

Figure size in inches, as ``WIDTH HEIGHT``. A single axes keeps Matplotlib's own figure size; a
``--subplots`` grid instead gets a size scaled to its shape, roughly 4 by 2.8 inches per
subplot, up to 16 by 11 inches for a large one.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --figsize 10 4
   opm-vis-sum tests/data/SPE1CASE1 -K 'W*:PROD' --subplots --figsize 20 12

The scaling is what keeps a wildcard matching a dozen wells readable - one figure's worth of
space shared between twelve subplots leaves each of them too small for its own axis labels.
Past the cap the subplots do start to shrink again, and an explicit ``--figsize`` is the way
out.
