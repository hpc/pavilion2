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

import os, datetime, grp, pwd, stat
from collections import OrderedDict
from pavilion.module_actions import ModuleAction
import pavilion.module_wrapper
from yapsy import PluginManager

""" Class to allow for scripts to be written for other modules.
    Typically, this will be used to write bash or batch scripts. 
"""

def get_action( mod_line ):
    """Function to return the type of action requested by the user for a
       given module, using the pavilion configuration syntax.  The string can
       be in one of three formats:
       1) '[mod-name]' - The module 'mod-name' is to be loaded.
       2) '[old-mod-name]->[mod-name]' - The module 'old-mod-name' is to be
                                         swapped out for the module 'mod-name'.
       3) '-[mod-name]' - The module 'mod-name' is to be unlaoded.
       :param str mod_line: String provided by the user in the config.
       :return object action: Return the appropriate object as provided by
                              the module_actions file.
    """
    if '->' in mod_line:
        return 'swap'
    elif mod_line.startswith( '-' ):
        return 'unload'
    else:
        return 'load'

def get_name( mod_line ):
    """Function to return the name of the module based on the config string
       provided by the user.  The string can be in one of three formats:
       1) '[mod-name]' - The module 'mod-name' is the name returned.
       2) '[old-mod-name]->[mod-name]' - The module 'mod-name' is returned.
       3) '-[mod-name]' - The module 'mod-name' is the name returned.
       :param str mod_line: String provided by the user in the config.
       :return str modn_name: The name of the module to be returned.
    """
    if '->' in mod_line:
        return mod_line[mod_line.find('->')+2,]
    elif mod_line.startswith('-'):
        return mod_line[1:]
    else:
        return mod_line

def get_old_swap( mod_line ):
    """Function to return the old module name in the case of a swap.
       :param str mod_line: String provided by the user in the config.
       :return str mod_old: Name of module to be swapped out.
    """
    return mod_line[:mod_line.find('->')-1]


class moduleManager( PluginManager ):
    """Class to inherit from and manage the plugin manager for the module
       plugins.  Assumes that the module plugins will be kept in the
       '${pav-root}/lib/pavilion/modules' directory.
    """

    def __init__( self ):
        super( moduleManager ).__init__()

        plugin_dir = os.path.dirname( os.path.abspath( __file__ ) ) +\
                     '/modules'

        self.setPluginPlaces( [ plugin_dir ] )

        self.collectPlugins()

        for mod in self.getAllPlugins():
            modname = mod.plugin_object.module
            self._mod_map[ modname ] = mod.plugin_object

    @property
    def mod_map( self ):
        return self._mod_map


class scriptHeader( object ):
    """Class to serve as a struct for the script header."""

    def __init__( self, shell_path=None, scheduler_macros=None ):
        """Function to set the header values for the script.
        :param string shell_path: Shell path specification.  Typically
                                  '/bin/bash'.  default = None.
        :param OrderedDict scheduler_macros: Scheduler macros.  If there are
                                             elements that are only one entry,
                                             the value will just be None.
                                             default = None.
        """
        self.shell_path = shell_path
        self.scheduler_macros = scheduler_macros

    @property
    def shell_path( self ):
        """Function to return the value of the internal shell path variable."""
        return self._shell_path

    @shell_path.setter
    def shell_path( self, value ):
        """Function to set the value of the internal shell path variable."""
        if value is not None and not isinstance(value, str):
            error = "Shell Path must be of type 'str', not {}".format(
                    type( value ) )
            raise TypeError( error )

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
        if value is not None and not isinstance(value, OrderedDict):
            error = "Scheduler Macro must be of type 'OrderedDict', not " +\
                    "{}".format( type( value ) )
            raise TypeError( error )

        self._scheduler_macros = value

    def reset( self ):
        """Function to reset the values of the internal variables back to
        None.
        """
        self.__init__()


