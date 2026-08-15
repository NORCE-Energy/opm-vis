opm-vis-rdates
==============

Lists the report steps in a case with their dates and the time since the simulation started,
instead of plotting anything. Dates are read from the restart files (``.UNRST``/``.X``) at day
resolution, so no summary file is needed. See :doc:`cli` for the shared ``PATHS`` convention.

.. code-block:: bash

   opm-vis-rdates tests/data/SPE1CASE1

.. code-block:: text

   Report step        Date  Days  Years
             0  01.01.2015     0  0.000
             1  31.01.2015    30  0.082
   ...
           120  29.12.2024  3650  9.993

Elapsed time is measured from the first report step - report step 0 is written at the start of
the run, so its date is the deck's ``START``. It is given both in days and in years of 365.25
days, matching the ``TIME`` and ``YEARS`` summary vectors.

Each option group below has its own page with a description and a runnable example of every
option in it: :doc:`cli_rdates_input`, :doc:`cli_rdates_rstep`, :doc:`cli_rdates_output`.

The same timeline is available from Python through
:class:`~opm_vis.utils.restart.Report` - see :doc:`examples`.

Option reference
----------------

.. click:: opm_vis.cli.rdates_cli:main
   :prog: opm-vis-rdates

.. toctree::
   :maxdepth: 1
   :caption: Option reference
   :hidden:

   cli_rdates_input
   cli_rdates_rstep
   cli_rdates_output
