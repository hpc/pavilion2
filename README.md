Pavilion
========

Pavilion is a software framework for running and analyzing jobs/tests targeting HPC systems.

- Code all Python 2.7 based

Usage:
```sh
    set the ENV variable PVINSTALL to point to the installation directory 
    (for example - "setenv PVINSTALL /users/me/pavilion")
    add to your search path this directory plus "/PAV"
    (for example - "setenv PATH ${PVINSTALL}/PAV:${PATH}")
    run the tool - "pav -h"
```
Version
====

0.5X

====

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
   - Development adheres to a well know set of developemnt and coding principles
   - Open source and managed thru git  
   - No extra files necessary to be placed into users test/job directory to hook into Pavilion
   - Only one command needed to run cli. Sub commands under "pav" umbrella  

====

See the README.txt file in the docs directory for more detailed information


