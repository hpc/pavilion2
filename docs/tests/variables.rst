.. _tests.variables:

Pavilion Test Variables
=======================

Pavilion provides a wide variety of variable you can substitute into your
test configuration values using :ref:`tests.values.expressions`. This covers
where those values come from.

.. contents::

.. _tests.variables.sets:

Variable Sets
-------------

Variables can come several different variable sets. Each set has a
category name ('var', 'sys', 'pav', 'sched') that is used in the
variable reference to remove ambiguity about the source of the variable,
but is otherwise optional. This ordering of variable sets also
determines the order in which the system resolves variable names where
the set isn't specified.

.. code:: yaml

    foo:
        variables:
          host_name: foo

        run:
          # This would echo 'foo' regardless of the fact that the system variables
          # also provides a 'host_name' variable, as the test variables (var) set
          # takes precedence.
          cmds: "echo {{host_name}}"

Test Variables (var)
^^^^^^^^^^^^^^^^^^^^

The test's ``variables`` section provides these variables, as
demonstrated in many examples. See the :ref:`tests.variables.detail`
section for more on these. While these
generally come from the test config, they can also be provided via host
and mode configuration files.

System Variables (sys)
^^^^^^^^^^^^^^^^^^^^^^

System variables are provided via system plugins. These are designed to
be easy to write, and provide a way for people working with Pavilion to
provide extra information about the system or cluster that Pavilion is
currently running on. The values may be
:ref:`tests.variables.deferred`.

Use ``pav show sys_vars`` to list the system variables.

Pavilion Variables (pav)
^^^^^^^^^^^^^^^^^^^^^^^^

Pavilion variables provide information about pavilion itself as well as
generally useful facts such as the current time. They are hard-coded
into Pavilion itself.

Use ``pav show pav_vars`` to list the pavilion variables.

Scheduler Variables (sched)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Scheduler variables are provided by the scheduler plugin selected via a
test's ``scheduler`` attribute. They vary by scheduler, and there are no
rules about what a given scheduler plugin should provide. Scheduler
plugin writers are encouraged to follow the following conventions for
variable naming, however:

-  test\_\* - Variables that are specific to a currently running test.
-  alloc\_\* - Variables specific to the current allocation.

Note that the current allocation resources and what the test wants may
differ, as the scheduler is allowed to request more resources than specifically
asked for by the test. Scheduler plugin writers are encouraged to
provide helper variables to simplify the launching of tests within an
arbitrary allocation.

.. _tests.variables.types:

Variable Types
--------------

While all variables in pavilion are treated as strings in the end, there
are several variable data structures available.

**Note: While all of the following examples use variables from the 'test
variables' set, variables from any variable set may have such data
structures (but nothing more complex).**

Single Value
^^^^^^^^^^^^

Single value variables are the simplest, and are what is generally shown
in the Pavilion documentation for simplicities sake. Variable references
are simply replaced with the variable's value.

.. code:: yaml

    foo:
      variables:
        bar: "baz"

      run:
        cmds: "echo {{bar}}"

Multiple Values
^^^^^^^^^^^^^^^

Variables may have multiple values, and referenced with an index
(counting from 0).

.. code:: yaml

    multi_vars:
        variables:
            msg: ['hello', 'you', 'handsome', 'devil']

        run:
          # Would print 'hello you devil'
          cmds: "echo {{msg.0}} {{msg.1}} {{msg.3}}"

Variables with multiple values referenced without an index are used as
if the first value is their only value. Additionally, single valued
variables can be referenced by the 0th index.

.. code:: yaml

    multi_vars2:
        variables:
          paths: ['/usr', '/home', '/root']
          list_cmd: 'ls'

        run:
            # This would result in the command: 'ls /usr'
            cmds: '{{list_cmd.0}} {{paths}}'

This can be used with repeated :ref:`tests.values.iterations`
to produce dynamic test arguments, among other things.

Complex Variables
^^^^^^^^^^^^^^^^^

Variables may also contain multiple sub-keys, as a way to group
related values. It is an error to refer to a variable that contains
sub-keys without specifying a sub-key.

.. code:: yaml

    subkeyed_vars:
        variables:
          compiler:
            name: 'gcc'
            cmd: 'mpicc'
            openmp: '-fopenmp'

        build:
          # Will result in 'mpicc -fopenmp mysrc.c'
          cmds: '{{compiler.cmd}} {{compiler.openmp}} mysrc.c'

But wait, there's more. Complex variables may also have multiple values.

.. code:: yaml

    subkeyed_vars:
        variables:
          compiler:
            - {name: 'gcc',   mpi: 'openmpi',   cmd: 'mpicc',  openmp: '-fopenmp'}
            - {name: 'intel', mpi: 'intel-mpi', cmd: 'mpiicc', openmp: '-qopenmp'}

        build:
          # Will result in `mpiicc -qopenmp mysrc.c`
          cmds: '{{compiler.1.cmd}} {{compiler.1.openmp}} mysrc.c'

This is especially useful when combined with
:ref:`tests.values.iterations` and
:ref:`tests.permutations`.

.. _tests.variables.detail:

Test Variables
--------------

Test variables provide a way to abstract certain values out of your
commands, where they can be modified through inheritance or defined by
host or mode configurations. Like everything else in test configs,
variables defined at the test level override anything defined by host or
mode configs. Unlike everything else, however, you can override that
behavior by appending a ``'?'`` or ``'+'`` to the variable name.

Test Variable References
^^^^^^^^^^^^^^^^^^^^^^^^

Variables may contain references to other variables in their values.
These can reference any other variable set (with the exception of
'sched' variables) and can contain substrings and all the other syntax tricks
Pavilion provides.

.. code:: yaml

    rec_example:
        variables:
          target_mount: '/tmp/'
          options: '-d {{target_mount}}'

Expected Variables (?)
^^^^^^^^^^^^^^^^^^^^^^

You can denote a variable as 'expected' by adding a question mark ``?``
to the end of it's name. The value provided then simply acts as the
default, and will be overridden if the host or mode configs provide
values. You can also leave the value empty, an error will be given if no
value is provided by an underlying host/mode config files.

.. code:: yaml

    expected_test:
      variables:
        # Pavilion will only use this value if the host or mode configs
        # don't define it.
        intensity?: 1

        # Pavilion expects the hosts or modes to provide this value.
        power?:

        run:
          cmds:
            - "./run_test -i {{intensity}} -p {{power}}"

Appended Variables (+)
^^^^^^^^^^^^^^^^^^^^^^

Instead of overriding values from host/mode configs, this lets you
append one or more additional unique values for that variable. You must
add at least one value.

.. code:: yaml

    append_test:
      variables:
        test_options+: [-d, -f]
        # This will add the single value to the list of test_drives
        test_drives+: /tmp

.. _tests.variables.deferred:

Deferred Variables
------------------

Deferred variables are simply variables whose value is to be determined
when a test runs on its allocation.

- They cannot have multiple values.
- They **can** have complex values, as their sub-keys are defined in
  advance.
- Only the system and scheduler variable sets can contained deferred values.
- Deferred values **are not allowed** in certain config sections:

  - Any base values (summary, scheduler, etc.)
  - The build section

    - The build script and build hash are generated as soon as the test
      run is created, which is long before we know the values of
      deferred variables.

  - The scheduler section.

    - Everything needs to be known here **before** a test is kicked off.
