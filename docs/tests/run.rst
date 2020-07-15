.. _tests.run:

Running Tests
=============

This page covers how the test ``run`` section is used to create the test
run script.

.. contents::

Run Configuration
-----------------

The run section of the test config is used to generate a ``run.sh``
script, which runs the actual test. It's fairly simple, as most of the
work involved in getting ready to run the test is configured separately.

modules (list)
^^^^^^^^^^^^^^

Modules to ``module load`` (or swap/remove) from the environment using
your cluster's module system.

For each module listed, a relevant module command will be added to the
build script.

See :ref:`tests.env.modules` for more info.

env (mapping)
^^^^^^^^^^^^^

A mapping of environment variable names to values.

Each environment variable will be set (and exported) to the given value
in the build script. Null/empty values given will unset. In either case,
these are written into the script as bash commands, so values are free
to refer to other bash variables or contain sub-shell escapes.

See :ref:`tests.env.variables` for more info.

.. _tests.run.create_files:

create_files (list)
^^^^^^^^^^^^^^^^^^^

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
                data.in:
                    - 'line 1'
                    - 'line 2'
                    - 'line 3'

                # Create file, "data.in", inside subdirectory "subdir". Note if
                # the subdirectory(ies) do not exist they will be created.
                ./subdir/data.in:
                    - 'line 1'
                    - 'line 2'
                    - 'line 3'

                # Create file, "var.in", with 'page' variable data inside nested
                # subdirectory "subdir/another_subdir".
                ./subdir/another_subdir/var.in:
                    - 'module = {{page.module}}'
                    - 'size = {{page.bytes}}'

                # Create file, "defer.in", with deferred variables.
                defer.in:
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

timeout
^^^^^^^

By default test runs timeout if they don't produce output within 30 seconds.
This setting allows you to extend that time arbitrarily,
including to such large numbers that your test will never time out.