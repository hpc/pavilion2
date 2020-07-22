.. _tests.scheduling:

Scheduling Tests
================

Tests are scheduled according to which ``scheduler`` they specify. This page
covers the basics of how scheduler plugins operate.

.. contents:: Table of Contents

Included Scheduler Plugins
--------------------------

Pavilion comes with three scheduler plugins:

.. code-block:: bash

    ./bin/pav show sched

     Available Scheduler Plugins
    -----------+------------------------------------------------------
     Name      | Description
    -----------+------------------------------------------------------
     slurm_mpi | Schedules tests via Slurm but runs them using mpirun
     raw       | Schedules tests as local processes.
     slurm     | Schedules tests via the Slurm scheduler.

Scheduler Configuration
~~~~~~~~~~~~~~~~~~~~~~~

The configuration options for each scheduler are documented in their config
file format. This is viewable by using the ``pav show sched --conf`` command.

.. code-block:: bash

    $ pav show sched --conf raw

    # RAW(opt)
    raw:
      # CONCURRENT(opt str): Allow this test to run concurrently with
      #   other concurrent tests under the 'raw' scheduler.
      #   Choices: true, false, True, False
      concurrent: False

These options are placed in test configs in a section named for the scheduler
. (Pavilion 2.3 plans to merge these into a single config section.)

.. code-block:: yaml

    mytest:
        scheduler: raw

        raw:
            concurrent: True

        run:
            cmds:
                - echo "I'm a raw test!"


Scheduler Plugin Basics
-----------------------

Scheduler plugins are responsible for the following:

- providing test runs with *scheduler* variables
- (optionally) writing a kickoff script
- using that kickoff script (or other mechanisms) to then run `pav _run
  <test_run_id>` on an allocation with a reasonable environment.
- Generate a unique scheduler ``job_id`` for the test run.
- Providing a mechanism to cancel tests.
- Providing a mechanism to check the test status.

Scheduler Variables
~~~~~~~~~~~~~~~~~~~

Each scheduler must provide a set of scheduler variables. Many, but not all, of
these will be :ref:`tests.variables.deferred`. The best way to see what
scheduler variables are available is to to use the `pav show sched --vars`
command.

.. code-block:: bash

    $ pav show sched --vars slurm

     Variables for the slurm scheduler plugin.
    -----------------+----------+----------------+------------------------------------------------------
     Name            | Deferred | Example        | Help
    -----------------+----------+----------------+------------------------------------------------------
     alloc_cpu_total | True     | 36             | Total CPUs across all nodes in this allocation.
     alloc_max_mem   | True     | 128842         | Max mem per node for this allocation. (in MiB)
     alloc_max_ppn   | True     | 36             | Max ppn for this allocation.
     alloc_min_mem   | True     | 128842         | Min mem per node for this allocation. (in MiB)
     alloc_min_ppn   | True     | 36             | Min ppn for this allocation.
     alloc_node_list | True     | ['node004',    | A space separated list of nodes in this allocation.
                     |          | 'node005']     |
     alloc_nodes     | True     | 2              | The number of nodes in this allocation.
     max_mem         | False    | 128842         | The maximum memory per node across all nodes (in
                     |          |                | MiB).
     max_ppn         | False    | 36             | The maximum processors per node across all nodes.
    ...


Writing a Kickoff Script
~~~~~~~~~~~~~~~~~~~~~~~~

The kickoff script's job is to have Pavilion run a specific test run under an
allocation. This is generally expected to be a shell script of some sort that
will both define the allocation (if possible) and run ``pav _run <test_run_id>``
within that allocation under an environment that can find Pavilion and its
libraries.

- For the ``raw`` scheduler, the ``kickoff.sh`` script is a simple shell
  script.
- For the ``slurm`` aand ``slurm_mpi`` schedulers, it is an ``sbatch`` script
  that uses top-of-file sbatch directives to configure slurm parameters.

.. code-block:: bash

    #!/bin/bash
    #SBATCH --job-name "pav test #18697"
    #SBATCH -p standard
    #SBATCH -N 3-3
    #SBATCH --tasks-per-node=1

    # Redirect all output to kickoff.log
    exec >/usr/local/pav/working_dir/test_runs/0018697/kickoff.log 2>&1
    export PATH=/usr/local/pav/src/bin:${PATH}
    export PAV_CONFIG_FILE=/usr/local/pav/config/pavilion.yaml
    export PAV_CONFIG_DIR=/usr/local/pav/config

    pav _run 18697

job_id
~~~~~~

The plugin must assign the test run a job id. This will generally be used by
the scheduler plugin to cancel or check the status of tests. It's saved in
the test run's 'job_id' file, and also as part of the test results.

Cancel Mechanisms
~~~~~~~~~~~~~~~~~

Pavilion scheduler plugins are required to provide a mechanism to cancel jobs
managed by that scheduler, whether they're currently running or queued under
the scheduler. Generally this means just using the test_run's job id to
cancel the test. Cancelled tests will be given the 'SCHED_CANCELLED' status.

Status Mechanisms
~~~~~~~~~~~~~~~~~

Similarly, Pavilion scheduler plugins must be able to query the status of
jobs, and give useful feedback on their state in the scheduler. As long as
the test is in the 'SCHEDULED' state from the test run's perspective (in the
run's status file), Pavilion will use the scheduler to look up the schedulers
status for the job, in order to provide more up-to-date test status
information.

