# Pavilion

Pavilion is a Python 3 (3.5+) based framework for running and analyzing 
tests targeting HPC systems. It provides a rich YAML-based configuration 
system for wrapping test codes and running them against various systems.
The vast majority of the system is defined via plugins,, giving users the 
ability to extend and modify Pavilion's operation to suit their needs. 
Plugin components include those for gathering system data, adding 
additional schedulers, parsing test results, and more.

## Project goals:
 - Robust testing in postDST, automated, and acceptance testing
 (system validation) scenarios.
 - End-to-end status tracking for all tests.
 - Simple, powerful test configuration language.
 - System agnostic test configs.
   - Hide common platform and environment idiosyncrasies from tests.
   - System specific defaults.
 - Eliminate unnecessary build repetition.
 - Extreme extensibility (plugins everywhere). 

## Documentation 
The [general documentation](https://pavilion2.readthedocs.io/en/latest/) is 
available via readthedocs, along with documentation for the Pavilion code 
itself.

