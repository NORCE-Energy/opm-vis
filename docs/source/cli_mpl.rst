opm-vis-mpl
===========

The alternative Matplotlib backend's command-line tool, drawing each cell as a flat quad instead
of real geometry. It is less developed than :doc:`cli_pv` and covers a smaller subset: one slice
at a time, no wells, no glyphs, no thresholding or clipping, and no whole-grid view. See
:doc:`cli` for the shared ``PATHS`` convention and 1-based ``-i``/``-j``/``-k`` indexing.

Each option group below has its own page with a description and a runnable example of every
option in it: :doc:`cli_mpl_input`, :doc:`cli_mpl_grid_only`, :doc:`cli_mpl_slicing`,
:doc:`cli_mpl_rstep_animation`, :doc:`cli_mpl_diff`, :doc:`cli_mpl_calculator`,
:doc:`cli_mpl_view`, :doc:`cli_mpl_output`. This backend supports a smaller option set than
:doc:`cli_pv` - see its option pages for wells, glyphs, thresholding and clipping, none of which
are available here.

Option reference
----------------

.. click:: opm_vis.cli.plot_cli:main
   :prog: opm-vis-mpl

.. toctree::
   :maxdepth: 1
   :caption: Option reference
   :hidden:

   cli_mpl_input
   cli_mpl_grid_only
   cli_mpl_slicing
   cli_mpl_rstep_animation
   cli_mpl_diff
   cli_mpl_calculator
   cli_mpl_view
   cli_mpl_output
