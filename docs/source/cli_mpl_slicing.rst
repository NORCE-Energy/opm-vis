Slicing
========

``-i``, ``--i-index``
-----------------------

Slice on the i dimension at this 1-based index. opm-vis-mpl supports only one slice at a time,
across ``-i``/``-j``/``-k`` combined.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -i 5 -r 60

``-j``, ``--j-index``
-----------------------

Slice on the j dimension at this 1-based index.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -j 6 -r 60

``-k``, ``--k-index``
-----------------------

Slice on the k dimension at this 1-based index.

.. code-block:: bash

   opm-vis-mpl tests/data/SPE1CASE1 -K SGAS -k 1 -r 60

At least one of ``-i``/``-j``/``-k`` is required - unlike opm-vis-pv, opm-vis-mpl has no
whole-grid view.
