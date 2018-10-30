#!python

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

from __future__ import unicode_literals
import os, datetime

""" Class to allow for scripts to be written for other modules.
    Typically, this will be used to write bash or batch scripts. 
"""


class scriptHeader:
    """Class to serve as a struct for the script header."""

    @property
    def shell_path( self ):
        """Function to return the value of the internal shell path variable."""
        return self._shell_path

    @shell_path.setter
    def shell_path( self, value ):
        """Function to set the value of the internal shell path variable."""
        if value != None and not isinstance(value, unicode):
            error = "Shell Path must be of type 'str', not {}".format(
                    type( value ) )
            raise TypeError( error )
        else:
            print( "Successfully set the shell_path variable." )
        self._shell_path = value

    @property
    def scheduler_macros( self ):
        """Function to return the value of the internal scheduler macros
        variable.
        """
        return self._scheduler_macros

    @scheduler_macros.setter
    def scheduler_macros( self, value ):
        """Function to set the value of the internal scheduler macros
        variable.
        """
        if value != None and not isinstance(value, dict):
            error = "Scheduler Macro must be of type 'dict', not {}".format(
                    type( value ) )
            raise TypeError( error )
        else:
            print( "Successfully set the scheduler_macros variable." )
        self._scheduler_macros = value

    def __init__( self, shell_path=None, scheduler_macros=None ):
        """Function to set the header values for the script.
        :param string shell_path: Shell path specification.  Typically
                                  '/bin/bash'.  default = None.
        :param dict scheduler_macros: Scheduler macros.  If there are elements
                                      that are only one entry, the value will
                                      just be None.  default = None.
        """
        self.shell_path = shell_path
        self.scheduler_macros = scheduler_macros

#        return self

    def reset( self ):
        """Function to reset the values of the internal variables back to
        None.
        """
        self.__init__()


class scriptModules:
    """Class to serve as a struct for the script modules."""

    @property
    def explicit_specification( self ):
        return self._explicit_specification

    @explicit_specification.setter
    def explicit_specification( self, value ):
        """Function to set the explicit specification internal variable."""
        if value != None and not isinstance( value, list ):
            error = "Explicit specification must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._explicit_specification = value

    @property
    def purge( self ):
        return self._purge

    @purge.setter
    def purge( self, value ):
        """Function to set the purge internal variable."""
        if not isinstance( value, bool ):
            error = "Purge specification must be of type 'bool' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._purge = value

    @property
    def unloads( self ):
        return self._unloads

    @unloads.setter
    def unloads( self, value ):
        """Function to set the unloads internal variable."""
        if value != None and not isinstance( value, list ):
            error = "Unloads specification must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._unloads = value

    @property
    def loads( self ):
        return self._loads

    @loads.setter
    def loads( self, value ):
        """Function to set the loads internal variable."""
        if value != None and not isinstance( value, list ):
            error = "Loads specification must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._loads = value

    @property
    def swaps( self ):
        return self._swaps

    @swaps.setter
    def swaps( self, value ):
        """function to set the swaps internal variable."""
        if value != None and not isinstance( value, dict ):
            error = "Swaps specification must be of type 'dict' and not " +\
                    "{}.".format( type( value ) )
        self._swaps = value

    def __init__( self, explicit_specification=None, purge=False,
                  unloads=None, loads=None, swaps=None ):
        """Function to set the modules section for the script.
        :param list explicit_specification: List of commands to manage the
                                            modules explicitly.  default = None
        :param bool purge: Whether or not module purge will work on this
                           machine. default = False
        :param list unloads: List of modules to unload for the script. 
                             default = None.
        :param list loads: List of modules to load for the script. 
                           default = None.
        :param dict swaps: Dictionary of modules to swap.  The current module
                           should be the key and the module to replace it with
                           should be the value.  default = None.
        """
        self.explicit_specification = explicit_specification
        self.purge = purge
        self.unloads = unloads
        self.loads = loads
        self.swaps = swaps

        return self

    def reset( self ):
        self.__init__()

class scriptEnvironment:
    """Class to contain the environment variable changes for the script."""

    @property
    def sets( self ):
        return self._sets

    @sets.setter
    def sets( self, value ):
        """Function to set the internal sets variable."""
        if value != None and not isinstance( value, dict ):
            error = "Sets specification must be of type 'dict' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._sets( value )

    @property
    def unsets( self ):
        return self._unsets

    @unsets.setter
    def unsets_setter( self, value ):
        """Function to set the internal unsets variable."""
        if value != None and not isinstance( value, list ):
            error = "Unsets specification must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._unsets( value )

    def __init__( self, sets=None, unsets=None ):
        """Function to set and unset the environment variables.
        :param dict sets: Dictionary of environment variables to set where the
                          key is the environment variable and the value is the
                          value assigned to that variable.  default = None
        :param list unsets: List of environment variables to unset for the
                            script.  default = None
        """
        self.sets = sets
        self.unsets = unsets

        return self

    def reset( self ):
        self.__init__()


