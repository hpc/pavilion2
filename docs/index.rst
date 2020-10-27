Pavilion2
=========

Pavilion is a Python 3 (3.5+) based framework for running and analyzing
tests targeting HPC systems. It provides a rich YAML-based configuration
system for wrapping test codes and running them against various systems.
The vast majority of the system is defined via plugins, giving users
the ability to extend and modify Pavilion's operation to suit their
needs. Plugin components include those for gathering system data, adding
additional schedulers, parsing test results, and more.

Project goals:
--------------

-  Robust testing in postDST, automated, and acceptance testing (system
   validation) scenarios.
-  End-to-end status tracking for all tests.
-  Simple, powerful test configuration language.
-  System agnostic test configs.
-  Hide common platform and environment idiosyncrasies from tests.
-  System specific defaults.
-  Eliminate unnecessary build repetition.
-  Extreme extensibility (plugins everywhere).

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   install.rst
   basics.rst
   advanced.rst
   config.rst
   test_run_lifecycle.rst

.. toctree::
   :maxdepth: 2
   :caption: Test Configuration

   tests/index.rst

.. toctree::
   :maxdepth: 2
   :caption: Test Results Gathering

   results/index.rst

.. toctree::
   :maxdepth: 2
   :caption: Plugins

   plugins/index.rst

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/index.rst

.. toctree::
   :maxdepth: 2
   :caption: API Documentation

   source/index.rst

.. toctree::
   :maxdepth: 2
   :caption: For Developers:

   DevelopmentGuidelines.rst

.. toctree::
   :hidden:
   :caption: Index:

   genindex.rst
