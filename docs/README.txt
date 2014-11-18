Pavilion Test Harness 

Built and tested with Python 2.7

File Structure:
--------------
   - all code under the PAV directory
   - PLUGINS sub-dir for new commands
   - SCRIPTS sub-dir for support scripts 
   - MODULES sub-dir for all custom built python src
   - SPECIAL-PKGS sub-dir for non-core Python packages

Collaboration tips:
------------------

  - add new features (sub-commands) to the plugins directory or
    append a new path to the ENV variable PV_PLUGIN_DIR and place code there.
  - all new remaining support code add to the modules directory
  - support scripts in other languages place in the scripts directory

Getting Started:
---------------

 -  set nix environment variable PVINSTALL to the installation directory of Pavilion
 -  set PATH to include $PVINSTALL/PAV 
 -  Pavilion runs at version 2.7 of Python, so make sure that is early in your PATH too.

  At this point you should be able to run "pth -h"

 - Pavilion is centered around the idea of a user defined test suite. Therefore, you need to create a user
   test suite config file with at least one test (or job) stanza in it.  An example exists in the docs directory.
   You only need to define what is different from the default test suite config file because the user
   test suite config file will inherit everything that is not explicity changed from the default config file. 
   This is basic YAML, where a new test stanza is defined when a new id is encountered at the begining of a new line.

   So.... the recommended approach to this is:
     1) create a directory someplace to place your test_suite config files.
     2) copy the Example default test suite to this directory and name it
        default_test_config.yaml. Tweak it only where appropriate.
        HINT : quite possibly only the results root directory definition may need to change.
     3) cd to this directory.
     4) copy the default config file to a new file (for example, my_test_config_suite.yaml) 
     5) strip all the entries from this new file down to only the specific entires you need changed.
        Only the id, name, source_location, and run:cmd parts are required to be in each new stanza. 
        The id must be unique for each stanza.
     6) At this point you should have at least two files in this directory.  The default one (the
        exact name is important) and your new one (the name is not important).

  - Type "pth view_test_suite ./my-test-config-suite.yaml" to see how your new test suite
    file is "folded" with the default file.  Add as may test stanzas as needed.

  - Type "pth run_test_suite ./my-test-config_suite.yaml" to run your defined tests. 
    Hint: making sure your jobs work without Pavilion will save you time debugging problems.

  - Type "pth get_results ./my-test-config_suite.yaml" to view your results. Notice the i, p, and
    f flags to this command.  There are very helpful if you want to see where the actual
    result data resides. 

  
Gazebo transition tips:

  - A Gazebo test suite can be converted to a Pavilion test suite using the "gzts2pvts"
    sub-command under "pth". Make sure you place this new file in the same directory as the default_test_config.yaml file.
    Edit this file as necessary, it may require some cleanup if the "gzts2pvts" couldn't figure out all the parts.
    If you run this on a system where you were using Gazebo it may be able to discover more of its pieces.

  - There is no more $GZ_TMPLOGDIR. This directory used to reside under the working_space (which still exists) and any files
    placed there were copied to the final results directory. Now, If you want other data saved to the final results directory
    you can either place it there directly ($PV_JOB_RESULTS_LOG_DIR) OR any files listed in the working_space:save_from_ws   
    section of the test suite will be moved there at job end.


Output data standardization (trend data):
-----------------------------------------

Specific test/job related values can be recorded and analyzed if they are saved as trend data.
Trend data is important result information that is printed as a separate line to STDOUT.
Multiple trend data values can be saved for every test run. This data is determined by the
application developer.

Syntax:
<td> name value [units]

Explanation:
<td> - tag or marker used by the result parser.
name - char string, up to 32 chars. Name of the trend data item.   
value - char string, up to 64 chars
units - char string, up to 24 chars.

Rules:
- One name value entry per line.
- The units field is optional.
- The <td> tag must start at the beginning of the line.
- Another line with a duplicate name entry will be ignored.
- A Maximum of 4k entries are allowed per test. 
- No spaces are allowed in either the name or value. 
- Underlines are recommended as opposed to dashes in the name field. 

Examples:
<td> IB0_max_rate 250 MB/sec
<td> IB1_max_rate 220 MB/sec
<td> n-n_write_bw_max 100 MB/sec
<td> phase_1_data 4700 
<td> phase_2_data 8200 


Querying Data:
 Trend data can be viewed using the get_results sub-command with the "-T" option.
 Data is harvested from the log files in the test results directory.


Debug Tips:
----------------

As Pavilion runs an output log is being generated/accumulated into /tmp/${USER}/pth.log


Utility Scripts:
---------------

pvjobs - show what jobs are present on Moab systems.
