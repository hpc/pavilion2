.. _tests.scheduling:

Scheduling Tests
================

Tests are scheduled according to which ``scheduler`` they specify. This page
covers the basics of how scheduler plugins operate.

.. contents:: Table of Contents

Included Scheduler Plugins
--------------------------

Pavilion comes with two scheduler plugins:

.. code-block:: bash

    pav show sched

     Available Scheduler Plugins
    -----------+------------------------------------------------------
     Name      | Description
    -----------+------------------------------------------------------
     raw       | Schedules tests as local processes.
     slurm     | Schedules tests via the Slurm scheduler.

Scheduler Configuration
~~~~~~~~~~~~~~~~~~~~~~~

The configuration options for schedulers are documented in their config
file format. This is viewable by using the ``pav show sched --conf`` command.

.. code-block:: bash

    $ pav show sched --conf raw

The listed options all go in the ``schedule`` section of a test config.
You may also notice scheduler specific sections in the listed options as well. Those
allow for custom configuration specific to a particular schedulers - options that are
not generally applicable.

Note that all options are expected to be generally applicable either. We may, in the future,
add a scheduler with concept of a QOS setting, for instance. Such settings are simply ignored
in those cases.

.. code-block:: yaml

    mytest:
        scheduler: slurm

        schedule:
            nodes: 5

        run:
            cmds:
                - echo "I'm a slurm test!"


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

.. _tests.scheduling.variables:

Scheduler Variables
~~~~~~~~~~~~~~~~~~~

Each scheduler must provide a set of scheduler variables. Most of these are
generic and available across all schedulers. Some of
these will be :ref:`tests.variables.deferred`. The best way to see what
scheduler variables are available is to to use the ``pav show sched --vars <sched_name>``
command.

.. code-block::

    $ pav show sched --vars slurm

     Variables for the slurm scheduler plugin.
    ----------------+----------+-----------------+------------------------------------------------------
     Name           | Deferred | Example         | Help
    ----------------+----------+-----------------+------------------------------------------------------
     chunk_ids      | False    | []              | A list of indices of the available chunks.
     errors         | False    | []              | Return the list of retrieval errors encountered when
                    |          |                 | using this var_dict. Key errors are not included.
     min_cpus       | False    | 1               | Get a minimum number of cpus available on each
                    |          |                 | (filtered) noded. Defaults to 1 if unknown.
     min_mem        | False    | 4294967296      | Get a minimum for any node across each (filtered)
                    |          |                 | nodes. Returns a value in bytes (4 GB if unknown).
     node_list      | False    | []              | The list of node names on the system. If the
                    |          |                 | scheduler supports auto-detection, will be the
                    |          |                 | filtered list. This list will otherwise be empty.
     node_list_id   | False    |                 | Return the node list id, if available. This is
                    |          |                 | meaningless to test configs, but is used internally
                    |          |                 | by Pavilion.
     nodes          | False    | 1               | The number of nodes available on the system. If the
                    |          |                 | scheduler supports auto-detection, this will be the
                    |          |                 | filtered count of nodes. Otherwise, this will be the
                    |          |                 | 'cluster_info.node_count' value, or 1 if that isn't
                    |          |                 | set.
     tasks_per_node | True     | 5               | The number of tasks to create per node. If the
                    |          |                 | scheduler does not support node info, just returns
                    |          |                 | 1.
     tasks_total    | True     | 180             | Total tasks to create, based on number of nodes
                    |          |                 | actually acquired.
     launch         | True     | srun -N 5 -w no | Construct a cmd to run a process under this
                    |          | de[05-10],node2 | scheduler, with the criteria specified by this test.
                    |          | 3 -n 20         |

.. _tests.scheduling.jobs:

Jobs
----

When Pavilion schedules a test, it also creates a job. Jobs organize all the information used
to kick off a test (or tests!), including the kickoff script, kickoff log, job id, and symlinks
back to each test that's part of the job. Each job is named by a random hash located in the
``working_dir>/jobs`` directory. Tests also refer back to their job through a symlink in each
test run directory.

The Kickoff Script
~~~~~~~~~~~~~~~~~~

The kickoff script's job is to have Pavilion run specific test run instances under an
allocation. This is generally expected to be a shell script of some sort that
will both define the allocation (if possible) and run ``pav _run <test_run_id>``
within that allocation under an environment that can find Pavilion and its
libraries.

For slurm, the kickoff script would look something like this:

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
the job's 'job_id' file, and also as part of the test results.

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
the test is in the 'SCHEDULED' or 'RUNNING' states from the test run's perspective (in the
run's status file), Pavilion will use the scheduler to look up the schedulers
status for the job, in order to provide more up-to-date test status
information.

.. _tests.scheduling.types:

Scheduler Plugin Types
----------------------

Scheduler plugins come in two varieties: Basic and Advanced

Basic
~~~~~

**The only 'basic' scheduler is 'raw' which only ever has one node. Most of this doesn't apply
except to user added schedulers.**

Basic Schedulers don't know anything about the system that isn't manually configured. This
information is given via the ``schedule.cluster_info`` section (see ``pav show sched --config``).
This information should generally be set in the host config for a particular system.

