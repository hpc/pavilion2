Pavilion Advanced Usage
=======================

This page is an overview of some of the advanced features of Pavilion, to
give you a better idea of what it's capable of.

.. contents::

Mode Configs
------------

*Full Docs:* :ref:`tests.format.mode`

In addition to host config files, you can provide mode config files that
you can apply to any test when you run it. They have the same format as
the host configs, but multiple can be provided per test.

For example, the following mode file could be used to set a particular
set of slurm vars:

.. code-block:: yaml

    slurm:
        account: tester
        partition: post-dst

.. code-block:: bash

    $ pav run -m tester -f post_dst_tests.txt

Advanced Test Configs
---------------------

Test configs aren't just static files. They can be re-shaped dynamically
through variable substitution, module file loads, and environment
variables.

Variables
~~~~~~~~~
*Full Docs:* :ref:`tests.variables`

Test configs can contain *expressions* within their config values that
reference and manipulate variables.

These variables come from a variety of sources (this is also the
resolution order):

- The test config's variables section (var)
- System Plugins (sys)
- Pavilion hardcoded variables (pav)
- The selected scheduler (sched)

Variable names must be in lowercase and start with a letter, but may
contain numbers, dashes and underscores.

.. code-block:: yaml

    mytest:
      scheduler: slurm

      variables:
        sleep_time: 24

      run:
        cmds:
          - "sleep {{var.sleep_time + 12}}"
          - 'echo "Slept {{sleep_time + 12}} seconds on node
             {{sched.node_num}}."'


-  Use double curly brackets ``{{var.myvar}}``.
-  Variable category is optional. ``{{myvar}}`` is fine.
-  Name conflicts are resolved in the order of categories listed above.
-  In fact, it's recommended to not use the category component unless
   you need to make the reference explicit.
-  You'll also see ``{{myvar.2}}`` list references, ``{{myvar.foo}}``
   attribute references, and the combination of the two
   ``{{myvar.1.bar}}``.


Listing Variables
^^^^^^^^^^^^^^^^^

Use the ``pav show`` commands to display what variables are available
from various sources.

::

    # pav show sched --vars slurm
    # pav show pav_vars

    pav show sys_vars

     Available System Variables
    -----------+-------------------------------------+---------------------------------------------
     Name      | Value                               | Description
    -----------+-------------------------------------+---------------------------------------------
     host_arch | <deferred>                          | The current host's architecture.
     host_name | <deferred>                          | The target host's hostname.
     host_os   | <deferred>                          | The target host's OS info (name, version).
     sys_arch  | x86_64                              | The system architecture.
     sys_host  | myhost                              | The system (kickoff) hostname.
     sys_name  | myhost                              | The system name (not necessarily hostname).
     sys_os    | {'name': 'sles', 'version': '12.3'} | The system os info (name, version).

Deferred Variables
^^^^^^^^^^^^^^^^^^

