Writing Your First Test
=======================

This is a step-by-step tutorial on how to write your first test in Pavilion.

.. contents:: Table of Contents


Preliminary Steps
-----------------

1.  `Install Pavilion on a Cluster <../install.html>`__
2.  Setup your environment for Pavilion.

    - We usually do this with a module file (lmod or env modules).

      - Set PAV_CONFIG_DIR to your Pavilion config directory.
      - Add the pavilion ``bin/`` directory to your path.
3.  Run ``pav show config`` to verify that pavilion is basically working.
4.  `Configure Pavilion <../config.html>`__
5.  Create your ``~/.pavilion`` directory.

Where to Write Your Tests
-------------------------

When writing a test, you should generally work out of your ``~/.pavilion/tests``
and ``~/.pavilion/test_src`` directories. When your test is ready, then move it
to the general Pavilion config directories. This generally helps keep your
production Pavilion config directories clean of half finished and broken tests.

Any tests found in your ``~/.pavilion`` directory will take precedence over
those found in the general Pavilion config directory.

Writing a Test
--------------

.. _supermagic: https://github.com/hpc/supermagic

We're going to use the `supermagic`_ hpc test as our example.


1. Download an archive of the source.

   - Put it in ``~/.pavilion/test_src``
2. Create a file called ``~/.pavilion/tests/supermagic.yaml``

My ``~/.pavilion`` directory structure now looks like this:

.. code-block:: text

    test_src/
        supermagic-master.zip
    tests/
        supermagic.yaml

The ``tests/supermagic.yaml`` file is a test **suite**. It's meant to
contain multiple test configurations, generally of the same base test. Let's
add to it:

.. code-block:: yaml

    # This is the name of your test. The full name of this test would be
    # 'supermagic.basic'.
    basic:

        # This will display as the test summary when you run 'pav show tests'
        summary: A basic supermagic run.

        # This section defines how the test is built, mainly by detailing how
        # to write a 'build.sh' script.
        build:
            # Pavilion will auto-extract this archive. The extracted directory
            # will be your build directory.
            source_location: supermagic-master.zip

            # Each of these commands is added as a separate line to the
            # build script.
            cmds:
                - gcc -o supermagic supermagic.c

        # The run section defines how the create the 'run.sh' script.
        run:
            cmds:
                # Each of these commands will be inserted into our run script.
                - ./supermagic

Use the command '``pav show tests``' to get a list of all known tests, including
yours.

Note:
  The above config won't work, but that's intentional. We'll fix it over the
  course of this tutorial.

.. code-block:: shell

    $ pav show tests

    -----------------+------------------------
     Name            | Summary
    -----------------+------------------------
    supermagic.basic | A basic supermagic run.

If your suite or test is highlighted in red and/or followed by an asterisk,
there was an error in your config. Use '``pav show tests --err``' to get
information on what and where the problem is in your yaml file.


Test Building
~~~~~~~~~~~~~

The combined cryptographic hashes of the build source and build script will
be the build name in <working_dir>/builds.

For instance, if our build hash is 'ac3251801d831', we'll end up with a
build directory like this:

.. code-block:: text

    <working_dir>/ac3251801d831/
        Makefile.am
        supermagic.c
        supermagic.h
        util/
            ...
        ...

We'll also end up with a build script that looks like this:

.. code-block:: bash

    #!/bin/bash

    # The first (and only) argument of the build script is the test id.
    export TEST_ID=${1:-0}
    export PAV_CONFIG_FILE=/home/bob/pav2/config/pavilion.yaml
    source /home/bob/pav2/src/bin/pav-lib.bash

    # Perform the sequence of test commands.
    gcc -o supermagic supermagic.c

When building the test Pavilion will run that script in the extracted build
directory.

Let's try it:

.. code-block:: shell

    $ pav run supermagic.basic
    Test supermagic.basic run 72 building 787aceaa19ac9a21

    Error building test:
    status BUILD_FAILED - Build returned a non-zero result.
    For more information, run 'pav log build 72'

