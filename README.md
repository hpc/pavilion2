====

 Software framework for running and analyzing jobs/tests targeting HPC systems.

- This tree all Python 2.7 based

Usage:
    "pth.py -h"

Collaboration:
  - new features that are sub-commands in the CLI add to the plugins directory or
    set the ENV variable PV_PLUGIN_DIR and place code there.
  - all remaining support code add to the modules directory or set the
    ENV variable PV_SRC_DIR and place code there.

Project goals included:
   - Support multiple schedulers/resource managers 
   - Very modular to encourage collaboration  
   - Make it simple to add tests, but highly configurable
   - Backward compatible (where reasonable) to the Gazebo test framework
   - Development adheres to a well know set of developemnt and coding principles.
   - Open source and managed thru git  
   - No Pavilion hook/config files necessary to be placed into users test/job directory
   - Only one command needed to run cli. Test handler runs under pth.py umbrella  
   - System config file and master config file separate, unlike one combined in Gazebo
