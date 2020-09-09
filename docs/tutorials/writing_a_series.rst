Writing a Series File
=====================

This is a step-by-step tutorial on how to write a series file in Pavilion.

A Test Series is a group of tests that is created whenever the user invokes
``pav run <test names>`` or ``pav run -f <file of test names>``. A series file
allows the user to specify test hierarchies, assign modes to specific tests,
and dictate other settings for tests which are grouped together in the same
series. Creating Test Series in this way also gives the user the option of
running tests in a continuous manner.

.. contents:: Table of Contents

Where to Write Series Files
---------------------------

Series files are yaml files and are placed in the <pav config dir>/series
directory.

Series File Elements
--------------------

Here's an example series file. Let's call it ``sanity_tests.yaml`` and include
tests that are normally run just to make sure the machine works.

.. code-block:: yaml

  # This is the body of the series file. This is where we define test sets,
  # which are groups of tests that we want to apply the same configurations to.
  series:

    # We'll call this test set 'front_end_tests' and run all the tests that
    # don't run on compute nodes with this set.
    front_end_tests:

      # List names of tests
      tests:
        - check_mounts
        - ping_compute_nodes
        - check_commands.front_end

      # List modes that need to be applied to this set of tests
      modes:
        - mode1
        - mode2

      # Define conditions. These will be addd to the only_if/not_if conditions
      # that already exist in each test, if any.
      only_if:
        "{{sys.system_name}}": "machine"

      # Don't run this set if the week day is Friday
      not_if:
        "{{pav.weekday}}": "Friday"

    individual_node_tests:

      # This group of tests depends on the previous set ('front_end_tests').
      # Because 'depends_pass' is set to 'True', this set requires that all the
      # tests in the set this set depends on must PASS in order for this set
      # to be run. The default is that 'depends_pass' is 'False', which means
      # the tests in the set this set depends on need only complete (regardless
      # of whether or not they PASS) in order for this set to run.
      depends_on: ['front_end_tests']
      depends_pass: True

      tests:
        - stream.per_node

    mp_tests:

      modes: ['mode5']

      depends_on: ['front_end_tests']
      depends_pass: True

      tests:
        - stream.mpi
        - supermagic.basic

  # if 'ordered' is set to 'True', then Pavilion will automatically run this
  # series such that each test set depends on the set before that.
  ordered: False

  # The total number of tests that will be run or scheduled at any given time.
  # There is no default setting
  simultaneous: 3

  # series-level modes: These modes will be applied to all sets and therefore
  # all tests
  modes: ['mode3', 'mode4']

  # We want this series to run continuously. The default is 'False', which means
  # the series will run (or attempt to run) each set once only.
  restart: True

Running, Monitoring, and Cancelling the Series
----------------------------------------------

Run `pav show series` to show the list of possible series to run.

To run a series file, the user must use the command
``pav series <series_name>``. To run the series above, we would run
``pav series sanity_tests``. This will output instructions on how to check the
status of and kill the series.

.. code-block:: text

  $ pav series sanity_tests
  Started series s19. Run `pav status s19` to view status. PGID is 9102.
  To kill, use `kill -15 -9102` or `pav cancel s19`.
