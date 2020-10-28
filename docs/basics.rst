Getting Started
===============


.. contents:: Table of Contents

Setup
~~~~~

See the :ref:`install` if you need to install Pavilion*

Add the PAV bin directory to your Path.

.. code:: bash

    PATH=<PVINSTALL_PATH>/bin:${PATH}

Pavilion figures out paths to everything else on its own.

Then simply run pavilion:

.. code:: bash

    pav --help

Configure Tests
~~~~~~~~~~~~~~~

Pavilion doesn't come with any tests itself; it's just a system for
running them on HPC clusters. Each test needs a configuration script,
and most will need some source files. Both of these will live in one of
your :ref:`config.config_dirs` under the ``tests/`` and ``test_src/``
sub-directories.

Test configs tell pavilion what environment it needs to build and run
your test, the commands to run it, how to schedule it on a cluster, and
how to parse the results. Don't worry if it seems like a lot, tests can
be as simple as a single command, just about everything in the config is
optional.

.. code:: yaml

    # Tests are in a strictly defined YAML format.

    # This defines a test, and names it.
    mytest:

      # The scheduler to use to schedule the test on a cluster.
      # In this case, we'll use the raw (local system) scheduler
      scheduler: raw
      run:
        cmds: 'test -d /var/log/messages'

The above test checks to see if the ``/var/log/messages`` directory
exits.

- The test is named 'mytest'. The name of the yaml file determines the
  test's *suite*.
- The test will PASS if that command returns 0.
- It will run as a process on the local machine, as your user.
- Pavilion doesn't have any special priviledges. It's meant to test things,
  from a normal user's perspective. If you want to test stuff as root, you'll
  have to run pavilion as root.

Host Configs
^^^^^^^^^^^^

Every system(host) that you run tests on will need a host configuration
file. These are located in ``hosts/<sys_name>.yaml`` in a pavilion
config directory.

This config is used to override the Pavilion defaults for values in
every test config run on that system. You can use these to set default
values for things like the max nodes per job in a given scheduler,
or setting useful :ref:`tests.variables` for that system. The
format is the same as a test config file, except with only one test and
without the name for that test.

.. code:: bash

    $ cat hosts/my_host.yaml

    scheduler: slurm

The above host config would set the default scheduler to 'slurm' for
tests kicked off on a host with a hostname of ``my_host``. Pavilion uses
the contents of the ``sys_name`` test config variable to determine the
current host, which is provided via a built-in
:ref:`plugins.sys_vars`. This behaviour can be overridden by
providing your own sys\_var plugin, which is especially useful on
clusters with multiple front-ends.

Mode Configs
^^^^^^^^^^^^

In addition to host config files, you can provide mode config files that
you can apply to any test when you run it. They have the same format as
the host configs, but multiple can be provided per test.

For example, the following mode file could be used to set a particular
set of slurm vars. It would reside in ``modes/tester.yaml`` in a
pavilion config directory.

.. code:: yaml

    slurm:
        account: tester
        partition: post-dst

.. code:: bash

    pav run -m tester -f post_dst_tests.txt

Running tests
~~~~~~~~~~~~~

Running tests is easy. All you need is the test suite name (the name of
the test file), and the test name (the name of the test in the suite).
Did you forget what you named them? That ok! Just ask Pavilion.

.. code:: bash

    $ pav show tests
    -----------------------+----------------------------------------------------
     Name                  | Summary
    -----------------------+----------------------------------------------------
     hello_mpi.hello_mpi   | Builds and runs an MPI-based Hello, World program.
     hello_mpi.hello_worse | Builds and runs MPI-based Hello, World, but badly.
     supermagic.supermagic | Run all supermagic tests.

    $ pav run supermagic.supermagic
    1 tests started as test series s33.

If you want to run every test in the suite, you can just give the suite
name. You can also run whatever combinations of tests you want. You also
list tests in a file and have Pavilion read that.

.. code:: bash

    $ pav run hello_mpi
    2 tests started as test series s34.

    $ pav run hello_mpi.hello_mpi supermagic
    2 tests started as test series s35.

    $ pav run -f mytests
    347 tests started as test series s36.

Test Status
^^^^^^^^^^^

If you want to know what's going on with your tests, just use the
``pav  status`` command.

.. code:: bash


    $ pav status
    ------+------------+----------+------------------+------------------------------
     Test | Name       | State    | Time             | Note
    ------+------------+----------+------------------+------------------------------
     41   | supermagic | COMPLETE | 16 May 2019 10:38| Test completed successfully.

It will display the status of all the tests in the last test series you
ran.

Test Series and ID's
~~~~~~~~~~~~~~~~~~~~

From the above, you may have noticed that each test gets a series id
like ``s24`` and a test id like ``41``. You can use these id's to
reference tests or suites of tests to get their status, results, and
logs through the pavilion interface. The ID's are unique for a given
Pavilion :ref:`config.working_dir` but they will
get reused as old tests are cleaned up.

Test Results
~~~~~~~~~~~~

Pavilion builds a mapping of result keys and values for every test that
runs. You can view the results of any tests using the ``pav results``
command.

.. code:: bash

    $ pav results Test Results
    ------------+----+--------
    Name        | Id | Result
    ------------+----+--------
    supermagic  | 41 | PASS

    $ pav results --full Test Results
    ------------+----+--------+----------+----------------+----------------+-----------------
      Name      | Id | Result | Duration | Created        | Started        |  Finished
    ------------+----+--------+----------+----------------+----------------+-----------------
     supermagic | 41 | PASS   | 3.825702 | 19-05-16 10:38 | 19-05-16 10:38 | 19-05-16 10:38


Every test has a results object that contains a variety of useful,
automatically populated keys. Additional keys can be defined through
:ref:`result parsing and result evaluations <results.basics>`.

Results are saved alongside each test, as well being written to a
central result log that is suitable for import into Splunk or other
tools.

The Overall Result
^^^^^^^^^^^^^^^^^^

By default, a test passes if its last command returns ``0``, but this can be
easily overridden.

.. code-block:: yaml

    mytest:
        run:
            cmds:
                # We'll use the result parsers below to parse values from
                # the output of the run script.
                - './test_script.sh'

        result_parse:
            regex:
                # Use the regex parser to extract a speed key and add it to
                # the results.
                speed:
                    regex: '^speed (\d+)'

        result_evaluate:
            # The test will PASS if the speed (extracted above) is more than 50.
            result: 'speed > 50'