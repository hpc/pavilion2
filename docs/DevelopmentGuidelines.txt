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
#
#  1. Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  2. Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  3. Neither the name of Los Alamos National Security, LLC, 
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


Guidlines to follow for cohesive team product development.


1. Code - Generally being developed in Python. However, in cases where a shell script or other language makes sense, use it.

1.1 Style

  Idiomatic Python - http://python.net/~goodger/projects/pycon/2007/idiomatic/handout.html

1.2 Language References 

 - http://www.greenteapress.com/thinkpython/thinkpython.pdf (nice, but more introductory)
 - http://www.diveintopython3.net


2. Coding Process/Philosphy
-------

2.1 Code Sharing 

2.1.1  To be stored github

2.1.2  Team development with Git - http://blog.ericbmerritt.com/2011/12/05/team-development-with-git.html

2.2 Directory Structure <INSTALL_DIR>/PAV

2.2.1 All source code under the PAV directory

2.2.1 Add new sub-commands in Plugins, with all "new" support code added to modules directory, under PAV.  

2.2.2 External packages (outside of the standard Python distro) collected under special_pkgs directory, under PAV 

2.3 Unit or Self testing to be used to verify correctness of code before any new release in test directory.

2.4 Use setting up and using Virtual Environments to improve development process 

 - http://jeffknupp.com/blog/2014/02/04/starting-a-python-project-the-right-way/ 

3. Adding new features (please do!)

 - If you want to add a new sub-command it gets placed in the plugins directory under PAV.
   Use one of the existing ones from the plugins directory as an example.
 - New Python code that is not a sub-command gets placed in the modules directory under PAV.
 - If a new feature to Pavilion requires extensive configuration settings, as opposed to arguments passed to it, 
   consider addition a new stanza/section to the default config YAML. A new scheduler of some type would probably
   be a case for this. Both Moab and LDMS use this method. 

4. Suggestions/Constructive Ideas

 - Please add new features to this software. Especially support for new schedulers, new results analysis tools, and
   more unit testing. Also, if you see code that you feel you can improve, have at it. Let us know what you are up by
   sending e-mail to gazebo@lanl.gov and note Pavilion in the subject line.  Code changes and updates to the main trunk of
   the source will be subject to a review for appropriateness.

Thanks,
The Pavilion Development Team
