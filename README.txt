Pavilion Test Harness 

Built and tested on Python 2.7

To Build a src distribution tar file:
  - edit the setup.py file appropriately
  - add files to include in MANIFEST.in file
  - from this directory run -> "python setup.py sdist"
  - tar file placed in "dist" directory

File Structure:
   - all source under the PAV directory
   - PLUGINS sub-dir for new commands
   - SCRIPTS sub-dir for non python tools
   - MODULES sub-dir for all custom built python src
   - SPECIAL-PKGS sub-dir for other used Python packages

Collaboration tips:

  - add new features (sub-commands) to the plugins directory or
    append a new path to the ENV variable PV_PLUGIN_DIR and place code there.
  - all remaining support code add to the modules directory

Getting Started:

 -  set ENV var PVINSTALL to the installation directory of Pavilion
 -  set PATH to include $PVINSTALL/PAV 

  At this point you should be able to run "pth -h"

 - Pavilion is centered around the idea of a user defined test suite. Therefore, you need to create a user
   test suite config file with at least one test (or job) stanza in it.  Some examples exist in the docs directory.
   You only need to define what is different from the default test suite config file because the user
   test suite config file will inherit everything that is not explicity changed from the default config file. 
   This is basic YAML, with a new test stanza is defined when a new id is encountered at the begining of a new line.

   So.... the recommended approach to this is:
     1) Create a directory someplace to place your test_suite config files.
     2) Copy the Example default test_suite to this directory, and name it
        default_test_config.yaml. Tweak it only where appropriate (like your results root directory).
     3) cd to this directory.
     4) copy the default config file to a new file (for example, my-test-config-suite.yaml) 
     5) strip all the entries from this new file down to only the specific entires you need changed.
        Only the id, name, source_location, and run:cmd parts are required to be in each stanza! 
     6) At this point you should have at least two files in this directory.  The default one (the
        exact  name is important) and your new one (the name is not important).

  - try "pth view_test_suite ./my-test-config-suite.yaml" to see how your new test suite
    file is "folded" with the default file.  Add some more test stanzas and try again.

  - try "pth run_test_suite ./my-test-config_suite.yaml" to actual run your defined jobs. 
    Hint: making sure you jobs run without Pavilion will save you time debugging problems.

  - try "pth get_results ./my-test-config_suite.yaml" to view you results.  

  
Tips:

  - If you have a Gazebo test suite you can convert it to a Pavilion test suite using the "gzts2pvts"
    sub-command under "pth". Make sure you place this file in a directory with a default_test_config.yaml file.
    Edit this file as necessary, it may require some cleanup if the "gzts2pvts" couldn't figure out all the parts.
    If you run this on a system that you have Gazebo all setup on it may be able to discover more of its parts.



