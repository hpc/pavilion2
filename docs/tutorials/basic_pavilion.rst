.. _tutorials.basic:

Basic Pavilion
==============

This is a step-by-step tutorial on how to write your first test in Pavilion. It is designed to
work on a generic linux system - no cluster required. Further tutorials do require a cluster,
however. If you have access to a slurm cluster (especially one where you can quickly get
allocations), it's advised to do this and further tutorials there.

.. contents:: Table of Contents


Preliminary Steps
-----------------

1. Install Pavilion
~~~~~~~~~~~~~~~~~~~

If you're doing this on a cluster, you should put all files on a (non-lustre)
filesystem that's accessible from all nodes and the frontend (via the same path). More
requirements are in the full install docs (:ref:`install`), but that's mostly NFS settings that
should be turned on for any sane shared filesystem.

Now, simply download Pavilion (either via a git checkout
``git checkout https://github.com/hpc/pavilion2.git`` or via the
`zip file <https://github.com/hpc/pavilion2/archive/refs/heads/master.zip>`__ (extract it).
Generally, the git checkout method is easier.

Then run the ``bin/setup_pav_deps`` scripts in the Pavilion source tree. That will download and
install all of Pavilion's dependencies. If you downloaded a tarball, the script will ask you to
provide a python virtual environment path, you can place this wherever you like (on the same
filesystem), but you will have to *activate* it to run Pavilion.

2. Setup Pavilion
~~~~~~~~~~~~~~~~~

For the purposes of this tutorial, we're going to use the pavilion config directory provided
in ``<pav_src>/examples/tutorials``. However, you should generally place your configuration
directories outside of the pavilion source tree. See the :ref:`basics.create_config` for more on
how to more generically configure Pavilion.

To do this, simply source the ``examples/tutorials/activate.sh`` script.

.. code-block:: bash

    # From the Pavilion source root
    source examples/tutorials/activate.sh

This will set ``PAV_CONFIG_DIR`` and ``PATH`` appropriate. The configuration will also set the
working directory to ``examples/tutorials/working_dir``.

This is generally all you need to do to set up Pavilion.

3. Test Your Installation
~~~~~~~~~~~~~~~~~~~~~~~~~

At this point you should be able to run ``pav show config``, and it will work without warnings.

A Quick YAML Primer
-------------------

All Pavilion configurations are written in YAML, a fairly easy to understand
data format. If you're new to YAML, here's a quick tutorial in one big code blob.

.. code-block:: yaml

    # Yaml uses pound signs for comments

    # Golden Rules
    # 1. No Tabs!  Tab characters are not allowed.
    # 2. Indentation is important for lists and mappings.
    # 3. Strings only! In Pavilion, all 'leaf' values are converted to strings,
    #    regardless of how Yaml handles them.
    # 4. Pavilion has a strict format for all its configuration files, especially about
    #    what mapping keys are allowed and where.
    # 5. Anything that can take a list of things, can just take one thing. It will be
    #    turned into a single item list automatically.

    # Yaml files generally start with top level key->value mapping.
    # When that is the case, the whole file is basically a mapping (at the top level)
    key1: "foo"

    # Yaml Supports a variety of ways to express string values.
    a_string1: "This is a string!"

    # Single quoted strings are literal, and generally preferred when writing Pavilion tests.
    a_string2: 'I am a literal!'

    # Types are inferred by the first few characters. This looks like it should be
    # a string, so it is.
    a_string3: This too is a string.

    # Strings can wrap and all whitespace is collapsed to single spaces.
    a_string4: 'I am going to go
                all the way around!'

    # There is more than this - You can do block quotes and other stuff too.

    # YAML supports other types too, but Pavilion (test) config values are always converted
    # into strings anyway.

    # Mappings can contain other mappings. The tabbing levels must be consistent.
    sub_map:
        subkey1: "Heya"
        subkey2: {another_key: "This is a mapping too, in 'inline' style"}

    # You can also have lists
    some_lists:
        list1:
            - Thing 1
            - Thing 2
        list2: [item1, item2, item3]

    # And that's really all you need to know to use Pavilion.

Writing a Test
--------------

*Technically, we're not writing a test, we're wrapping a test so it can run anywhere!*

The test itself is provided in ``test_src/hello_world.c``. We're going to write
a test configuration to build and run that test.

A Basic Test Config
~~~~~~~~~~~~~~~~~~~

Create a file called 'tutorial.yaml' in the ``tests/`` directory.

Open it in your favorite editor. *Remember, use spaces for indentation!*

Enter the following into that file, minus the comments.

.. code-block:: yaml

    # Every Pavilion test config is a mapping from test name to test config.
    # This test will be called 'basic'.
    # The filename is the test suite, in our case, 'tutorial'.
    # So the full test name is 'tutorial.basic'.
    basic:
        # Everything in the mapping under 'basic' is its test config.

        # Let's give our test a quick description
        summary: The basic hello world run.

        # The build section tells Pavilion how to write a bash script
        # that will be used to build the test. We'll look at the result in a bit.
        build:
            # This is where to find the test source, relative to the `../test_src' directory.
            # It can also be where to put/name downloaded test source.
            source_path: hello_world.c

            # We're about to use gcc to compile the test. If you need to
            # load a module to get gcc, add that module to this list.
            modules: []

            # These commands are added to the build script.
            cmds:
                # The capitalization is an intentional mistake. Keep it!
                - gcc -o hello HELLO_WORLD.C

        # Like build, this tells Pavilion how to write a 'run script'.
        run:
            # It should be 'cmds' here - another intentional mistake.
            commands:
                - './hello'

Debugging a Config
^^^^^^^^^^^^^^^^^^

Now, you should have a test. Let's find it! Run ``pav show tests``.

Oh no! Our test is highlighted in red, and has errors. Let's look at those errors.
Run ``pav show tests --err`` to read our errors.

It says we have an invalid config key called 'command' under 'run'. Hmm, let's find out what
should go there.  Run ``pav show test_config`` to see the full test config format documentation.
Near the top you can find the 'run' section, and you can see that the 'commands' key should be
'cmds'. Correct that in your test config, and run ``pav show tests`` again.

That should be the only error, but if not, track down further errors in the same way. The most
common mistake at this point is to have incorrect indentation levels. Remember, no tabs, and each
mapping must a consistent indentation level for all of its keys.

Building a Test
---------------

Now that our test is in better shape, let's run it.  Simply run ``pav run tutorial.basic``.

It should start the process of building the test and.. OH NO, another failure.

.. code-block::

    $ pav run tutorial.basic
    Creating Test Runs: 100%
    Building 1 tests for test set cmd_line.


    Error building tests for series 's2': Build error while building tests. Cancelling all builds.
      Failed builds are placed in <working_dir>/test_runs/<test_id>/build for
      the corresponding test run.
      Errors:
      Build error for test tutorial.basic (2) in test set 'cmd_line'. See test status
        file (pav cat 2 status) and/or the test build log (pav log build 2)

Let's do what the error suggests, and run ``pav log build <test_id>`` to see what went wrong. The
log command gives us quick access to tests logs, and we'll use it quite a few times in this
tutorial.

Additionally, you can get directory info for a test run via ``pav ls <test_id>``,
and print specific files with ``pav cat <test_id> <filename>``, where ``<filename>`` is relative to
the test run directory.

.. code-block::

    $ pav log build 2
    gcc: error: HELLO_WORLD.C: No such file or directory
    gcc: fatal error: no input files
    compilation terminated.

    $ pav cat 2 build.sh
    #!/bin/bash

    # The first (and only) argument of the build script is the test id.
    export TEST_ID=${1:-0}
    export PAV_CONFIG_FILE=/home/pflarr/repos/pavilion/examples/tutorials/pavilion.yaml
    source /home/pflarr/repos/pavilion/bin/pav-lib.bash

    # Perform the sequence of test commands.
    gcc -o hello HELLO_WORLD.C

It looks like we just need to de-capitalize 'HELLO_WORLD.C' into 'hello_world.c', and the build
will work (which we did intentionally to show these debugging steps). After doing that, we get:

.. code-block::

    $ pav run tutorial
    Creating Test Runs: 100%
    Building 1 tests for test set cmd_line.
    BUILD_SUCCESS: 1
    Kicked off '1' tests of test set 'cmd_line' in series 's5'.

    $ pav status
     Test statuses
    ---------+--------+-----------------+-------+----------+--------+----------+--------------------
     Test id | Job id | Name            | Nodes | State    | Result | Time     | Note
    ---------+--------+-----------------+-------+----------+--------+----------+--------------------
     3       |        | tutorial.basic  | 1     | COMPLETE | FAIL   | 11:55:53 | The test completed
             |        |                 |       |          |        |          | with result: FAIL

Yay, it built! It still failed though. We'll get into that in a moment.

First though, let's talk about a few things:

Build Reuse
~~~~~~~~~~~

When Pavilion builds a test, it takes everything that goes into that build - mainly the source and
the build script Pavilion generates - and creates a hash. If that hash already exists, then so
does the build! So we just re-use the old build. If you to run the test again, you'd see this:

.. code-block::

    $ pav run tutorial
    Creating Test Runs: 100%
    Building 1 tests for test set cmd_line.
    BUILD_REUSED: 1
    Kicked off '1' tests of test set 'cmd_line' in series 's6'.

Note that it says it reused one build.

Source File Types
~~~~~~~~~~~~~~~~~

In our example we're using a single C source file as our our test, but most archives and whole
directories will work as well. Archives will be extracted automatically for you, and the root
directory of that archive will be the root of your build directory.

Build Directories
~~~~~~~~~~~~~~~~~

Builds for tests can often be huge. We don't really want to copy all of those files,
so Pavilion instead symlinks to them all. If you look in the build directory with ``pav ls``
you'll see exactly that:

.. code-block::

    $ pav ls --symlink 3 build
    working_dir/test_runs/3/build:
    hello -> ../../../builds/ed34332fe63b9169/hello
    pav_build_log -> ../../../builds/ed34332fe63b9169/pav_build_log
    .built_by -> ../../../builds/ed34332fe63b9169/.built_by
    hello_world.c -> ../../../builds/ed34332fe63b9169/hello_world.c

It's ok to write new files into the build directory as part of your build commands, or even
overwrite some of these symlinks. The original files are protected as read-only, and you'll just
replace existing symlinks with real files.

If you need an actual file instead of a symlink, you can use the ``build.copy_files`` to list
files to actually copy. See :ref:`tests.build` for more info.

**NOTE**: The 'run script' will be executed from within each test's build directory. So all of
the commands in your 'run.cmds' section should be relative to to that path.

Running a Test
--------------

Our test built, but it's now failing. Let's look at the results and find out why. Run
``pav results --full <test_id>`` to get the full result object.

.. code-block::

    $ pav results --fail 6
    [{'created': 1643656934.8110116,
      'duration': 0.016700267791748047,
      'finished': 1643656935.5868542,
      'id': 6,
      'job_info': {},
      'name': 'tutorial.basic',
      'pav_result_errors': [],
      'pav_version': '2.3',
      'per_file': {},
      'permute_on': {},
      'result': 'FAIL',
      'return_value': 1,
      'sched': {'chunk_ids': None,
                'errors': None,
                'min_cpus': '1',
                'min_mem': '4294967296',
                'node_list_id': '',
                'nodes': '1',
                'tasks_per_node': '1',
                'tasks_total': '1',
                'test_cmd': '',
                'test_min_cpus': '8',
                'test_min_mem': '62',
                'test_nodes': '1'},
      'started': 1643656935.570154,
      'sys_name': 'durkula',
      'test_version': '0.0',
      'user': 'pflarr',
      'uuid': '07a37017-dc75-4b38-817a-6888a32fbcb7'}]

That's a lot of results for such a simple test! We can see that the 'result' value is 'FAIL', which
only happens if our test 'result' condititon fails.

What is that condition? It can be whatever we want, but by default it's whether the
test ``run.sh`` script returns 0, which is generally determined by what we put in 'run.cmds' in
our test config. As we can also see above, the return value of our ``run.sh`` was 1, which is
very much not 0.

So let's find out why. We can get the run log via ``pav log run <test_id>``.

.. code-block::

    $ pav log run 6
    Usage: ./hello <thing>
    I need to know what to say hello to.

It looks very much like our ``hello`` script needs an argument. Let's change that in
our ``tutorial.yaml`` file.

.. code-block:: yaml

    basic:
        # ...
        run:
            cmds:
                - './hello bob'

And now if you run it, the test should pass.

Custom Results
--------------

Pavilion can pull results out of the test output for you automatically.  The output
of each test run ends up in the ``run.log`` file, and Pavilion can parse results out
of that (or any other file). For full results documentation see :ref:`results`.

Let's look at our test output.

.. code-block::

    $ pav log run dummy.8
    Hello Paul!
    Today's lucky number is: 0.4789

It's not uncommon to find tests whose return value is not a good indicator
of whether they succeeded or not. In those cases we need to look for some
value to indicate if we passed or not. In this case, let's look for 'Hello <some_name>!',
and on finding that say that our test passed.

Add a result parse section to your test config:

.. code-block:: yaml

    basic:
        # ...

        # Add this to the bottom of your basic test config.

        result_parse:
        # The result parse section is organized by parser. Pavilion comes with more than one,
        # and it's fairly easy to add your own.

            # We're going to use the regex parser. It allows you to write regexes to match lines
            # with values we want, and grab part of them.
            regex:
                # Under here are the result keys that we'll pull out.
                # We can store directly to the result key, but it has to be boolean.
                result:
                    # Here we configure the result parser, we need to tell it what to look for
                    # and what to do with the value

                    # Look for a line with 'Hello <some name>!
                    # Always use single quotes for regexes.
                    regex: '^Hello .*!$'

                    # If we find a result, discard it, and just store 'True' in our 'result' key
                    action: 'store_true'

Go ahead and give that a shot. You can use ``pav results -f <test_id>`` to look at the results
of the test after you run it. Pavilion automatically converts the boolean value of
'result' into either 'PASS' or 'FAIL'.

The results are all in one big JSON mapping, saved to both a per-test-run results file and logged
to a central results log file.

Debugging Results
~~~~~~~~~~~~~~~~~

I didn't set up any forced errors this time around, but there will be times you run
into problems with result parsing when working on a test.

Any errors you encounter will have a short description listed in the ``pav_result_errors`` key.
Pavilion logs all error messages from parsing there. Additionally, if the error is with parsing
the 'result' key, Pavilion can return a result of 'ERROR'.

In either case, if you want to see exactly what happened and where, the *result log* is
super helpful. It shows, step-by-step, what Pavilion did when parsing results. You can
use that to figure out where and why things went wrong. It's in the 'results.log' file,
which is viewable via ``pav log results <test_id>``.

Lastly, if you're debugging result parsers on a test, you can re-run just the result parsing
step using ``pav results --re-run -f <test_id>``. Pavilion will use the result handling steps
from the test config as it currently exists to reparse the results (though it only saves them via
another option).

Other Result Parsers
~~~~~~~~~~~~~~~~~~~~

Pavilion comes with several result parser plugins, and you can add your own too. To get a list of
what's available, use the ``pav show result_parsers`` command.

To see the full documentation for one of them, use ``pav show result_parsers --doc <parser>``. It
will give you documentation for the options the parser takes, as well as documentation for the
general arguments all parsers take. In the next section, we'll use the 'split' parser to pull
out a value. It would be good to look at its options now.

Parsing Out Values
~~~~~~~~~~~~~~~~~~

We usually want to instrument our tests by pulling out useful result values. You can, for
instance, have Splunk or a similar tool read your result logs. You can then use Splunk searches
to compare current results to past results, or create dashboards for each system.

Let's try that here. The 'lucky number' is going to be our value to parse out. We're going to
do things a bit differently this time though, in order to demonstrate how result parsing
actually works under the hood and show off its power.

.. code-block:: yaml

    basic:
        # ...
        result_parse:
            split:
                # We can set any key here, including multiple keys!
                # If the result parser returns a list of (regex and split can), they're
                # assigned to the keys in order. Extra items are discarded. Items
                # assigned to an underscore '_' are also discarded.
                "_, lucky":
                    # The number (and nothing else) comes after a colon ':'. So if we
                    # split on that and save the second part, we've got the number.
                    sep: ':'

                    # But wait, how do we know which line to do this to? Like this:
                    for_lines_matching: "^Today"
                    # So we'll only grab this value from lines that start with (^)
                    # 'Today'.

                    # What if we still match multiple lines? Just get the first one.
                    match_select: first  # This is the default, so it could have been left out.

The ``for_lines_matching`` and ``match_select`` options can be used with any result parser - the
result parser is only lines that are 'matched'. The ``for_lines_matching`` option defaults
to matching every line, which is why our regex parser worked above. There's also a
``preceeded_by`` option, for those cases where the prior lines are what you need to
tell when to parse out a value.

If you run your modified test, and use ``pav results -f <test_id>`` you'll see that
we now have a 'lucky' key with that value in it. Nice!

Result Evaluations
~~~~~~~~~~~~~~~~~~

Result Evaluations is additional, powerful layer to handling results in Pavilion. It lets you
take the results you already parsed out into the result json and combine, modify, or recalculate
them with a full math expression system and useful functions.

Let's say we really want our luck expressed on a scale from 1-1000. It's fairly common
to need to normalize test results based on units or an arbitrary scale.

.. code-block:: yaml

    basic:
        # ...
        # This section is distinct from 'result_parse'.
        result_evaluate:
            # We can store to most result keys
            normalized_luck: 'round(lucky * 1000)'
                            # round() is a provided expression function (see below).
                            # Values in the results are available as variables, including
                            # from other expressions.
                            # Don't worry about types - it's all implicitly dealt with.

If you run the test and check the results, you'll see ``normalized_luck`` as a new key.

In this example, we used the 'round()' function. A list of all available functions
can be seen with ``pav show functions``. Like result parsers, they're plugins and you can add
your own (it's *really* easy).

Conclusion
----------

In this tutorial we've learned how to set up Pavilion and write a simple test
configuration that builds, runs, and gets results from a test.

Yet this is just scratching the surface of what Pavilion can do. Our next tutorial
will show you how to make your configurations generic, dynamically multiply, and run
under a cluster's scheduler. It's available here: :ref:`tutorials.advanced`.

If you're more interested in learning about pulling out interesting data from your
test results, there's a separate tutorial for that: :ref:`tutorials.results`.