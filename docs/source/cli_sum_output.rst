Output
=======

``--save``, ``-s``
--------------------

Saves to file instead of opening an interactive window. Given a path, the plot is written there;
given with no path at all, a name is generated from the selected vectors, ``--compare`` and
``--x-axis``.

.. code-block:: bash

   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --save rates.png
   opm-vis-sum tests/data/SPE1CASE1 -K FOPR --save

The generated name spells out at most three vectors and then counts the rest, and replaces the
``:`` and ``,`` in a mnemonic with ``-`` - they are ordinary characters in a summary mnemonic but
poor ones in a file name, and ``:`` is invalid on Windows. So a wildcard still gives a usable
name:

.. code-block:: text

   -K FOPR                          FOPR_date.png
   -K 'WOPR:*' --x-axis years       WOPR-INJ_WOPR-PROD_years.png
   -K FOPR --compare                FOPR_compare_date.png
   -K '*'                           BGSAT-1-1-1_BGSAT-1-1-2_BGSAT-1-1-3_and39more_date.png

``--subplots``, ``--layout`` and the axis limits are deliberately not part of the name: they
change how the same data is laid out, not what it is.

The file format follows the extension, as Matplotlib reads it - ``.png``, ``.pdf`` and ``.svg``
all work.
