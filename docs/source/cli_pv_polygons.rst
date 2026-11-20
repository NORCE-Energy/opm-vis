Polygons
=========

``--polygon``
---------------

File with polygons to draw (repeatable), such as licence boundaries, plume outlines or
seismic lines. Points with a depth (``x y z``) are drawn where they are. Outlines with only
``x y`` are drawn flat at the top of the grid - not following its shape - and are left out of a
``--view 2d`` i- or j-slice, where they would only be seen edge-on.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX -k 1 \
       --polygon tests/data/SPE1CASE1/SPE1CASE1_POLYGONS.geojson
   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX --view 3d \
       --polygon outlines.npz --polygon wells_area.csv

Polygon files are read by their extension:

- ``.npy``: one polygon as an ``(n, 2)`` or ``(n, 3)`` array, or a stack of several, shape
  ``(m, n, 2|3)``.
- ``.npz``: one polygon per array, named by its key.
- ``.txt``, ``.csv``, ``.dat``, ``.xyz``: columns ``x y [z]``, separated by whitespace or commas,
  with a blank line between polygons. Lines starting with ``#`` are comments, and a header row
  such as ``x,y,z`` is skipped.
- ``.geojson``, ``.json``: ``Polygon``, ``MultiPolygon``, ``LineString`` and ``MultiLineString``
  geometries, named by each feature's ``name`` property.

Points are in the same coordinates the grid is drawn in (world coordinates when the grid has
``MAPAXES``), with ``z`` as depth, positive down. Polygons from NumPy and text files are closed
automatically; GeoJSON line strings are kept open. A polygon is named after its file, numbered
if the file holds several, unless the format gives it a name; each name is drawn as a label.

A polygon lying entirely outside the plotted grid gives a warning naming it and its file, since
it would otherwise be drawn out of sight with no sign of what went wrong. The usual cause is a
file in other units - e.g. kilometres for a grid in metres. Note that axes wider than 1 km are
labelled in km, but the coordinates underneath, and so the polygon points, are still metres.

``--polygon-color``
---------------------

Colour of the polygon lines and labels. Default: ``red``.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX -k 1 \
       --polygon tests/data/SPE1CASE1/SPE1CASE1_POLYGONS.geojson --polygon-color white

``--polygon-linewidth``
-------------------------

Thickness of the polygon lines, in pixels. Default: 3.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX -k 1 \
       --polygon tests/data/SPE1CASE1/SPE1CASE1_POLYGONS.geojson --polygon-linewidth 5

``--polygon-label``
---------------------

Label for the polygons of one ``--polygon`` file, replacing their own names. Given once per
``--polygon``, in the same order; ``""`` leaves that file unlabelled.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX -k 1 \
       --polygon boundary.npy --polygon-label "Storage unit" \
       --polygon tests/data/SPE1CASE1/SPE1CASE1_POLYGONS.geojson --polygon-label ""

``--polygon-labels`` / ``--no-polygon-labels``
------------------------------------------------

Labels each polygon (default), or draws the polygons with no labels at all.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K PERMX -k 1 \
       --polygon tests/data/SPE1CASE1/SPE1CASE1_POLYGONS.geojson --no-polygon-labels
