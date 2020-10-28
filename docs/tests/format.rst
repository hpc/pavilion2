.. _tests.format:

Test Format
===========

This page contains in-depth documentation on the test format.

.. contents::


Tests and Suites
----------------

Each Suite is a yaml file (with a ``.yaml`` extension) which can contain
multiple tests. Suite files must reside in ``<config_dir>/tests/``,
where ``<config_dir>`` is one of your :ref:`config.config_dirs`. Tests
in a suite can be run as a group or independently, and can even inherit
from one another.

.. code:: yaml

    # The test will be called supermagic.
    supermagic:
        # Use the slurm scheduler
        scheduler: slurm

        # Configure how to build the test. If two tests have identical build
        # configurations, they will share a build.
        build:
          # This will be searched for in <config_dir>/test_src/ for each of
          # the known config directories.
          source_location: supermagic.xz
          # These commands are written into a build script.
          cmds:
            - mpicc -o super_magic super_magic.c

        # Configure how to run the test.
        run:
          # Like with building, these are to generate a script to run the test.
          # By default, the return result of the last command determines whether
          # the test result is PASS or FAIL.
          cmds:
            - "srun ./super_magic"

    # We can have more than one test config per suite file.
    supermagic2:
        ...

Test Formatting and Structure
-----------------------------

Pavilion uses YAML as the base configuration language, but the structure
of suite files is strictly defined. If you violate these rules, Pavilion
will warn you immediately. You can use whatever advanced YAML constructs
you'd like, as long as the end result still conforms to Pavilion's
expected structure.

All config keys in pavilion are **lowercase**, including test names.

.. code:: yaml

    # Suite files are a YAML mapping at the top level. The key is the test
    # base name, and the value is a strictly defined mapping of the test attributes
    # and sections.
    formatting:
        # This (short) description appears when listing tests.
        summary: This example explains pavilion/YAML test formatting.

        # The documentation string is for longer test documentation.
        doc: Note that YAML strings only have to be quoted if they contain
             special characters. They can wrap lines with or without quotes.
             The extra tabbing and newlines are automatically removed.

             A double newline will force a newline, however.

             You can also double quote strings (which allows for escapes),
             single quote strings (which interprets them completely literally),
             or use either of the YAML block string styles.

        # This adds to the test name. It's particularly useful for
        # permuted tests, as it lets put a generated component in the test name.
        # {{compiler}} is a pavilion variable reference. We'll cover that later.
        subtitle: "{{compiler}}"

        # In this build section, we use YAML 'block' style everywhere.
        # You could also use 'flow' style
        build:
          modules:
            - gcc
            - openmpi
          env:
            MPICC: mpicc
          cmds:
            - "$MPICC -o formatting formatting.c"

        # In this run section, we use YAML 'flow' formatting everywhere.
        # You could also use 'block' style
        run:
          modules: ['gcc', 'openmpi']
          env: {MPICC: mpicc}

          # Anything that accepts a list of values will also accept a single value.
          # Pavilion will quietly make it a single item list.
          cmds: "./formatting"

Pavilionisms
~~~~~~~~~~~~

While YAML is the base configuration language, Pavilion interprets the
values given in some non-standard ways.

Escapes
^^^^^^^

