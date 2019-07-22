![Pavilion Logo][logo]

LA-CC-15-041

Pavilion is a Python 3 (3.4+) based framework for running and analyzing 
tests targeting HPC systems. It provides a rich YAML-based configuration 
system for wrapping test codes and running them against various systems.
The vast majority of the system is pluggable, giving users the ability
to modify Pavilion's operation via easy to write plugins. This includes
components for gathering system data, adding additional schedulers, parsing 
test results, and more.

## Project Goals
 - Robust testing in postDST, automated, and acceptance testing
 (system validation) scenarios.
 - End-to-end status tracking for all tests.
 - Simple, powerful test configuration language.
 - System agnostic test configs.
   - Hide common platform and environment idiosyncrasies from tests.
   - System specific defaults.
 - Eliminate unnecessary build repetition.
 - Extreme extensibility (plugins everywhere). 

## Contents
 - [Home](index.md)
 - Setup
     - [Installation](INSTALL.md)
     - [Configuring Pavilion](config.md)
 - Usage
     - [Pavilion Basic Usage](basic.md)
     - [Pavilion Advanced Usage](advanced.md)
 - Writing Tests
     - [Basics](tests/basics.md)
     - [Building](tests/build.md)
     - [Running](tests/run.md)
     - [Environment](tests/env.md)
     - Scheduling
     - [Results](tests/results.md)
     - [Variables](tests/variables.md)
     - Permutations
     - Documentation
 - Plugins and Customization
     - System Variables
     - Module Wrappers
     - Result Parsers
     - Schedulers
     - [Commands](plugins/commands.md)


[logo]: imgs/logo.png
