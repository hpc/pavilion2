Running Tests
=============

This page covers how the test ``run`` section is used to create the test
run script, and what the lifecycle of a test actually looks like.

-  `Run Configuration <#run-configuration>`__
-  `Test Run Lifecycle <#test-run-lifecycle>`__

Run Configuration
-----------------

The run section of the test config is used to generate a ``run.sh``
script, which runs the actual test. It's fairly simple, as most of the
work involved in getting ready to run the test is configured separately.

How these are used to compose a `run script is covered
below <#create-the-run-script>`__.

There are four attributes:

-  `modules <#modules-list>`__ - Add/remove/swap modules.
-  `env <#env-mapping>`__ - Alter environment variables
-  `create_files <#create\_files-list>`__ - Create files at run time.
-  `cmds <#cmds-list>`__ - Run these commands.

modules (list)
^^^^^^^^^^^^^^

Modules to ``module load`` (or swap/remove) from the environment using
your cluster's module system.

For each module listed, a relevant module command will be added to the
build script.

See `Module Environment <env.html#modules>`__ for more info.

env (mapping)
^^^^^^^^^^^^^

A mapping of environment variable names to values.

Each environment variable will be set (and exported) to the given value
in the build script. Null/empty values given will unset. In either case,
these are written into the script as bash commands, so values are free
to refer to other bash variables or contain sub-shell escapes.

See `Env Vars <env.html#environment-variables>`__ for more info.

create\_files (list)
^^^^^^^^^^^^^^^^^^^^

File(s) to be created at runtime.

- Each string is a file to be generated and populated with a list of strings
  as file contents at runtime.
- The file string must be a path contained within the test's build directory;
  paths that would otherwise result in writing outside this directory will
  result in an exception at test finalize time.
- variables and deferred variables are allowed.

.. code:: yaml

    run_example:
        build:
            variables:
                page:
                    - {module: 'craype-hugepages2M', bytes: '2097152'}
        run:
            create_files:
                # Create file, "data.in", in the build directory at runtime.
                - data.in
                    - 'line 1'
                    - 'line 2'
                    - 'line 3'

                # Create file, "data.in", inside subdirectory "subdir". Note if
                # the subdirectory(ies) do not exist they will be created.
                - ./subdir/data.in
                    - 'line 1'
                    - 'line 2'
                    - 'line 3'

                # Create file, "var.in", with 'page' variable data inside nested
                # subdirectory "subdir/another_subdir".
                - ./subdir/another_subdir/var.in
                    - 'module = {{page.module}}'
                    - 'size = {{page.bytes}}'

                # Create file, "defer.in", with deferred variables.
                - defer.in
                    - system_name = {{sys.name}}
                    - system_os = {{sys.os}}

cmds (list)
^^^^^^^^^^^

The list of commands to perform when running the test.

-  Each string in the list is put into the run script as a separate
   line.
-  The return value of the last command in this list will be the return
   value of the run script.

   -  The run script return value is one way to denote build success
      or failure.

-  If your script failures don't cascade (a failed ``./configure``
   doesn't result in a failed ``make``, etc), append ``|| exit 1`` to
   your commands as needed. You can also use ``set -e`` to exit on any
   failure.

Test Run LifeCycle
------------------

Every test run in Pavilion undergoes the same basic steps.

1. `Create a Test Instance <#creating-the-test-run>`__
2. `Create the Run Script <#create-the-run-script>`__
3. `Schedule the Test <#scheduling-a-test>`__
4. `Build the Test Source <build.html>`__
5. `Run the Test Script <#running-run-sh>`__
6. `Process Test Results <#gathering-results>`__
7. `Set the Test as complete <#set-the-test-run-as-complete>`__

Each of these steps has a corresponding test **state**, which is used to
monitor the progress of each test.

.. figure:: ../imgs/test_lifecycle.png
   :alt: Running a Test

   Running a Test

Disambiguation
^^^^^^^^^^^^^^

Note the difference between a 'test suite', 'test config', and a 'test
run'. - A 'test suite' is a config file that can contain multiple raw
'test configs' - A 'test config' is the set of attributes used to define
a test. - A finalized 'test config' is the config with all the
variables, permutations, and other bits resolved. - A 'test run' is a
finalized 'test config' turned into an actual, running test. - A 'test
series' is one or more 'test runs' that were started as a single
invocation of the ``pav run`` command.

This section of the documentation covers the lifecycle of a single 'test
run'.

Creating the Test Run
~~~~~~~~~~~~~~~~~~~~~

Each test run created in Pavilion is given a unique **ID**. This **ID**
corresponds to a directory in ``<working_dir>/test_runs``, which contains
everything there is to know about a test.

.. figure:: ../imgs/test_run_dir.png
   :alt: Test Run Directory

   Test Run Directory