The YAML library used by Pavilion has been modified to handle escapes more
like Python. This makes it easier for Pavilion to separately handle escapes
that are unique to it (like ``\{{``). Yaml would normally throw an error
on such escapes when using double quoted strings, but now it simply leaves them
as is.

Additionally, there is no general escape syntax in Pavilion. In most cases,
a backslash followed by a character remains as a backslash and that character
. There are, however, a few exceptions.

- ``\{{`` -> ``{{`` (Override special meaning of double brackets).
- ``\[~`` -> ``[~`` (Override special meaning of iteration brackets).
- ``\\{{`` -> A backslash followed by the start of an expression.
- ``\\[~`` -> A backslash followed by the start of an iteration.
- ``\~`` -> ``~``
- ``\\~`` -> A backslash followed by the iteration seperator start character.

Strings Only
^^^^^^^^^^^^

All Pavilion (non-structural) test config values are interpreted as
strings.

YAML provides several different data types, but Pavilion forcibly
converts all of them to strings. The bool True becomes "True", 5 becomes
the string "5", and so on. This done mostly because it enables Pavilion
variable substitution in any config value. Some Pavilion scheduler and
result parser plugins ask for integer or other specific data types in
their configs. It's up to those plugins to interpret those values and
report errors.

Single/Multiple Values
^^^^^^^^^^^^^^^^^^^^^^

Many configuration attributes in Pavilion accept a list of values. If
you give a single value instead of a list to such attributes, Pavilion
automatically interprets that as a list of that single value.

.. code:: yaml


    multi-example:
        build:
          # The cmds attribute of both 'build' and 'run' accepts a list of command
          # strings.
          cmds:
            - echo "cmd 1"
            - echo "cmd 2"

        run:
          # If you have only one command, you don't have to put it in a list.
          cmds: echo "cmd 1"

        variables:
          # Keys in the variables and permutations sections always take a list,
          # but that list can have mappings as keys. Whether one value or multiple
          # values is given, Pavilion always sees it as a list.
          foo:
            - {bar: 1}
            - {bar: 2}
          baz: {buz: "hello"}

Hidden Tests
------------

Tests can be hidden by starting their name with an underscore '_' character.
This is often useful when you have a base test that others inherit from, but
the base test is never supposed to run on its own.

- Hidden tests never run when you run a whole suite.
- To run them, you must specify the full name of the test:
  ``pav run mytestsuite._base``.
- The ``pav show tests`` commands won't show them unless give the
  ``--hidden`` flag.

.. code:: yaml

    # This won't run
    _base:
        build:
            cmds: make

        run:
            cmds: ./mytest -n {{count}}

    big_run:
        inherits_from: _base

        variables:
            count: 1000

Host Configs
------------

Host configs allow you to have per-host settings. These are layered on
top of the general defaults for every test run on a particular host.
They are ``<name>.yaml`` files that go in the ``<config_dir>/hosts/``
directory, in any of your :ref:`config.config_dirs`.

Pavilion determines your current host through the ``sys_name`` system
variable. The default plugin simply uses the short hostname, but it's
recommended to add a plugin that gives a system name that generically
refers to the entire cluster.

You can specify the host config with the ``-H`` option to the
``pav run``.

::

    pav run -H another_host my_tests

Format
~~~~~~

Host configs are a test config, and accept every option that a test
config does. The test attributes are all at the top level; there're no
test names here.

.. code-block:: yaml

    scheduler: slurm
    slurm:
        partition: user
        qos: user

.. _tests.format.inheritance:

Inheritance
-----------

Tests within a single test suite file can inherit from each other.

.. code-block:: yaml

    super_magic:
        summary: Run all standard super_magic tests.
        scheduler: slurm
        build:
          modules:
            - gcc
            - openmpi
          cmds:
            - mpicc -o super_magic super_magic.c

        run:
          modules:
            - gcc
            - openmpi
          cmds:
            - echo "Running supermagic"
            - srun ./supermagic -a

        result_parse:
          ... # Various result parser configurations.

    # This gets all the attributes of supermagic, but overwrites the summary
    # and the test commands.
    super_magic-fs:
        summary: Run all standard super_magic tests, and the write test too.
        inherits_from: super_magic
        run:
          cmds:
            - srun ./supermagic -a -w /mnt/projects/myproject/

Rules of Inheritance
~~~~~~~~~~~~~~~~~~~~

1. Every field in a test config can be inherited (except for
   inherits\_from).
2. A field that takes a list (modules, cmds, etc.) are always completely
   overwritten by a new list. (In the above example, the single command
   in the fs test command list overwrites the entire original command
   list.)
3. A test can inherit from a test, which inherits from a test, and so
   on.
4. Inheritance is resolved before permutations or any variables
   substitutions.

.. _tests.format.mode:

Mode Configs
------------

Mode configs are exactly like host configs, except you can have more
than one of them. They're meant for applying extra defaults to tests
that are situational. They are ``<name>.yaml`` files that go in the
``<config_dir>/modes/`` directory, in any of your :ref:`config.config_dirs`.

For instance, if you regularly run on the ``dev`` partition, you might
have a ``<config_dir>/modes/dev.yaml`` file to set that up for you.

.. code-block:: yaml

    slurm:
        partition: dev
        account: dev_user

You could then add the mode when starting tests with the ``-m`` option:

.. code-block:: bash

    $ pav run -m dev my_tests

.. _tests.format.resolution_order:

Order of Resolution
-------------------

The various features of test configs are resolved in a very particular
order.

1. Each test is loaded and different configs are overlaid as follows;
   later items take precedence in conflicts.

   1. The general defaults.
   2. The host config.
   3. The actual test config.
   4. Inheritance is resolved.
   5. Any mode configs in the order specified.

2. Tests are filtered down to only those requested.
3. Command line overrides ('-c') are applied.
4. Permutations are resolved.
5. Variables in the chosen scheduler config section are resolved. (You
   should't have ``sched`` variables in these sections.)
6. Variables are resolved throughout the rest of the config.

This results in the semi-final test config. :ref:`tests.variables.deferred`
can't be resolved until we're on the allocation. Once there, we'll finish
resolving those, and resolve any parts of the config that used them. Parts of
the config that are required before kicking off the test (like the build and
scheduler sections), can't use deferred variables.

Top Level Test Config Keys
--------------------------

inherits\_from
~~~~~~~~~~~~~~

Sets the test (by test base name) that this test inherits from *which must be*
*a test from this file*. The resulting test will be composed of all
keys in the test it inherits from, plus any specified in this test
config. See :ref:`tests.format.inheritance`.

subtitle
~~~~~~~~

This will be added to the test name for logging and documentation
purposes. A test named ``foo`` with a subtitle of ``bar`` will be
referred to as ``foo.bar``. It provides a place where you can add
variable or permutation specific naming to a test. Subtitles appear in
logs and when printing information about tests, but subtitles aren't
considered when selecting tests to run.

summary
~~~~~~~

The short test summary. Pavilion will include this description when it
lists tests, but only the first 100 characters will be printed.

doc
~~~

A longer documentation string for a test.

variables
~~~~~~~~~

A mapping of variables that are specific to this test. Each variable
value can be a string, a list of strings, a mapping of strings, or a
list of mappings (with the same keys) of strings. See the
:ref:`tests.variables` documentation for more info.

scheduler
~~~~~~~~~

Sets the scheduler for this test. Defaults to 'raw'. It's recommended to
set this in your host configs.

build
~~~~~

This sub-section defines how the test source is built.

See :ref:`tests.build` for the sub-section keys and usage.

run
~~~

This sub-section defines how the test source is run.

See :ref:`tests.run` for the sub-section keys and usage.

result_parse
~~~~~~~~~~~~

This sub-section defines how test results are parsed.

See :ref:`results.basics` for the sub-section keys and usage.

result_evaluate
~~~~~~~~~~~~~~~

Allows you to further modify and analyze test results.

See :ref:`results.basics`.

only_if and not_if
~~~~~~~~~~~~~~~~~~

These sub-sections defines conditions under which tests are skipped.

See :ref:`tests.skip_conditions` for the sub-section keys and usage.

<schedulers>
~~~~~~~~~~~~

Each loaded scheduler plugin defines a sub-section for configuring that
scheduler, such as ``slurm`` and ``raw``.

To see documentation on these, use
``pav show sched --config <scheduler>`` to get the config documentation
for that scheduler.
