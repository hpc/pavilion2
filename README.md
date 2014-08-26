====

 Software framework for running and analyzing jobs/tests targeting HPC systems.

- This tree all Python 2.7 based

Usage:
    module load python-epd  # on lanl toss systems to get required modules
    "pth -h"

Collaboration tips:
  - new features (sub-commands) add to the plugins directory or
    append to the ENV variable PV_PLUGIN_DIR and place code there.
  - all remaining support code add to the modules directory or append to the
    ENV variable PV_SRC_DIR and place code there.

Project goals:
   - Design to support multiple schedulers/resource managers 
   - Modular to encourage collaboration  
   - Simple to add tests, but highly configurable
   - Backward compatible (where reasonable) to the Gazebo test framework
   - Development adheres to a well know set of developemnt and coding principles
   - Open source and managed thru git  
   - No extra files necessary to be placed into users test/job directory to hook into Pavilion
   - Only one command needed to run cli. Test handler runs under "pth" umbrella  
   - Separate system config and master config files to isolate hardware specifics 