class scriptDetails( object ):
    """Class to contain the final details of the script."""

    def __init__( self, 
                  name="_".join( datetime.datetime.now().__str__().split() ),
                  script_type="bash",
                  user=str( os.environ['USER'] ),
                  group=str( os.environ['USER'] ),
                  owner_perms=7,
                  group_perms=5,
                  world_perms=0 ):
        """Function to set the final details of the script.
        :param string name: Specify a name for the script. 
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

    @property
    def name( self ):
        return self._name

    @name.setter
    def name( self, value ):
        if not isinstance( value, str ):
            error = "Name must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._name = value

    @property
    def script_type( self ):
        return self._script_type

    @script_type.setter
    def script_type( self, value ):
        if not isinstance( value, str ):
            error = "Script type must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._script_type = value

    @property
    def user( self ):
        return self._user

    @user.setter
    def user( self, value ):
        if not isinstance( value, str ):
            error = "User must be of type 'str' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        self._user = value

    @property
    def group( self ):
        return self._group

    @group.setter
    def group( self, value ):
        if not isinstance( value, str ):
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
        if value < 0 or value > 7:
            error = "Owner permissions must be between 0 and 7, inclusive."
            raise ValueError( error )
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
        if value < 0 or value > 7:
            error = "Group permissions must be between 0 and 7, inclusive."
            raise ValueError( error )
        self._group_perms = value

    @property
    def world_perms( self ):
        return self._world_perms

    @world_perms.setter
    def world_perms( self, value ):
        if not isinstance( value, int ):
            error = "World permissions must be of type 'int' and not " +\
                    "{}.".format( type( value ) )
            raise TypeError( error )
        if value < 0 or value > 7:
            error = "World permissions must be between 0 and 7, inclusive."
            raise ValueError( error )
        self._world_perms = value

    def reset( self ):
        self.__init__()


class scriptComposer( object ):

    def __init__( self ):
        """Function to initialize the class and the default values for all of
        the variables.
        """

        self._header = scriptHeader()

        self._details = scriptDetails()

        self._script_lines = []

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
    def details( self ):
        return self._details

    @details.setter
    def details( self, details_obj ):
        if not isinstance( details_obj, scriptDetails ):
            error = "Tried to assign non-scriptDetails object {}".format(
                        type( details_obj ) ) + " to the details variable."
            raise TypeError( error )
        self._details = details_obj

    def reset( self ):
        """Function to reset all variables to the default."""
        self.__init__()

    def envChange( self, env_mod ):
        """Function to take the environment variable change requested by the
        user and add the appropriate line to the script.
        :param Union(dict, OrderedDict) env_mod: String representing an environment
                                         variable to be unset (prepended with
                                         a '-') or a dictionary defining the
                                         variable to be set or modified as the
                                         key and the value to assign as the
                                         value.
        """
        if not isinstance( env_mod, dict ) or issubclass( env_mod, dict ):
            error = "Environment modifications must be provided as a " +\
                    "dict or subclass.  {} is of type {}.".format( env_mod,
                                                              type( env_mod ) )
            raise TypeError( error )

        for item, val in env_mod.items():
            if val is not None:
                self._script_lines.append( 'export {}={}'.format( item, val ) )
            else:
                self._script_lines.append( 'unset {}'.format( item ) )

    def moduleChange( self, mod_name ):
        """Function to take the module changes specified in the user config
        and add the appropriate lines to the script.
        :param Union(list, str) mod_name: Name of a module or a list thereof in
                                          the format used in the user config.
        """

        mod_obj_list = []

        for mod in mod_name:
            self.addNewline()
            fullname = get_name( mod )
            if '/' in fullname:
                name, version = fullname.split('/')
            else:
                name = fullname
                version = None
            action = get_action( mod )

            module_obj = module_wrapper.get_module_wrapper( name, version )

            if action == 'load':
                mod_act, mod_env = module_obj.load()

                for act in mod_act:
                    if isinstance( act, str ):
                        self._script_lines.append( act )
                    elif issubclass( act, ModuleAction ):
                        self._script_lines.extend( [ act.action(),
                                                     act.verify() ] )

                self.envChange( mod_env )

            elif action == 'unload':
                mod_act, mod_env = module_obj.unload()

                for act in mod_act:
                    if isinstance( act, str ):
                        self._script_lines.append( act )
                    elif issubclass( act, ModuleAction ):
                        self._script_lines.extend( [ act.action(),
                                                     act.verify() ] )

                self.envChange( mod_env )

            elif action == 'swap':
                old = get_old_swap( mod )
                if '/' in old:
                    oldname, oldver = old.split('/')
                else:
                    oldname = old
                    oldver = None

                mod_act, mod_env = module_obj.swap( old_module_name=oldname,
                                                    old_version=oldver )

                for act in mod_act:
                    if isinstance( act, str ):
                        self._script_lines.append( act )
                    elif issubclass( act, ModuleAction ):
                        self._script_lines.extend( [ act.action(),
                                                     act.verify() ] )

                self.envChange( mod_env )

    def addNewline( self ):
        """Function that just adds a newline to the script lines."""
        self._script_lines.append('\n')

    def addComment( self, comment ):
        """Function for adding a comment to the script.
        :param str comment: Text to be put in comment without the leading '# '.
        """
        if not isinstance( comment, str ):
            error = "Comments must be of type 'str', which {} isn't.".format(
                                                                      comment )
            raise TypeError( error )

        self._script_lines.append( "# " + comment )

    def addCommand( self, command ):
        """Function to add a line unadulterated to the script lines.
        :param str command: String representing the whole command to add.
        """
        if not isinstance( command, str ) or not isinstance( command, list ):
            error="Command must be of type 'str' or 'list' and not {},".format(
                  command ) + " which is of type {}.".format( type( command ) )
            raise TypeError( error )
        elif isinstance( command, list ):
            for cmd  in command:
                if not isinstance( cmd, str ):
                    error = "Commands must be of type 'str' and not {}".format(
                            cmd ) + ", which is of type {}.".format(type(cmd))
                    raise TypeError( cmd )
                self._script_lines.append( cmd )
        elif isinstance( command, str ):
            self._script_lines.append( command )

    def writeScript( self, dirname=os.getcwd() ):
        """Function to write the script out to file.
        :param string dirname: Directory to write the file to.  default=$(pwd)
        :return bool result: Returns either True for successfully writing the
                             file or False otherwise.
        """

        file_name = self.details.name

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

        lineList = []

        if self.header.shell_path is not None:
            lineList.append( "#!{}\n".format( self.header.shell_path ) )

        if self.header.scheduler_macros is not None:
            for keyname in self.header.scheduler_macros.keys():
                macro_str = "# " + keyname + " " + \
                            self.header.scheduler_macros[keyname] + "\n"
                lineList.append( macro_str )

        lineList.append( "\n" )
        lineList.extend( self._script_lines )

        script_file.writelines( lineList )

        scriptfno = script_file.fileno()

        permission_val = 100 * self.details.owner_perms +\
                          10 * self.details.group_perms +\
                               self.details.world_perms

        fperm_val = 0

        if self.details.owner_perms in [ 1, 3, 5, 7 ]:
            fperm_val += stat.S_IXUSR

        if self.details.owner_perms in [ 2, 3, 6, 7 ]:
            fperm_val += stat.S_IWUSR

        if self.details.owner_perms in [ 4, 5, 6, 7 ]:
            fperm_val += stat.S_IRUSR

        if self.details.group_perms in [ 1, 3, 5, 7 ]:
            fperm_val += stat.S_IXGRP

        if self.details.group_perms in [ 2, 3, 6, 7 ]:
            fperm_val += stat.S_IWGRP

        if self.details.group_perms in [ 4, 5, 6, 7 ]:
            fperm_val += stat.S_IRGRP

        if self.details.world_perms in [ 1, 3, 5, 7 ]:
            fperm_val += stat.S_IXOTH

        if self.details.world_perms in [ 2, 3, 6, 7 ]:
            fperm_val += stat.S_IWOTH

        if self.details.world_perms in [ 4, 5, 6, 7 ]:
            fperm_val += stat.S_IROTH

        os.fchmod( scriptfno, fperm_val )

        if self.details.user == None:
            self.details.user = os.environ['USER']

        try:
            uid = pwd.getpwnam( self.details.user ).pw_uid
        except KeyError:
            error = "Username {} not found on this machine.".format(
                                                            self.details.user )
            raise ValueError( error )

        if self.details.group == None:
            self.details.group = os.environ['USER']

        try:
            grp_st = grp.getgrnam( self.details.group )
        except KeyError:
            error = "Group {} not found on this machine.".format(
                                                           self.details.group )
            raise ValueError( error )

        if self.details.user not in grp_st.gr_mem:
            error = "User {} is not in group {}.".format( self.details.user,
                                                          grp_st.gr_name )
            raise ValueError( error )

        gid = grp_st.gr_gid

        os.fchown( scriptfno, uid, gid )

        script_file.close()

        return True