<run_id>/**status**
  Contains all the statuses that a test has had. The last
  listed is the current test status.
<run_id>/**config**
  The finalized configuration for the test run, in json.
<run_id>/**job\_id**
  The job\_id assigned by the scheduler. The format depends on the scheduler
  plugin.
<run_id>/**kickoff.sh**
  The kickoff script, written by the scheduler plugin.
  This simply calls pavilion again to run this particular test inside
  of an allocation. The extension may vary depending on the scheduler
  plugin.
<run_id>/**build.sh**
  The `build script <build.html#create-a-build-script>`__.
<run_id>/**run.tmpl**
  A dummy run script Pavilion creates to make sure your test run config makes
  sense. It may have deferred variables inserted with a placeholder.
<run_id>/**run.sh**
  The final run script.
<run_id>/**variables**
  All of the variables your test had access to when it was created. This is
  updated with deferred variable values when your test runs on an allocation.
<run_id>/**(kickoff/build/run).log**
  The stdout and stderr of each of the above scripts when they were run.
<run_id>/**build**
  The build directory. The test will run within this directory.

  - The files in here are softlinks to the
    `actual build <build.html#copy-the-build>`__.
<run_id>/**RUN_COMPLETE**
  Created when the run has completed, and contains just the completion time.
<run_id>/**result.json**
  The json of the test results.

Create the Run Script
~~~~~~~~~~~~~~~~~~~~~

Pavilion will create a dummy runs script as ``run.tmpl`` soon as the test run
object is created. If your run config contained deferred variables, this will
be filled in with a placeholder.

The real ``run.sh`` script is only generated right before your test is created.

.. code:: yaml

    run_example:
        build:
          source_location: run_example

        run:
          modules: [python]
          env:
            PYTHONPATH: ./libs

          cmds:
            # Host CPU's is a deferred variable.
            - python run_example.py {{sys.host_cpus}}

would result in a run script that looks like:

.. code:: bash

    #!/bin/bash

    # This contains utility functions used in Pavilion scripts.
    source /home/bob/pavilion/bin/pav-lib.bash

    # Load the modules, and make sure they're loaded
    module load python
    check_module_loaded python

    # Set environment variables
    export PYTHONPATH=./lib

    # Run the test cmds
    python run_example.py 12

Scheduling a Test
~~~~~~~~~~~~~~~~~

When you run a 'test series', each test is scheduled separately and gets
a separate allocation. Pavilion leaves it up to the scheduler plugin,
and the scheduler itself, to handle exactly when and how a test is
scheduled. Each test's scheduler configuration section determines the
exact setting used by the scheduler plugin when scheduling a test.

Generally speaking, scheduler plugins write a **kickoff** script and
tell their scheduler to run that script. These scripts simply use
Pavilion to perform the actual test run for the specific test ID using
the super-secret ``pav _run <run id>`` command.

.. code:: bash

    #!/bin/bash
    #SBATCH --job-name "pav test #3"
    #SBATCH -p standard
    #SBATCH -N 2-2
    #SBATCH --tasks-per-node=2

    # Redirect all output to kickoff.log
    exec >/usr/projects/hpctest/pav2/working_dir/test_runs/0000003/kickoff.log 2>&1
    export PATH=/home/bob/pavilion/src/bin:${PATH}
    export PAV_CONFIG_FILE=/home/bob/.pavilion/pavilion.yaml
    pav _run 3

slurm
^^^^^

For the existing **slurm** scheduler, this means writing an sbatch
script (``kickoff.sbatch``) and scheduling it via the sbatch command.
Since the slurm sbatch script allows us to set all options within the
script header, we do so to allow for easier debugging of Pavilion.

It's up to the Pavilion user to make sure the test's slurm settings are
such that the test will eventually get an allocation.

raw
^^^

The **raw** scheduler simply runs tests as an independent sub-process.
It can let them all run simultaneously, or limit them to one-at-time
depending on the scheduler settings.

Running run.sh
~~~~~~~~~~~~~~

Within the ``pav _run`` command, after we've `built the test
src <build.html>`__ and resolved ``run.tmpl`` into the final ``run.sh``
script, we simply have to run it.

-  The script is run in the default login environment of the user.
-  The return value of the script, which is the return value of the
   script's last command by default, is the default PASS/FAIL result of
   the script.

Gathering Results
~~~~~~~~~~~~~~~~~

After the test completes, Pavilion gathers the results. It does this
whether the test passed or failed, but not if Pavilion encountered an
error during the run.

The results, both those gathered by default and through result parsers,
are compiled into a single JSON object and written to ``results.txt``,
and logged to the `result log <../config.html#result-log>`__.

Set the Test Run as Complete
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lastly, the test run is set as complete, regardless of whether it
passed, failed, or encountered an error. Note that this is separate from
the status file; a file named 'RUN\_COMPLETE' is created in the test run
directory. The file contains only a timestamp of when the run officially
ended. Various commands can use this as an easy way to differentiate
complete tests from those that may still be running.
