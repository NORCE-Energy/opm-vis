Output
=======

``--save``, ``-s``
--------------------

Saves to file instead of opening an interactive window. If given with no path, a name is
generated from the keyword, slice and report step(s).

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save
   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save sgas_k1.png
