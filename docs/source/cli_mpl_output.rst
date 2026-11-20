Output
=======

``--save``, ``-s``
--------------------

Saves to a file instead of opening an interactive window. The file name is generated from the
keyword, slice and report step(s), e.g. ``SGAS_k1_r60.png`` or ``SGAS_k1_r0-120.gif``. Images
go in ``mpl-figs/`` and animations in ``mpl-gifs/``, inside the case's ``-f``/``--folder``
(the first one, if several are given; the current folder if none), unless ``--save-folder``
says otherwise.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save
   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 --animate --save

``--save-name``, ``-sn``
-------------------------

File name to save to instead of the generated one, without its suffix: ``.png`` for an image or ``.gif`` for an animation is added
to match the format, unless the name already ends with it. The folder is ``--save-folder``'s
(or its default), so the name cannot hold a folder of its own. Giving it implies ``--save``.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -sn top_layer
   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -sf results -sn top_layer

``--save-folder``, ``-sf``
---------------------------

Folder to save to, instead of the default ``mpl-figs/`` (images) or ``mpl-gifs/``
(animations) inside the case folder. A relative path is taken from the current folder, not the
case folder. Giving it implies ``--save``. A folder that does not exist yet is created,
along with any missing parent folders, and the program prints ``Created folder <path>`` when it
does so.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -sf results/plots