Deferred variables are those that can't be resolved at test kickoff
time. They need to know something about the node the test is being
started on (which we won't know till the scheduler gives us nodes), or
something about the allocation.

Because some parts of the test are resolved at kickoff time (usually on
a front-end) rather than on the nodes, deferred variables aren't allowed
in those sections. Namely, this includes the ``build`` and various
scheduler config sections, as well as root level config values. Pavilion
will tell you when you make this mistake.

Expressions
~~~~~~~~~~~

*Full Docs:* :ref:`tests.values.expressions`

The double curly brace sections that can contain variables are really fully
capable :ref:`tests.values.expressions`, and can contain math operations and
function calls. Functions are provided via
:ref:`plugins <plugins.expression_functions>`.

.. code-block:: yaml

    mytest:
      variables:
        sleep_time: 24

      run:
        cmds:
          - "sleep {{ max([var.sleep_time/4, 1, sleep_time + 1]) }}"


Inheritance
~~~~~~~~~~~

*Full Docs:* :ref:`tests.format.inheritance`

Tests within a single test suite file can inherit from each other.

.. code-block:: yaml

    test_a:
        variables:
            key1: "apple"
            key2: "pear"

        run:
            cmds: 'echo "{{key1}} {{key2}}"'

    test_b:
        inherits_from: test_a

        variables:
            key2: "banana"

The first test, 'test_a', would echo "apple pear", while the second would
echo "apple banana".


Rules of Inheritance
^^^^^^^^^^^^^^^^^^^^

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

Permutations
~~~~~~~~~~~~

Let's say you want to create ten mostly identical tests, but each test takes
slightly different input. In Pavilion, you can assign those different input
values to a variable, and then create test 'permutations' over those values.
Each permutation of a test is an instance of that test where that variable takes
on just one of the values from your variable.

.. code-block:: yaml

    nbodies:

        variables:
            bodies: [2, 3, 10, 1000, 10000, 100000]
        permute_on: bodies

        run:
            cmds:
                - "nbodies -n {{bodies}} -s 1000"

        build:
            ...

This will create six test configurations (and thus six test runs), one for each
 of the values of ``bodies`` with run commands that look like:

 - nbodies -n 2 -s 1000
 - nbodies -n 3 -s 1000
 - nbodies -n 10 -s 1000
 - etc.

You also can permute over multiple variables at once, producing a test run for
each possible permutation of values. See :ref:`tests.permutations`
for more info.

Skip Conditions
~~~~~~~~~~~~~~~

*Full Docs:* :ref:`tests.skip_conditions`

The ``only_if`` and ``not_if`` sections of the test config allow users
to specify the conditions under which a test should run. Tests are 'SKIPPED'
unless each of their ``only_if`` conditions (and none if their ``not_if``
conditions) match. The conditions are ``key:value/s`` pairs; the key is a
Pavilion variable, and the value/s are one or more items that the 'resolved'
value of the Pavilion variable might match to.

.. code:: yaml

    test: # This test uses the directives only_if and not_if.
        only_if:
            # For this test to run, 'user' must be one of the values below.
            "{{user}}": ['calvin', 'paul', 'nick', 'francine']
        not_if:
            # For this test to run 'sys_arch' must not be x86_64
            "{{sys_arch}}": 'x86_64'
        run:
            cmds:
                - 'echo "Helloworld"'

Environment
-----------

Pavilion provides means to alter environment variables and load
environment (or lmod) modules.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

*Full Docs:* :ref:`tests.env.variables`

You can set environment variables in your test scripts using the
'env' section under both 'run' and 'build'. This will cause the variables to
be exported within the generated run or build script, where they can be used
by commands run as part of that script. Note that environment variables are
**only** usable in the *cmds* and *env* sections, as these are written
directly into the build and run scripts.

.. code-block:: yaml

    python_test:
        run:
          env:
            # Unset the python path environment variable.
            PYTHONPATH:
            # Use a different python home
            PYTHONHOME: /home/mario/python_root/
            # Specify a python version
            PY_VERS: 3
          cmds:
            - python${PY_VERS} -c "print('hello world')"

This will result in a run script that looks like:

.. code-block:: bash

    #!/bin/bash

    unset PYTHONPATH
    export PYTHONHOME=/home/mario/python_root
    export PY_VERS=3

    python${PY_VERS} -c "print ('hello world')"

Modules
~~~~~~~

*Full Docs:* :ref:`tests.env.modules`

You can have pavilion load module files automatically for each test or
build. This assumes the modules (and module build combinations) are
available on your system. If the test can't load a module, the test will
report a ENV\_FAILED status and fail.

.. code-block:: yaml

    super_magic:
        scheduler: slurm
        build:
          modules:
            - gcc/7.4.0
            - openmpi
          cmds:
            - mpicc -o super_magic super_magic.c
        run:
          # This runs as a separate script from the build, so you
          # have to specify modules for both the build and run.
          modules:
            - gcc/7.4.0
            - openmpi
          cmds:
            - srun ./super_magic -a

Pavilion assumes everything is starting from a clean system state in
regards to modules, which is essentially the environment you get by
default when logging in. That state may include modules that you don't
want loaded, so Pavilion provides a means for removing and swapping
modules as well.

.. code-block:: yaml

    super_magic:
        build:
          modules:
            # Swap the gcc module for the intel module.
            - 'gcc -> intel/18.0.3'
            # Remove the python module
            - '-python'
          ...

Module Wrappers
^^^^^^^^^^^^^^^

When tell pavilion to load/remove/swap modules, the code to do this is
added to the test or build script automatically using
:ref:`plugins.module_wrappers`.
The default module wrapper performs the module command, and
then verifies that the module is actually loaded.

More complicated setups are possible by adding additional plugins
that replace this default behaviour for particular modules or module versions.
You could, for instance, wrap all your compiler modules to set a consistent
compiler wrapper environment variable.

.. code-block:: yaml

    openmp_test:
        build:
          modules:
            # Normally intel-mpi would require that we use mpiicc to build.
            # In our case though, we use module_wrappers (not shown) to set the
            # $MPICC env variable consistently across different MPI modules.
            # We also set $OPENMP_FLAG to value, as it varies across compilers.
            - intel
            - intel-mpi
          cmds:
            - '$MPICC $OPENMP_FLAG -o openmp_test openmp_test.c

    # This test will use the same command, but it will work thanks to our
    # module wrapper plugins.
    openmp_test2:
        inherits_from: openmp_test
        build:
          modules:
            - gcc
            - openmpi

Module wrappers are also useful for smoothing the differences clusters that
have distinct module setups. For instance, one might wrap the gcc module
such that it loads normally on some systems, but it performs a module swap
on an odd system that loads a different compiler by default. This can allow
for a single, host-agnostic set of tests.

Schedulers
----------

An HPC testing framework wouldn't be complete without allowing you to
schedule your tests. Most of the above example tests reference a
scheduler, but don't configure one. It's time to rectify that.

.. code-block:: yaml

    super_magic:
        scheduler: slurm
        slurm:
          # Slurm lets us set a number of nodes as a range.
          num_nodes: 2-all
          # These are standard slurm options.
          tasks_per_node: 3
          partition: test_partition
          reservation: testing
          qos: test

        build:
          modules: [gcc, openmpi]
          cmds:
            - mpicc -o super_magic super_magic.c

        run:
          modules: [gcc, openmpi]
          cmds:
            # Regardless of scheduler used, scheduler vars are in the 'sched'
            # category. This var generates an srun command based on the slurm args
            # given above. Assuming we got 10 nodes, it will look like:
            # srun -N 10 -n 30 ./supermagic -a
            # Note that this would run in an sbatch script within an allocation
            # that conforms to the rest of the slurm settings.
            - {sched.test_cmd} ./supermagic -a

Schedulers are plugins in Pavilion, and are
fairly loosely defined. They must at least do the following:

* Provide a scheduler variable set for use in configs (the set may be empty).
* The available keys/values are up to the plugin writer.

  - See ``pav show sched --vars <sched_name>`` for a listing of what's
    available for a given scheduler.
* Define a configuration section for test configs.

  - See ``pav show sched --config <sched_name>`` for the definition.
* Provide a means to kickoff tests.

  - The scheduler writes a script that does little more than call Pavilion
    again to actually run a test.
  - The Slurm plugin runs this script using ``sbatch``.
  - The Raw plugin simply runs it as a subprocess.
* Provide a means to monitor scheduled tests.
* Provide a means to cancel scheduled tests.

