.. _tests.suites:

Suite Organization
==================

This section details the organization of test suites.

.. contents::


.. _tests.suites.suite_directories:

Suite Directories
-----------------

In addition to single-file test suites, Pavilion provides the option to organize more complex
suites using a directory structure. Under this structure, each suite directory contains not only
the suite config YAML file, but also any host, mode, and OS configs associated with the suite,
along with any source code required by the suite's tests. This provides a convenient way of
collecting the test code and data in a single location. This is useful, for instance, if the
user wishes to version control each test separately and use it as a Git submodule in a larger
project.

.. _tests.suites.organizing_suites:

Two Ways of Organizing Suites
-----------------------------

All test suites reside in the ``suites`` directory under one of the user's configuration
directories. There are two ways of organizing these suites, depending on the user's needs and the
complexity of the suite:

1. A simple suite may consist of a single suite config, ``<suite_name>.yaml``, placed directly in
the ``suites`` directory. This method is useful for tests that do not require source code or other
files.

2. Suites consisting of multiple files, including additional configs and source code, should be
placed under a subdirectory of ``suites``, ``suites/<suite_name>/``. Arbitrary files may be placed
in this subdirectory, but the subdirectory **must** contain at minimum a suite config named
``suite.yaml``.

In both cases, the suite config follows the format described in the :ref:`tests.format` section.
Note the difference in file name between the two organization methods: in the first, the name of
the file is the name of the suite; in the second, the file name is the generic ``suite.yaml``, and
Pavilion derives the suite name from the file's parent directory.

.. admonition:: Deprecation Warning
    :class: warning

    Pavilion previously used the ``tests`` and ``test_src`` subdirectories to store suite configs
    and test source code. These directories are now deprecated in favor of the single
    ``suites`` directory, and support for them is planned for eventual removal. While the older
    organization structure continues to be supported, users should plan on reorganizing existing
    tests using the new structure.

.. _tests.suites.auxiliary_configs:

Host, OS, and Mode Configs
--------------------------

When using the first organization method, host, OS, and mode configs must be placed under their
respective subdirectories (``hosts``, ``os``, or ``modes``) under the user's config directory
and must be named according to their associated host, operating system, or mode.

When using the second, suite directory method of organization, suite-specific auxiliary configs may
optionally be placed in the suite directory alongside the suite config itself. These configs may be
used to define test-specific options and variables that vary by host or OS, without cluttering
global host, OS, or mode configs with test-specific variables. These configs extend, rather than
override, configs placed in the ``hosts``, ``os``, and ``modes`` directories.

This method is especially useful in combination with the submodule-based test structure described
above, since it allows host-specific test options and variables to be version controlled along with
the suite config while maintaining independence from global configs.

If used, these suite-specific configs must be named ``hosts.yaml``, ``os.yaml``, or ``modes.yaml``,
depending on their config type. **Note that these file names are plural**.

The directory method of organization allows multiple hosts, OSs, or modes to be specified in a
single config file. Pavilion discovers host and OS config files automatically based on the detected
host and OS, but specific hosts and OSs, as well as modes, can be selected on test invocation by
passing the name of the host, OS, or mode to ``pav run`` using the appropriate flag (either ``-H``,
``-o``, or ``-m``). The following is an example of a host file containing multiple host entries (OS
and mode formats are analogous):

.. code-block:: yaml

    host1:
        scheduler: slurm
        slurm:
            partition: user
            qos: user
    host2:
        scheduler: raw
        variables:
            foo: bar

Note that this format differs from the format used by configs located in the ``hosts``, ``os``, and
``modes`` directories; in this case, the config file consists of a series of key–value pairs, where
the keys are the names of hosts (or OSs or modes) and the values are individual host configs. This
is necessary even in configs containing only a single host, since configs derive their names from
the top-level keys.
