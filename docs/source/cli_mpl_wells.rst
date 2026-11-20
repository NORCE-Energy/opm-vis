Wells
======

Wells are drawn on the plotted slice wherever they are completed in it, each labelled with its
name: a dot on a k-slice, a line on an i- or j-slice. There is no option to turn them off, but
``--well-name`` picks which ones.

``--well-name``
-----------------

Only draws this well (repeatable). Without it, every well on the slice is drawn. A name that is
not a well in the case is an error listing the wells it has. A well that is not completed on
the plotted slice is not drawn either way.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --well-name INJ
   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -i 1 -r 60 --well-name INJ --well-name PROD
