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

    def __init__(self, shebang='#!/bin/bash'):
        """The header values for a script.
        :param string shebang: Shell path specification.  Typically
                                  '/bin/bash'.  default = None.
        """

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

    def get_lines(self):
        """Function to retrieve a list of lines for the script header."""
        if self.shebang[:2] != '#!':
            ret_list = ['#!{}'.format(self.shebang)]
        else:
            ret_list = [self.shebang]

        return ret_list

    def reset(self):
        """Function to reset the values of the internal variables back to
        None.
        """
        self.__init__()


class ScriptComposer:
    """Manages the building of bash scripts for Pavilion."""

    def __init__(self, header=None):
        """Function to initialize the class and the default values for all of
        the variables.

        :param ScriptHeader header: The header class to use. Defaults to one
            that simply adds ``#!/bin/bash`` as the file header.
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
                # Auto quote variables that contain spaces if they aren't already
                # quoted.
                qvalue = str(value).strip()
                if qvalue and qvalue[0] not in ('"', "'") and ' ' in qvalue:
                    value = '"{}"'.format(qvalue)

                self._script_lines.append('export {}={}'.format(key, value))
            else:
                self._script_lines.append('unset {}'.format(key))

    def module_change(self, module, sys_vars, config_wrappers):
        """Take the module changes specified in the user config and add the
        appropriate lines to the script. This will parse the module name into
        various actions, find the appropriate module_wrapper plugin, and use
        that to get the lines to add to the script.

        :param str module: Name of a module or a list thereof in the format
            used in the user config.
        :param sys_vars: The pavilion system variable dictionary.
        :param config_wrappers: Moduler wrappers specified via config.
        """

        action, (name, version), (oldname, oldver) = module_wrapper.parse_module(module)

        module_obj = module_wrapper.get_module_wrapper(name, version, config_wrappers)

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