Asking for 'all' nodes on a _Basic_ scheduler will result in an allocation for the
configured number of nodes, regardless of the state of those nodes.

.. code-block:: yaml

    mytest:
      schedule:
        # Tell the scheduler that this system has 60 nodes (at peak)
        cluster_info:
          node_count: 60
        # Ask for between 90% (56 nodes) and all 60 nodes
        # This gives some flexibility in case some nodes are down.
        min_nodes: '90%'
        nodes: all

Advanced
~~~~~~~~

Advanced scheduler plugins are plugins that can get an inventory of nodes and node state
from the system. Such schedulers are able to dynamically determine how many nodes are up or
available, and create allocations based on that. As a result, asking for 'all' nodes via an
advanced scheduler will get you an allocation request for all nodes that are currently up and not
otherwise filtered out by ``partition`` or other scheduler settings.

Advanced schedulers also enable chunking and job sharing.

.. _tests.scheduling.job_sharing:

Job Sharing
-----------

On an advanced scheduler, when two tests have the same job parameters, they are automatically
scheduled together in the same job allocation. The kickoff script for that job will start the
tests serially, and the result of each test run does not effect the others.

Job sharing makes the most sense for short tests that cover a wide range of nodes - such tests
often take longer to set up the allocation than they do to run.

This is enabled by default. It can be disabled through the ``schedule.share_allocation`` option.

.. _tests.scheduling.chunking:

Chunking
--------

On an advanced scheduler, the ``chunking`` section of the ``schedule`` configuration enables
powerful tools for dividing up a system to test it piece by piece. It is disabled when the chunk
size is equal to all nodes on the system (the default), but can be enabled by selecting a
specific chunk size.

.. code-block:: yaml

    mytest:
      schedule:
        # When using chunking, this is relative to the chunk and not the whole system.
        nodes: all

        # Get 500 node chunks
        chunking:
          size: 500

When using chunking nodes are selected for each job entirely in advance by Pavilion. This can lead
to the tests being a bit more fragile than usual - the failure of a single node can keep a test
from running even if the are 'spare' nodes outside of the chunk.

Chunk Selection
~~~~~~~~~~~~~~~

By default, Pavilion will assign each test to the least used chunk for a given set of tests. This
will distribute your tests evenly across the entire system.

You can, however, specify a specific chunk for each test, or even create permutations of a test
such that it will one once on each chunk. The ``sched.chunk_ids`` scheduler variable contains a
list of all available chunks ids for a test, and can be used in combination with the ``chunk``
setting to specify a chunk.

**Note: It is not generically safe to specify chunks other than chunk '0', as chunks above
zero aren't guaranteed to exist.**

.. code-block:: yaml

    # This will create an instance of this test for every chunk available, giving
    # full coverage of the system.
    mytest:
      permute_on: chunk_ids

      chunk: '{{chunk_ids}}'
      schedule:
        # When using chunking, this is relative to the chunk and not the whole system.
        nodes: all

        # Get 500 node chunks
        chunking:
          size: 500

Node Selection
~~~~~~~~~~~~~~

By default, Pavilion selects (near) contiguous blocks of nodes for each chunk, but this is
customizable. Instead, you can select nodes randomly for each chunk (random), distributed across the
system (dist), or semi-randomly distributed (rand-dist). Regardless of the node selection method,
the number of chunks will be the same and they (mostly) won't overlap.

It is very likely that the chunk size won't align precisely with the number of nodes that are to
be divided into chunks. These 'extra' nodes may be excluded or back-filled with nodes from another
chunk (they always come from the second to last chunk). The default is to 'backfill'.

These are set via the ``schedule.chunking.node_selection`` and ``schedule.chunking.extra`` options.

.. code-block:: yaml

    # This test run over a random selection of 25% of the nodes on the system.
    mytest:
      schedule:
        # When using chunking, this is relative to the chunk and not the whole system.
        nodes: all

        # Get 500 node chunks
        chunking:
          size: 25%
          node_selection: random

.. _tests.scheduling.wrapper:

Wrapper
-------

You can use the wrapper feature on any scheduler to wrap the scheduler test command and run the
wrapper command before actually running the intended command.

.. code-block:: yaml

    basic:
        scheduler: slurm
        schedule:
            wrapper: valgrind
            partition: standard
            nodes: 1

        run:
            cmds:
                # The run command will be `srun -N1 -p standard valgrind ./supermagic -a`
                # It will run `valgrind ./supermagic -a` on the allocation
                - '{{sched.launch}} ./supermagic -a'

When using the ``raw`` scheduler, the ``{{sched.launch}}`` normally returns an empty string. You can 
use the wrapper setting to control a different scheduler directly.

.. code-block:: yaml

    shoot_yourself_in_the_foot_mode:
        scheduler: raw
        schedule:
            # Note that generally it's MUCH better to use the Pavilion's scheduling options,
            # but this allows you to, for example, test the scheduler itself.
            # Other note - You can use mpirun under slurm by setting ``schedule.slurm.mpi_cmd=mpirun``.
            wrapper: 'mpirun -np 2'
        run:
            cmds:
                # With the schedule wrapper, this will be `mpirun -np 2 ./supermagic -a`
                - '{{sched.launch}} ./supermagic -a'

