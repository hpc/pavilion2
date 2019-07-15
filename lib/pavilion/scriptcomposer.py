import datetime
import grp
import os
from pathlib import Path

from pavilion import module_wrapper
from pavilion import utils
from pavilion.module_actions import ModuleAction


# Class to allow for scripts to be written for other modules.
# Typically, this will be used to write bash or batch scripts.


def get_action(mod_line):
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
    elif mod_line.startswith('-'):
        return 'unload'
    else:
        return 'load'


def get_name(mod_line):
    """Function to return the name of the module based on the config string
       provided by the user.  The string can be in one of three formats:
       1) '[mod-name]' - The module 'mod-name' is the name returned.
       2) '[old-mod-name]->[mod-name]' - The module 'mod-name' is returned.
       3) '-[mod-name]' - The module 'mod-name' is the name returned.
       :param str mod_line: String provided by the user in the config.
       :return str modn_name: The name of the module to be returned.
    """
    if '->' in mod_line:
        return mod_line[mod_line.find('->')+2:]
    elif mod_line.startswith('-'):
        return mod_line[1:]
    else:
        return mod_line


def get_old_swap(mod_line):
    """Function to return the old module name in the case of a swap.
       :param str mod_line: String provided by the user in the config.
       :return str mod_old: Name of module to be swapped out.
    """
    return mod_line[:mod_line.find('->')-1]


class ScriptComposerError(RuntimeError):
    """Class level exception during script composition."""


class ScriptHeader():
    """Class to serve as a struct for the script header."""

    def __init__(self, shell_path=None, scheduler_headers=None):
        """Function to set the header values for the script.
        :param string shell_path: Shell path specification.  Typically
                                  '/bin/bash'.  default = None.
        :param list scheduler_headers: List of lines for scheduler resource
                                       specifications.
        """
        self._shell_path = None
        self._scheduler_headers = None
        self.shell_path = shell_path
        self.scheduler_headers = scheduler_headers


    @property
    def shell_path(self):
        """Function to return the value of the internal shell path variable."""
        return self._shell_path

    @shell_path.setter
    def shell_path(self, value):
        """Function to set the value of the internal shell path variable."""
        if value is None:
            value = '#!/bin/bash'

        self._shell_path = value

    @property
    def scheduler_headers(self):
        """Function to return the list of scheduler header lines."""
        return self._scheduler_headers

    @scheduler_headers.setter
    def scheduler_headers(self, value):
        """Function to set the list of scheduler header lines."""
        if value is None:
            value = []

        self._scheduler_headers = value

    def get_lines(self):
        """Function to retrieve a list of lines for the script header."""
        if self.shell_path[:2] != '#!':
            ret_list = ['#!{}'.format(self.shell_path)]
        else:
            ret_list = [self.shell_path]

        for i in range(0, len(self.scheduler_headers)):
            if self.scheduler_headers[i][0] != '#':
                ret_list.append('# {}'.format(self.scheduler_headers[i]))
            else:
                ret_list.append(self.scheduler_headers[i])

        return ret_list

    def reset(self):
        """Function to reset the values of the internal variables back to
        None.
        """
        self.__init__()


class ScriptDetails():
    """Class to contain the final details of the script."""

    def __init__(self, path=None, group=None, perms=None):
        """Function to set the final details of the script.
        :param Union(str,Path) path: The path to the script file. default =
            'pav_(date)_(time)'
        :param string group: Name of group to set as owner of the file.
                             default = user default group
        :param int perms: Value for permission on the file (see
                          `man chmod`).  default = 0o770
        """
        self._path = None
        self._group = None
        self._perms = None
        self.path = path
        self.group = group
        self.perms = perms

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if value is None:
            value = "_".join(datetime.datetime.now().__str__().split())

        self._path = Path(value)

    @property
    def group(self):
        return self._group

    @group.setter
    def group(self, value):
        if value is None:
            value = utils.get_login()

        self._group = str(value)

    @property
    def perms(self):
        return self._perms

    @perms.setter
    def perms(self, value):
        if value is None:
            value = 0o770

        self._perms = oct(value)

    def reset(self):
        self.__init__()


class ScriptComposer():

    def __init__(self, header=None, details=None):
        """Function to initialize the class and the default values for all of
        the variables.
        """

        if header is None:
            header = ScriptHeader()

        self.header = header

        if details is None:
            details = ScriptDetails()
        self.details = details

        self._script_lines = []

    def reset(self):
        """Function to reset all variables to the default."""
        self.__init__()

    def env_change(self, env_dict):
        """Function to take the environment variable change requested by the
        user and add the appropriate line to the script.
        :param dict env_dict: A dictionary (preferably an OrderedDict) of
         environment keys and values to set. A value of None will unset the
         variable.
        """

        for key, value in sorted(env_dict.items()):
            if value is not None:
                self._script_lines.append('export {}={}'.format(key, value))
            else:
                self._script_lines.append('unset {}'.format(key))

    def module_change(self, module, sys_vars):
        """Function to take the module changes specified in the user config
        and add the appropriate lines to the script.
        :param str module: Name of a module or a list thereof in the format
         used in the user config.
        :param dict sys_vars: The pavilion system variable dictionary.
        """

        fullname = get_name(module)
        if '/' in fullname:
            name, version = fullname.split('/')
        else:
            name = fullname
            version = None
        action = get_action(module)

        module_obj = module_wrapper.get_module_wrapper(name, version)

        if action == 'load':
            mod_act, mod_env = module_obj.load(sys_vars, version)

        elif action == 'unload':
            mod_act, mod_env = module_obj.unload()

        elif action == 'swap':
            old = get_old_swap(module)
            if '/' in old:
                oldname, oldver = old.split('/')
            else:
                oldname = old
                oldver = None

            mod_act, mod_env = module_obj.swap(old_module_name=oldname,
                                               old_version=oldver)
        else:
            # This is not an expected error
            raise RuntimeError("Invalid Module action '{}'".format(action))

        for act in mod_act:
            if isinstance(act, ModuleAction):
                self._script_lines.extend(act.action())
                self._script_lines.extend(act.verify())
            else:
                self._script_lines.append(act)

        self.env_change(mod_env)

    def newline(self):
        """Function that just adds a newline to the script lines."""
        # This will create a blank line with just a newline.
        self._script_lines.append('')

    def comment(self, comment):
        """Function for adding a comment to the script.
        :param str comment: Text to be put in comment without the leading '# '.
        """
        self._script_lines.append("# {}".format(comment))

    def command(self, command):
        """Function to add a line unadulterated to the script lines.
        :param str command: String representing the whole command to add.
        """
        if isinstance(command, list):
            for cmd in command:
                self._script_lines.append(cmd)
        elif isinstance(command, str):
            self._script_lines.append(command)

    def write(self):
        """Function to write the script out to file.
        :return bool result: Returns either True for successfully writing the
                             file or False otherwise.
        """

        with self.details.path.open('w') as script_file:
            script_file.write('\n'.join(self.header.get_lines()))
            script_file.write('\n\n')

            script_file.write('\n'.join(self._script_lines))
            script_file.write('\n')

        os.chmod(str(self.details.path), int(self.details.perms, 8))

        try:
            grp_st = grp.getgrnam(self.details.group)
        except KeyError:
            error = ("Group {} not found on this machine."
                     .format(self.details.group))
            raise ScriptComposerError(error)

        gid = grp_st.gr_gid

        os.chown(str(self.details.path), os.getuid(), gid)