class scriptCommands:
    """Class to contain the script commands."""

    @property
    def commands( self ):
        return self._commands

    @commands.setter
    def commands( self, value ):
        """Function to set the internal commands variable."""
        if not isinstance( value, list ):
            error = "Commands must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._commands = value

    def __init__( self, commands=None ):
        """Function to specify the commands for the script.
        :param list commands: List of strings specifying the script commands
                              in order.  default = None
        """
        self.commands = commands

        return self

    def reset( self ):
        self.__init__()


class scriptPost:
    """Class to contain the post-script commands."""

    @property
    def commands( self ):
        return self._commands

    @commands.setter
    def commands( self, value ):
        """Function to set the internal commands variable."""
        if value != None and not isinstance( value, list ):
            error = "Commands must be of type 'list' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._commands = value

    def __init__( self, commands=None ):
        """Function to specify the commands to run at the end of the script
        for generic tasks.
        :param list commands: List of strings specifying the postscript
                              commands in order.  default = None
        """
        self.commands = commands

        return self

    def reset( self ):
        self.__init__()


class scriptDetails:
    """Class to contain the final details of the script."""

    @property
    def name( self ):
        return self._name

    @name.setter
    def name( self, value ):
        if not isinstance( value, unicode ):
            error = "Name must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._name = value

    @property
    def script_type( self ):
        return self._script_type

    @script_type.setter
    def script_type( self, value ):
        if not isinstance( value, unicode ):
            error = "Script type must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._script_type = value

    @property
    def user( self ):
        return self._user

    @user.setter
    def user( self, value ):
        if not isinstance( value, unicode ):
            error = "User must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._user = value

    @property
    def group( self ):
        return self._group

    @group.setter
    def group( self, value ):
        if not isinstance( value, unicode ):
            error = "Group must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._group = value

    @property
    def owner_perms( self ):
        return self._owner_perms

    @owner_perms.setter
    def owner_perms( self, value ):
        if not isinstance( value, int ):
            error = "Owner permissions must be of type 'int' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._owner_perms = value

    @property
    def group_perms( self ):
        return self._group_perms

    @group_perms.setter
    def group_perms( self, value ):
        if not isinstance( value, int ):
            error = "Group permissions must be of type 'int' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._group_perms = value

    @property
    def world_perms( self ):
        return self._world_perms

    @world_perms.setter
    def world_pers( self, value ):
        if not isinstance( value, int ):
            error = "World permissions must be of type 'int' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._world_perms = value

    def __init__( self, 
                  name="_".join( datetime.datetime.now().__str__().split() ),
                  script_type="bash",
                  user=os.environ['USER'],
                  group="",
                  owner_perms=7,
                  group_perms=5,
                  world_perms=0 ):
        """Function to set the final details of the script.
        :param string script_name: Specify a name for the script. 
                                   default = 'pav_(date)_(time)'
        :param string script_type: Type of script, determining an appropriate
                                   file ending.  default = bash
        :param string user: Name of user to set as owner of the file. 
                            default = current user
        :param string group: Name of group to set as owner of the file. 
                             default = user default group
        :param int owner_perms: Value for owner's permission on the file (see
                                `man chmod`).  default = 7
        :param int group_perms: Value for group's permission on the file (see
                                `man chmod`).  default = 5
        :param int world_perms: Value for the world's permission on the file
                                (see `man chmod`).  default = 0
        """
        self.name = name
        self.script_type = script_type
        self.user = user
        self.group = group
        self.owner_perms = owner_perms
        self.group_perms = group_perms
        self.world_perms = world_perms

        return self

    def reset( self ):
        self.__init__()


