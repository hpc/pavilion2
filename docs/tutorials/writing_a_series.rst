.. _tutorials.series:

Writing a Series File
=====================

A test series is a group of interrelated test runs. While tests started together
via ``pav run`` are automatically grouped together as a simple series, more
complex relationships are possible by explicitly defining a series with a test
series config file. A series file allows the user to specify test hierarchies,
assign modes to specific tests, and dictate other settings for the group of
tests. Creating a test series in this way also gives the user the option of
limiting the number of tests running or scheduled at any given time and running
the tests in a continuous manner.

.. contents:: Table of Contents

Where to Write Series Files
---------------------------

Series configs are yaml files and are placed in the ``<pav config dir>/series``
directory. Like all the other config files in Pavilion, the config file name
must follow the format ``<series name>.yaml``.

Series Configuration
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

      # Names of the tests that will run as part of this test set.
      # The ordering of these tests (relative to each other) is generally up to
      # the scheduler.
      tests:
        - check_mounts
        - ping_compute_nodes
        - check_commands.front_end

      # List modes that need to be applied to this set of tests
      modes:
        - fe_settings
        - maintenance_testing

      # Define conditions. These will be added to the only_if/not_if conditions
      # that already exist in each test, if any.

      # Only run this test if it's being run on the machine 'blue_cluster'
      only_if:
        "{{sys.sys_name}}": "blue_cluster"

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

      # The 'mpi8.yaml' mode file will be applied to each of the tests in
      # this group.
      modes: ['mpi8']

      depends_on: ['front_end_tests']
      depends_pass: True

      tests:
        - stream.mpi
        - supermagic.basic

  # if 'ordered' is set to 'True', then Pavilion will automatically run this
  # series such that each test set depends on the set before that.
  ordered: False

  # The total number of tests that will be run or scheduled at any given time.
  # default: no limit
  simultaneous: 3

  # series-level modes: These modes will be applied to all sets and therefore
  # all tests
  modes: ['all_partitions', 'all_nodes']

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
  To kill, use `pav cancel s19` or `kill -15 -9102`.