Oh no! Our build failed. Let's follow the suggestion, and look at the build
log for our test. We can also use '``pav cat 72 build.sh``' to output the build
script itself too.

Note:
  Your test run number will be different.

.. code-block:: shell

    $ pav log build 72

    In file included from supermagic.c:20:0:
    supermagic.h:78:17: fatal error: mpi.h: No such file or directory
     #include "mpi.h"
                 ^
    compilation terminated.

Loading a Reasonable Compiler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We tried to build with gcc, but supermagic requires an mpi compiler wrapper.
We'll have to provide that somehow. Typically that's done with module files.
So let's modify the build section of our test config to load those modules.

Note:
  Module loading works with lmod and environment modules (tmod), and
  assumes the module environment is set up automatically on login. This is
  covered in more details in the
  `install instructions <../install.html>`__.

.. code-block:: yaml

    build:
        # In our environment, we would load a compiler module and an
        # mpi module. Your environment is probably different.
        # Note that we can just use the module default (like with gcc),
        # or specify a version (like with openmpi).
        modules: [gcc, openmpi/2.1.2]
        # We can also set environment variables. In this case we want to
        # set CC to 'mpicc' so the configure script knows which compiler
        # to use.
        env:
            CC: mpicc

        source_location: supermagic-master.zip
        cmds:
            # We must use autotools to write our configure script
            - ./autogen

            # Then run that configures script to generate our Makefile.
            - ./configure

            # Then finally simply run make.
            - make

Now try running your test again, and look at both the build log and build
scripts. If you've set up your modules correctly, the test should build. It
will probably fail to run, but we'll fix that next. If it still fails to
build, check the build log and the build script itself.

.. code-block:: shell

    $ pav run supermagic.basic
    Test supermagic.basic run 19 building 990e7094373e28c1
    1 test started as test series s81.

    $ pav log build 19
    $ pav cat 19 builds.h

Pavilion also saves failed builds in the test run's directory. These
will be in ``<working_dir>/test_runs/<test_run_id>/build``. From there you can
run and debug the build script directly.

Successful Builds
^^^^^^^^^^^^^^^^^

Successful builds are reused by multiple tests runs. Instead of copying their
contents, Pavilion instead recreates their directory structure and makes
symlinks to the individual files. The test run script will run in this
'simulated' build directory, and is free to delete, add, or overwrite any
files in the build it wants. The run scripts can't append to or otherwise
edit the files though!


Getting the Test to Run
-----------------------

Now that our test has built, let's actually try to get it to run. That's
going to involve a scheduler. We need to configure our test to so it knows
what scheduler resources ask for.

Note:
    This tutorial uses Slurm as the scheduler, mainly because that's the only
    one (other than raw/local scheduling) that Pavilion supports.
    Fortunately, Pavilion was designed pretty generically where schedulers
    are concerned, and schedulers are simply another type of Pavilion plugin.
    If you use a different scheduler, we'd love to help add a Pavilion plugin
    for it. Just contact the Pavilion developers via github.

Add the following to your supermagic test config:

.. code-block:: yaml

    basic:

        # We'll just configure slurm to use two nodes, and two processes each.
        # We could also put in a range, or even 'all'.
        slurm:
            num_nodes: 2
            tasks_per_node: 2

        # Tell pavilion to use the slurm scheduler for this test.
        scheduler: slurm

        run:
            # Odds are good that your program will need to find your openmpi
            # libs at run time.
            modules: ['gcc', 'openmpi/2.1.2']

            cmd:
                # We'll go over this in a second.
                - '{{sched.test_cmd}} ./supermagic'

Kickoff Scripts
~~~~~~~~~~~~~~~

Every scheduler writes a kickoff script and saves it in the test's run
directory. This script is expected to be the root process of the scheduled
job. It should set up a reasonable environment, and then runs any Pavilion tests
that need to run in that allocation. Our kickoff script for the above test
might look like this (with extra comments):

