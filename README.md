#Pavilion
=========

LA-CC-15-041

Pavilion is a software framework for running and analyzing jobs/tests targeting HPC systems.
> Python 2.7 based


Usage:
```sh
    set the ENV variable PVINSTALL to point to the installation directory 
    (for example - "setenv PVINSTALL /users/me/pavilion")
    add to your search path this directory plus "/PAV"
    (for example - "setenv PATH ${PVINSTALL}/PAV:${PVINSTALL}/PAV/scripts:${PATH}")
    create own default and test specific config files. See examples in $PVINSTALL/docs dir
    run the tool - "pav -h"
```

## Alternative execution method

An alternative run method has been added (06/21/18):
set the required environment variables:
```bash
export PVINSTALL=/path/to/repository
export PAV_CFG_ROOT=$PVINSTALL/test_suites
export PATH=$PATH:$PVINSTALL/PAV
```
This allows for the user to employ pre-existing test configurations.

From the command line, the machine, test, and modes can be specified.
 - Machine: specifies the machine on which the tests are run and sets an upper limit on nodes and submission times.
 - Modes: specifies different run modes including what partition or reservation on which to run the tests.
 - Tests: specifies the test to be run (i.e. - supermagic, imb, helloC, lustre-mount, etc.).

In addition, custom modifications can be specified in the command line call.  These take the form of:
```bash
-c *.slurm.num_nodes=4
```

Multiple custom modifications can be specified per command line call.
An example command line call that uses all of these is:
```bash
pav -n wolf -m prevent-maint -t imb -c *.slurm.num_nodes=all -c allreduce.source_location=/test/location run_test_suite
```

This will run the Intel MPI Benchmark test suite on Wolf using all available nodes with a different source
location than that specified in the pre-generated test configs in the PreventMaint reservation.

Version 1.1.2

> Verified to work with Moab scheduler thus far. 
> Support for both for Slurm and Raw in version 1.1.0.


Collaboration tips:

  - add new features (sub-commands) to the plugins directory or
    append new path to the ENV variable PV_PLUGIN_DIR and place code there.
  - all remaining support code add to the modules directory or append to the
    ENV variable PV_SRC_DIR and place code there.
  - add support scripts in other languages to the scripts directory

====

Project goals:

   - Support multiple schedulers/resource managers 
   - Modular to encourage collaboration  
   - Simple to add tests, but highly configurable
   - Backward compatible (where reasonable) to the Gazebo test framework
   - Development adheres to a well know set of developement and coding principles
   - Open source and managed thru git  
   - No extra files necessary to be placed into users test/job directory to hook into Pavilion
   - Only one command needed to run cli. Sub commands under "pav" umbrella  

====

See the README.txt file in the docs directory for more detailed information