class scriptComposer( object ):

    @property
    def header( self ):
        return self._header

    @header.setter
    def header( self, header_obj ):
        if not isinstance( header_obj, scriptHeader ):
            error = "Tried to assign non-scriptHeader object {}".format(
                              type( header_obj ) ) + " to the header variable."
            raise TypeError( error )
        self._header = header_obj

    @property
    def modules( self ):
        return self._modules

    @modules.setter
    def modules( self, modules_obj ):
        if not isinstance( modules_obj, scriptModules ):
            error = "Tried to assign non-scriptModules object {}".format(
                            type( modules_obj ) ) + " to the modules variable."
            raise TypeError( error )
        self._modules = modules_obj

    @property
    def environment( self ):
        return self._environment

    @environment.setter
    def environment( self, environment_obj ):
        if not isinstance( environment_obj, scriptEnvironment ):
            error = "Tried to assign non-scriptEnvironment object {}".format(
                    type( environment_obj ) ) + " to the environment variable."
            raise TypeError( error )
        self._environment = environment_obj

    @property
    def commands( self ):
        return self._commands

    @commands.setter
    def commands( self, commands_obj ):
        if not isinstance( commands_obj, scriptCommands ):
            error = "Tried to assign non-scriptCommands object {}".format(
                          type( commands_obj ) ) + " to the commands variable."
            raise TypeError( error )
        self._commands = commands_obj

    @property
    def post( self ):
        return self._post

    @post.setter
    def post( self, post_obj ):
        if not isinstance( post_obj, scriptPost ):
            error = "Tried to assign non-scriptPost object {}".format(
                                  type( post_obj ) ) + " to the post variable."
            raise TypeError( error )
        self._post = post_obj

    @property
    def details( self ):
        return self._details

    @details.setter
    def details( self, details_obj ):
        if not isinstance( details_obj, scriptDetails ):
            error = "Tried to assign non-scriptDetails object {}".format(
                        type( details_obj ) ) + " to the details variable."
            raise TypeError( error )
        self._details = details_obj

    def __init__( self ):
        """Function to initialize the class and the default values for all of
        the variables.
        """

        self._header = scriptHeader()

        self._modules = scriptModules()

        self._environment = scriptEnvironment()

        self._commands = scriptCommands()

        self._post = scriptPost()

        self._details = scriptDetails()

        return self

    def writeScript( self, dirname=os.getcwd() ):
        """Function to write the script out to file.
        :param string dirname: Directory to write the file to.  default=$(pwd)
        :return bool result: Returns either True for successfully writing the
                             file or False otherwise.
        """

        file_name = self.details.script_name

        if not os.path.isabs( file_name ):
            file_name = os.path.join( dirname, file_name )

        if self.details.script_type == 'bash':
            file_name = file_name + '.sh'
        elif self.details.script_type == 'batch':
            file_name = file_name + '.batch'
        else:
            error = "Script type of {} is not recognized.".format(
                                                     self.details.script_type )
            raise TypeError( error )

        if os.path.isfile( file_name ):
            error = "Script file name {} exists.".format( file_name )
            raise TypeError( error )

        script_file = open( file_name, 'w' )

        if self.header.shell_path != None:
            script_file.write( self.header.shell_path )

        if self.header.scheduler_macros != None:
            for keyname in self.header.scheduler_macros.keys():
                macro_str = "# " + keyname + " " + \
                            self.header.scheduler_macros[keyname]
                script_file.write( macro_str )

        script_file.write("")

        if self.modules.explicit_specification != None:
            for module_spec in self.modules.explicit_specification:
                script_file.write( module_spec )
        else:
            if self.modules.purge:
                script_file.write( "module purge" )

            if self.modules.swaps != None:
                for mod_out, mod_in in self.modules.swaps.items():
                    script_file.write( "module swap {} {}".format( mod_out,
                                                                     mod_in ) )

            if self.modules.unloads != None:
                for module in self.modules.unloads:
                    script_file.write( "module unload {}".format( module ) )

            if self.modules.loads != None:
                for module in self.modules.loads:
                    script_file.write( "module load {}".format( module ) )

        script_file.write("")

        if self.environment.unsets != None:
            for unset in self.environment.unsets:
                script_file.write( "unset {}".format( unset ) )

        if self.environment.sets != None:
            for var, val in self.environment.sets:
                script_file.write( "export {}={}".format( var, val ) )

        script_file.write("")

        if self.commands.commands != None:
            for command in self.commands.commands:
                script_file.write( command )

        script_file.write("")

        if self.post.commands != None:
            for command in self.post.commands:
                script_file.write( command )

        scriptfno = script_file.fileno()

        os.fchmod( scriptfno,
                   100 * self.details.owner_perms +
                    10 * self.details.group_perms +
                         self.details.world_perms )

        uid = os.getuid()

        gid = pwd.getpwnam( os.environ['USER'] ).pw_gid

        os.fchown( scriptfno, uid, gid )

        script_file.close()

        return True
