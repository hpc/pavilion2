.. _tests.suites:

Suite Organization
==================

This section details the organization of test suites.

.. contents::


.. _tests.suites.suite_directories:

Suite Directories
-----------------

In addition to simple tests, Pavilion provides the option to organize suites using a directory
structure, such that the suite directory contains not only the test config, but any host, mode,
and OS configs associated with the test, as well as test source code. This provides a convenient
way of collecting the test code and data in a single location. This is useful, for instance, if the
user wishes to version control each test separately and use it as a Git submodule in a larger
project.

.. _tests.suites.organizing_suites:

Two Ways of Organizing Suites
-----------------------------

All test suites reside in the `suites` directory under one of the user's configuration directories.
There are two ways of organizing these suites, depending on the user's needs and the complexity of
the suite:

1. A simple suite may consist of a single suite config, `<suite_name>.yaml`, placed directly in the
`suites` directory.

2. Suites consisting of multiple files, including additional configs and test source, should be
placed under a subdirectory of `suites`, `suites/<suite_name>/`.

In the latter case, arbitrary files may be placed in the subdirectory, but it **must** contain a
suite config named `suite.yaml`. In both cases, the suite config follows the format described in
the previous section. Note the difference in file name between the two organization methods: in the
first, the name of the file is the name of the suite; in the second, the file name is the generic
`suite.yaml`, and Pavilion derives the suite name from its containing directory.

.. admonition:: Deprecation Warning
    :class: warning

    Pavilion 2.4 uses the `tests` and `test_src` subdirectories to store suite configs and test
    source code respectively. As of the latest release, these directories are deprecated in favor
    of the single `suites` directory, and support for them will eventually be removed.

.. _tests.suites.auxiliary_configs:

Host, OS, and Mode Configs
--------------------------

When using the first organization method, host, OS, and mode configs must be placed under their
respective subdirectories under the user's config directory and must be named with the name of
their associated host, operating system, or mode.

When using the second, suite directory method of organization, auxiliary configs must be placed
in the suite directory alongside the suite config and must be named `hosts.yaml`, `os.yaml`, or
`modes.yaml` according to their config type. **Note that these file names are plural**. These
configs override configs placed in the `hosts`, `os`, and `modes` subdirectories under the
configuration directories.

The suite directory method of organization allows for more flexibility in these auxiliary configs.
Specifically, multiple hosts, OSs, or modes may be specified in a config file. A single host, OS,
or mode can be selected on test invocation by passing the name of the host, OS, or mode to the
appropriate flag (either `-H`, `-o`, or `-m`). The following is an example of a host file
containing multiple host entries (OS and mode formats are analogous):

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

Note that this format differs from the format used by configs located in the `hosts`, `os`, and
`modes` directories; in this case, individual configs within each config file derive their names
from top-level keys rather than from the name of the config file.
