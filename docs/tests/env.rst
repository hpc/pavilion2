.. _tests.env:

Build and Run Environments
==========================

Setting up your environment is crucial for running and building tests,
and Pavilion gives you several options for doing so.

-  `Environment Variables <#environment-variables>`__
-  `Modules <#modules>`__
-  `Module Wrappers <#module-wrappers>`__

Assumptions
-----------

Pavilion assumes that it runs under a relatively clean, default login
environment; ie the login environment a new user might get when they log
into the machine for the first time, including any default modules or
environment variables. This is **not required**, but simply means that
when you run Pavilion, it will work the same as when your co-worker
does.

That aside, most basic changes won't have a significant impact on
Pavilion. However, a few things will: - Changing from the default
Python3 or PYTHONPATH - Modifying LD\_LIBRARY\_PATH or similar variables
that affect compilation.

Lastly, Pavilion writes and runs *BASH* scripts. It assumes that
whatever your environment is, the module system will work under *BASH*
just as well as your native environment.

.. _tests.env.variables:

Environment Variables
---------------------

The ``env`` attribute allows you to set environment variables in either
the *run* or *build* scripts. They are configured as a YAML
mapping/dict, and (unlike the rest of Pavilion) can have upper-case keys
(but no dashes). Like with the run/build commands, the values can
contain any bash shell syntax without issue.

.. code:: yaml


    env_example:
      run:
        env:
          PYTHONPATH: $(pwd)/libs
          TEST_PARAM1: 37
          # The starting { means this has to be quoted.
          AN_ARRAY: "{hello world}"

        cmds:
          - for value in ${AN_ARRAY[@]}; do echo $value; done
          - python3 mytest.py

Each set variable is set (and \_exported) in the order given.

.. code:: bash

    #!/bin/bash

    export PYTHONPATH=$(pwd)/libs
    export TEST_PARAM1=37
    export AN_ARRAY={hello world}

    for value in ${AN_ARRAY[@]}; do echo $value; done
    python3 mytest.py

Escaping
~~~~~~~~

Values are not quoted. If they need to be, you'll have to quote them
twice, once for YAML and once for the quotes you actually need.

.. code:: yaml


    quote_example:
      run:
        env:
          DQUOTED: '"This will be in double quotes. It is a literal string as far
                   as YAML is concerned."'
          SQUOTED: "'This $VAR will not be resolved in bash, because this is single
                   quoted.'"
          DDQUOTED: """Double quotes to escape them."""
          SSQUOTED: '"That goes for single quotes '' too."'
          NO_QUOTES: $(echo "YAML only quotes things if the first character
          is a quote. These are safe.")

.. code:: bash

    #/bin/bash

    export DQUOTED="This will be in double quotes. It is a literal string as far as YAML is concerned."
    export SQUOTED='This $VAR will not be resolved in bash, because this is single quoted.'
    export DDQUOTED="Double quotes to escape them."
    export SSQUOTED="That goes for single quotes '' too."
    export NO_QUOTES=$(echo "YAML only quotes things if the first character is a quote. These are safe.")


.. _tests.env.modules:

Modules
-------

Many clusters employ module systems to allow for easy switching between
build environments. Pavilion supports both the environment (TCL) and the
LMOD module systems, but other module systems can be supported by
overriding the base :ref:`plugins.module_wrappers`.

Loading modules
~~~~~~~~~~~~~~~

In either *run* or *build* configs, you can have Pavilion import modules
by listing them (in the order needed) under the *modules* attribute.

.. code:: yaml

    module_example:
      build:
        modules: [gcc, openmpi/2.1.2]

In the generated build script, each of these modules will be both loaded
and checked to see if they were actually loaded.

.. code:: bash

    #/bin/bash

    TEST_ID=$1

    module load gcc
    # This checks to make sure the module was loaded. If it isn't the script
    # exits and updates the test status.
    is_module_loaded gcc $TEST_ID

    module load openmpi/2.1.2
    is_module_loaded openmpi/2.1.2 $TEST_ID

Other Module Manipulations
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also unload and swap modules.

.. code:: yaml

    module_example2:
      build:
        source_location: test_code.xz
      run:
        # This assumes gcc and openmpi are already loaded by default.
        modules: [gcc->intel/18.0.4, -openmpi, intel-mpi]
        cmds:
          - $MPICC -o test_code test_code.c

Module Wrappers
---------------

Module wrappers allow you to change how Pavilion loads specific modules,
module versions, and even modules in general. The default module wrapper
provides support for lmod and tmod, generates the source to load
modules within run and build scripts, and checks to see if they've been
successfully loaded (or unloaded).

For more information on writing these, see :ref:`plugins.module_wrappers`.
