Pavilion HPC Testing Framework 

#  ###################################################################
#
#  Disclaimer and Notice of Copyright 
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC. 
#  This software was produced under U.S. Government contract 
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), 
#  which is operated by Los Alamos National Security, LLC for 
#  the U.S. Department of Energy. The U.S. Government has rights 
#  to use, reproduce, and distribute this software.  NEITHER 
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES 
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY 
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to 
#  produce derivative works, such modified software should be 
#  clearly marked, so as not to confuse it with the version 
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary 
#  forms, with or without modification, are permitted provided 
#  that the following conditions are met:
#  -  Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  -  Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  -  Neither the name of Los Alamos National Security, LLC, 
#     Los Alamos National Laboratory, LANL, the U.S. Government, 
#     nor the names of its contributors may be used to endorse 
#     or promote products derived from this software without 
#     specific prior written permission.
#   
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC 
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS 
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
#  OF SUCH DAMAGE.
#
#  ###################################################################


Built and tested with Python 2.7

File Structure:
--------------

   - all code resides under the PAV directory
     - PLUGINS sub-dir for new commands
     - SCRIPTS sub-dir for support scripts 
     - MODULES sub-dir for all custom built python src
     - SPECIAL-PKGS sub-dir for non-core Python packages

Getting Started:
---------------

 -  set *nix environment variable PVINSTALL to the install directory of Pavilion
 -  add $PVINSTALL/PAV to the PATH variable
 -  Pavilion runs at version 2.7 of Python, so if necessary, add the correct python bin early
    into the PATH search sequence.
 -  set the Pavilion output log environment variable PV_LOG, if not set will default
    to /tmp/$USER/pav.log.

  At this point you should be able to run "pav -h"

 - Pavilion is driven by a user defined test suite. Therefore, you need to create a user
   test suite config file with at least one test (or job) stanza in it.  An example exists in the docs directory.
   For each new job/test one only need to define what is different from the default test suite config file because the user
   test suite config file will inherit everything that is not explicity changed from the default config file. 
   This is basic YAML, a new test stanza is defined when a new id is encountered at the begining of a new line.

   So.... the recommended approach to this is:
     1) create a directory someplace to place your test_suite config files.
     2) copy the Example default test suite to this directory and name it
        default_test_config.yaml. Tweak it only where appropriate.
        HINT : quite possibly only the root results directory definition may need to change.
     3) cd to this directory.
     4) copy the default config file to a new file (for example, my_test_config_suite.yaml) 
     5) strip all the entries from this new file down to only the specific entires you need changed.
        Only the id, name, source_location, and run:cmd parts are required to be in each new stanza. 
        The id must be unique for each stanza.
     6) At this point you should have at least two files in this directory.  The default one (the
        exact name IS important) and your new one (this name is NOT important, but should end with ".yaml").

  - Type "pav view_test_suite ./my-test-config-suite.yaml" to see how your new test suite
    file is "folded" with the default file.  Add as may test stanzas as needed.

  - Type "pav run_test_suite ./my-test-config_suite.yaml" to run each test in the test suite. 
    Hint: making sure your jobs/tests work without Pavilion will save you time debugging problems.

  - Type "pav get_results -ts ./my-test-config_suite.yaml" to view your results. Notice the i, p, and
    f flags for this command.  There are very helpful if you want to see where the actual
    result data resides. 

  
Gazebo transition tips (for former users of Gazebo):

  - A Gazebo test suite can be converted to a Pavilion test suite using the "gzts2pvts"
    sub-command under "pav". Place this new converted file in the same directory as the default_test_config.yaml file.
    Edit it as needed, it may require some cleanup if the "gzts2pvts" couldn't figure out all the sub-parts.
    If you run this on a system where you had Gazebo configured and running it may be able to discover more of its parts.

  - There is no more $GZ_TMPLOGDIR. This directory used to reside under the working_space where, by default, any files
    placed there were copied to the final results directory. Now, If you want other data saved to the final results directory
    your run script can either place it there directly ($PV_JOB_RESULTS_LOG_DIR) OR any files listed in the
    working_space:save_from_ws section of the test suite will be moved there at job completion.