.. code-block:: bash

    #!/bin/bash

    # Slurm kickoff scripts are an sbatch script. All the sbatch configuration
    # is done in the script header for consistency.
    #SBATCH --job-name "pav test #20"
    #SBATCH -p standard
    #SBATCH -N 2-2
    #SBATCH --tasks-per-node=2

    # Redirect all output to kickoff.log
    exec >/users/pflarr/.pavilion/working_dir/test_runs/0000020/kickoff.log 2>&1

    # Set the path so we can find the pavilion command that started this test.
    export PATH=/yellow/usr/projects/hpctools/pflarr/repos/pavilion/bin:${PATH}

    # Point pavilion to the config file that configured it.
    export PAV_CONFIG_FILE=None

    # Actually run this particular test in the allocation.
    pav _run 20

The most important bit here is the '``pav _run 20``' line. This starts pavilion
up again, within the allocation, to start our test run. From there it will
load the test and eventually run it's 'run.sh' script.

The kickoff log is also available to view with the
'``pav log kickoff <run_id>``' command. Unless you have bad scheduler options,
that log is typically empty.

Run Scripts
~~~~~~~~~~~

Pavilion generates a run script for every test run as well. Just like with
build scripts, it's composed of the module loads, environment variable
exports, and finally the run commands themselves.

Unlike with build scripts though, Pavilion often doesn't know exactly what
the run script should look like until we're in the allocation, so it has to
wait until then to write the final '``run.sh``' file. Here's ours:

.. code-block:: bash

    #!/bin/bash

    # The first (and only) argument of the build script is the test id.
    unset PAV_CONFIG_FILE
    export TEST_ID=${1:-0}
    source /yellow/usr/projects/hpctools/pflarr/repos/pavilion/bin/pav-lib.bash

    # Perform the sequence of test commands.
    srun -N 2 -n 4 ./supermagic

There are few things to point out.

1.  The result of a test defaults to the whether run script returns zero. This
    usually just ends up being the return value of the last of your test
    commands.
    If there are critical commands before that, make sure to add an
    ``|| exit 1`` to them. (This isn't needed in this case).
2.  Our test script cmd was '``{{sched.test_cmd}} ./supermagic``. The part in
    double curly braces is a Pavilion variable reference, which our scheduler
    replaces with an srun command based on our scheduler settings.
3.  It's important to use '``{{sched.test_cmd}}``'  rather than srun directly.
    Pavilion tests may run in larger allocations than you request, and this
    makes sure each test only runs under what it requested.

Debugging Test Runs
^^^^^^^^^^^^^^^^^^^

Like with builds, we can use pavilion commands to look at our test run scripts
and logs to see what went wrong.

``pav log run <run_id>>``
    Prints the log for that test run.
``pav cat <run_id> run.sh``
    Outputs the run script.

From within an appropriate interactive allocation, you can also directly run
the run script.

Test Results
------------

Every test run produces a 'results' object. This includes the test **result**
value, but it can contain any arbitrary json data you'd like. To extract that
information, we can configure result parsers for our test:

.. code-block:: yaml

    basic:
        ...

        result_parse:
            regex:
                  # The key is where to store found items in our results
                  # structure.
                num_tests:
                  # The regex needs to be in 'literal' single quotes. The
                  # backslash still needs to be escaped.
                  regex: 'num tests.*: (\\d+)'

                # If we match this regex, then we'll say the test passed.
                result:
                  regex:  '<results> PASSED'
                  action: 'store_true'


Now when we run the test, we get the 'num_tests' value added to our results.

.. code-block:: text

    $ pav results -f 29

    {
        "name": "supermagic.basic",
        "id": "19",
        "result": "PASS",
        "created": "2019-12-03 15:46:13.241378",
        "duration": "0:00:00.872191",
        "finished": "2019-12-03 15:46:13.247315",
        "errors": [],
        "num_tests": "11",
    }

Conclusion
----------
So now you have your first test written.
