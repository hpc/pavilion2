"""The script composer makes it easy to build up a script with a
prescribed environ in a programmatic way.

It also handles translating our module specifications into
specific actions to add to the script."""

from pathlib import Path

from pavilion import module_wrapper
from pavilion.module_actions import ModuleAction


class ScriptComposerError(RuntimeError):
    """Class level exception during script composition."""


class ScriptHeader:
    """Class to serve as a struct for the script header."""

    def __init__(self, shebang='#!/bin/bash', scheduler_headers=None):
        """The header values for a script.
        :param string shebang: Shell path specification.  Typically
                                  '/bin/bash'.  default = None.
        :param list scheduler_headers: List of lines for scheduler resource
                                       specifications.
        """
        self._scheduler_headers = None
        self.scheduler_headers = scheduler_headers

        # Set _shebang so that style_check doesn't complain at the setter block.
        self._shebang = None
        self.shebang = shebang

    @property
    def shebang(self):
        """Function to return the value of the internal shell path variable."""
        return self._shebang

    @shebang.setter
    def shebang(self, value):
        """Function to set the value of the internal shell path variable."""
        self._shebang = value

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
        if self.shebang[:2] != '#!':
            ret_list = ['#!{}'.format(self.shebang)]
        else:
            ret_list = [self.shebang]

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


class NoHeader(ScriptHeader):
    """Class for no file header.
    None.
    """
    @property
    def shebang(self):
        pass

    @shebang.setter
    def shebang(self, comment):
        pass

    def get_lines(self):
        pass


class ScriptComposer:
    """Manages the building of bash scripts for Pavilion."""

    def __init__(self, header=None):
        """Function to initialize the class and the default values for all of
        the variables.

        :param ScriptHeader header: The header class to use. Defaults to one
            that simply adds ``#!/bin/bash`` as the file header.
        :param ScriptDetails details: The metadata class to use.
        """

        if header is None:
            header = ScriptHeader()

        self.header = header

        self._script_lines = []

    def env_change(self, env_dict):
        """Function to take the environment variable change requested by the
        user and add the appropriate line to the script.

        :param dict env_dict: A dictionary (preferably an OrderedDict) of
            environment keys and values to set. A value of None will unset the
            variable.
        """

        for key, value in env_dict.items():

            if value is not None:
                self._script_lines.append('export {}={}'.format(key, value))
            else:
                self._script_lines.append('unset {}'.format(key))

    @staticmethod
    def parse_module(mod_line):
        """Parse a module specification into it's components. These can come
in one of three formats:

1. 'mod-name[/version]' - Load the given module name and version
2. '-mod-name[/version]' - Unload the given module/version.
3. 'old_name[/old_vers]->mod-name[/version]' - Swap the given old
   module for the new one.

:param str mod_line: String provided by the user in the config.
:rtype: (str, (str, str), (str, str))
:return: action, (name, vers), (old_name, old_vers)
"""
        old_mod = None
        if '->' in mod_line:
            old_mod, mod = mod_line.split('->')
            action = 'swap'
        elif mod_line.startswith('-'):
            action = 'unload'
            mod = mod_line[1:]
        else:
            action = 'load'
            mod = mod_line

        if '/' in mod:
            mod_name, mod_vers = mod.rsplit('/', 1)
        else:
            mod_name = mod
            mod_vers = None

        if old_mod is not None:
            if '/' in old_mod:
                old_mod_name, old_mod_vers = old_mod.rsplit('/', 1)
            else:
                old_mod_name = old_mod
                old_mod_vers = None

            return action, (mod_name, mod_vers), (old_mod_name, old_mod_vers)
        else:
            return action, (mod_name, mod_vers), (None, None)

    def module_change(self, module, sys_vars):
        """Take the module changes specified in the user config and add the
        appropriate lines to the script. This will parse the module name into
        various actions, find the appropriate module_wrapper plugin, and use
        that to get the lines to add to the script.

        :param str module: Name of a module or a list thereof in the format
            used in the user config.
        :param dict sys_vars: The pavilion system variable dictionary.
        """

        action, (name, version), (oldname, oldver) = self.parse_module(module)

        module_obj = module_wrapper.get_module_wrapper(name, version)

        if action == 'load':
            mod_act, mod_env = module_obj.load(sys_vars, version)

        elif action == 'unload':
            mod_act, mod_env = module_obj.unload(sys_vars, version)
        elif action == 'swap':
            mod_act, mod_env = module_obj.swap(sys_vars,
                                               oldname,
                                               oldver,
                                               requested_version=version)
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
        """Add a line unadulterated to the script lines.

        :param str command: String representing the whole command to add.
        """
        if isinstance(command, list):
            for cmd in command:
                self._script_lines.append(cmd)
        elif isinstance(command, str):
            self._script_lines.append(command)

    def write(self, path: Path):
        """Function to write the script out to file.

        :return bool result: Returns either True for successfully writing the
                             file or False otherwise.
        """

        with path.open('w') as script_file:
            script_file.write('\n'.join(self.header.get_lines()))
            script_file.write('\n\n')

            script_file.write('\n'.join(self._script_lines))
            script_file.write('\n')

        # Make the file executable.
        path.chmod(path.stat().st_mode | 0o110)