Job Output Data standardization:
---------------------------------

Pavilion interacts with test output via two basic pieces of data, results and trend data.  This data is simply printed
as a separate line to STDOUT by the job's run script and/or application.  

1) Results

To determine if a job passed for failed it must supply a pass/fail indicator and an optional summary reason.

Syntax -
<results> Pass|Fail, [reason]

Explanation - 
Pass/Fail - determined by individual test/job
reason - optional string (one line) summarizing pass or fail reason 

2) Trend data

Specific test/job related values are efficiently analyzed if they are reported as trend data.
Multiple trend data values can be saved for every test run. This data is
obviously unique to each application and is determined by the test/app developer.

Syntax -
<td> name[+target_item] value [units]

Explanation - 
<td> - tag used by the result parser. 
name - char string, up to 32 chars. Name of the value of
  interest. Referred to in Pavilion parlance as trend data.   
  Note - If name is followed by a "+" (no spaces) with a node name
  attached then an automated tool is available to create boxplots 
  for that that node. ( see get_results "-bp" argument )
value - char string, up to 64 chars
units - optional char string, up to 24 chars.
target_item - trend data is associtated with the test that produced it. To provide more specific association, 
  for example, to a node name, add this string to the end of the trend_data name field. The "+" is a reserved
  character! 
  ex. "<td> flop_rate+node005 743.2 Gflops"

Hints for viewing boxplots:
 To view from a machine with the showimage ( or xview on the Cray) tool
 - in the Boxplots directory of appropriate date run ...
 examples -
 find . -name \*.png -exec showimage {} \;
 or
 find  /tmp/Boxplots-02-24-2015T09:14:18:691101/ -name \*.png -exec showimage {} \;

Rules:
- One name value entry per line.
- The units field is optional.
- The <td> tag must start at the beginning of the line.
- Another line with a duplicate name  will be ignored.
- A Maximum of 4k entries are allowed per test. 
- No spaces are allowed in either the name or value field. 
- Underlines are recommended as opposed to dashes in the name field. 

Examples:
<td> IB0_max_rate 250 MB/sec
<td> IB1_max_rate 220 MB/sec
<td> n-n_write_bw_max 100 MB/sec
<td> phase_1_data 4700 
<td> phase_2_data 8200 

Querying Data Tip:
 Trend data can be culled using the get_results sub-command with the "-T" option.
 Data is harvested from the log files in the test results directory.


Debugging Tips:
----------------

As Pavilion runs an output log is being generated. It will default to
/tmp/$USER/pav.log, but can be changed by defining the env variable PV_LOG. 


Handy Stand-alone Utility Scripts:
---------------------------------

pvjobs - show job state on Moab systems.


Outstanding Items:
------------------

Interested in collaborating?  Fresh ideas, code improvements, new plugins, etc. are welcome.


1. Elegant way to handle building binaries on-the-fly with various libs/compilers and then create a
unique name to differentiate between these variations.

2. Handle Node/PE combinations using a range and step of values in addtion to
just the comma separated list of numbers that are supported now.

3. The Slurm scheduler job handling code needs to be developed, a skeleton exists.

4. Better way for saving the correct JobId value. Historically the Moab job id was written to the
log file. How should this be handled universally for all scheduler types?  The unix
process id is placed in the log file already.

5. Ditto for handling what Moab referred to as the segment name. A cluster can have 
multiple parts that can be targeted due to different features for the part.  Does target
cluster make sense still. 

6. Could always use some code refactoring or just general code reviewing.

7. Much in the way of handling all the posible error conditions that may arise if the test suite is
configured wrong. Much more unit testing needed here and overall.

8. Addition of Data analytic and Machine learning tools.
