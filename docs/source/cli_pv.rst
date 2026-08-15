opm-vis-pv
==========

The PyVista backend's command-line tool. It renders the grid as real VTK geometry, with an
interactive camera, wells, vector glyphs, thresholding, clipping and animation - the full option
set. See :doc:`cli` for the shared ``PATHS`` convention and 1-based ``-i``/``-j``/``-k``
indexing.

Each option group below has its own page with a description and a runnable example of every
option in it: :doc:`cli_pv_input`, :doc:`cli_pv_grid_only`, :doc:`cli_pv_slicing`,
:doc:`cli_pv_rstep_animation`, :doc:`cli_pv_diff`, :doc:`cli_pv_calculator`, :doc:`cli_pv_view`,
:doc:`cli_pv_wells`, :doc:`cli_pv_appearance`, :doc:`cli_pv_threshold`, :doc:`cli_pv_clip`,
:doc:`cli_pv_glyphs`, :doc:`cli_pv_output`.

Option reference
----------------

.. click:: opm_vis.cli.pvplot_cli:main
   :prog: opm-vis-pv

.. toctree::
   :maxdepth: 1
   :caption: Option reference
   :hidden:

   cli_pv_input
   cli_pv_grid_only
   cli_pv_slicing
   cli_pv_rstep_animation
   cli_pv_diff
   cli_pv_calculator
   cli_pv_view
   cli_pv_wells
   cli_pv_appearance
   cli_pv_threshold
   cli_pv_clip
   cli_pv_glyphs
   cli_pv_output
