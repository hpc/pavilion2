"""Performs various configuration directories related commands."""

# Pycharm says this isn't available in python 3.9+. It is wrong.
import grp
import sys
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Union

import yc_yaml as yaml
from pavilion import config
from pavilion import errors
from pavilion.output import fprint, draw_table
from pavilion.utils import get_login
from .base_classes import sub_cmd, Command


class ConfigCmdError(errors.PavilionError):
    """Raised for errors when creating configs."""


class ConfigCommand(Command):
    """Command plugin to perform various configuration directory tasks."""

    def __init__(self):
        super().__init__(
            name='config',
            description="Create or modify Pavilion configuration directories.",
            short_help="Perform various configuration tasks.",
            sub_commands=True)

    def _setup_arguments(self, parser):

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Action to perform"
        )

        create_p = subparsers.add_parser(
            'create',
            help="Create a new configuration dir, sub-folders, and config file.",
            description="Creates a new configuration directory at the given location with "
                        "the given label, and adds it to the root Pavilion config.")

        create_p.add_argument(
            '--working_dir',
            help='Set the given path as the working directory for this config dir.')

        create_p.add_argument(
            '--group',
            help="Set the group of the created directory to this group name, and set the "
                 "group sticky bit to the config dir and it's working dir (if given).")

        create_p.add_argument(
            'label',
            help="The label for this config directory, to uniquely identify run tests.")

        create_p.add_argument(
            'path', type=Path,
            help="Where to create the config directory.")

        setup_p = subparsers.add_parser(
            'setup',
            help="Setup a root pavilion config directory, including a new pavilion.yaml file.",
            description="As per 'create', except ignore any normally found pavilion.yaml and "
                        "create a new one in the the given location alongside the other created "
                        "files. Does not create a 'config.y"
        )
        setup_p.add_argument(
            '--group',
            help="Set the group of the created directory to this group name, and set the "
                 "group sticky bit to the config dir and it's working directory.")
        setup_p.add_argument(
            'path', type=Path,
            help="Where to create the config directory.")
        setup_p.add_argument(
            'working_dir', type=Path,
            help='Set the given path as general default working directory.')

        add_p = subparsers.add_parser(
            'add',
            help="Add the given path as a config directory in the root pavilion.yaml.",
            description="Add the given path as a config directory in the root pavilion.yaml.")
        add_p.add_argument("path", type=Path,
                           help="Path to the config directory to add. It must exist.")

        remove_p = subparsers.add_parser(
            'remove',
            help="Remove the given config dir path from the root pavilion.yaml",
            description="Remove the config config dir path from the root pavilion.yaml. The "
                        "directory itself is not removed.")
        remove_p.add_argument("config", help="Path or config label to remove.")

        subparsers.add_parser(
            'list',
            help="List the paths to the config directories, their labels, and working_dirs.")

    def run(self, pav_cfg, args):
        """Run the config command's chosen sub-command."""

        pav_cfg_file = pav_cfg.pav_cfg_file

        # This path is needed by (almost) all sub commands.
        if pav_cfg_file is None and args.sub_cmd != 'setup':
            fprint(sys.stderr,
                   "Main Pavilion config file path is missing. This would generally happen "
                   "when loading a pavilion.yaml manually (not through 'find_pavilion_config)")
            return 1

        return self._run_sub_command(pav_cfg, args)

    @sub_cmd()
    def _create_cmd(self, pav_cfg: config.PavConfig, args):

        label = args.label
        path: Path = args.path
        path = path.resolve()

        if args.group is not None:
            try:
                group = self.get_group(args.group)
            except ConfigCmdError as err:
                fprint(self.errfile, err)
                return 1
        else:
            group = None

        try:
            self.create_config_dir(pav_cfg, path, label, group, args.working_dir)
        except ConfigCmdError as err:
            fprint(self.errfile, err)
            return 1

        return 0

    @sub_cmd()
    def _setup_cmd(self, pav_cfg: config.PavConfig, args):
        """Similar to the 'config create' command, but with the expectation that this will
         be the primary pavilion config location."""

        # The provided Pavilion config is ignored - we're creating a new one.
        _ = pav_cfg

        path: Path = args.path.resolve()

        if args.group is not None:
            try:
                group = self.get_group(args.group)
            except ConfigCmdError as err:
                fprint(self.errfile, err)
                return 1
        else:
            group = None

        pav_cfg: config.PavConfig = config.PavilionConfigLoader().load_empty()
        pav_cfg.working_dir = args.working_dir
        pav_cfg.pav_cfg_file = path/'pavilion.yaml'

        try:
            self.create_config_dir(pav_cfg, path, 'main', group, working_dir=args.working_dir)
        except ConfigCmdError as err:
            fprint(self.errfile, err)

        return self.write_pav_cfg(pav_cfg)

    @staticmethod
    def get_group(group_name) -> Union[grp.struct_group, None]:
        """Check the supplied group and return a group struct object.

        :raises ValueError: On invalid groups names.
        """

        user = get_login()

        try:
            group = grp.getgrnam(group_name)
        except KeyError:
            raise ConfigCmdError("Group '{}' does not exist.".format(group_name))

        if user not in group.gr_mem:
            raise ConfigCmdError("Current user '{}' is not in group '{}'."
                                 .format(user, group_name))

        return group

    def create_config_dir(self, pav_cfg: config.PavConfig, path: Path,
                          label: str, group: Union[None, grp.struct_group],
                          working_dir: Path = None):
        """Create a standard Pavilion configuration directory at 'path',
        saving a config.yaml with the given label."""

        config_data = {
            'label': label,
        }

        if not path.parent.exists():
            raise ConfigCmdError("Parent directory '{}' does not exist.".format(path.parent))

        if label in pav_cfg.configs:
            raise ConfigCmdError("Given label '{}' already exists in the pav config."
                                 .format(label))

        # This should fail if it already exists.
        try:
            path.mkdir()
        except OSError as err:
            raise ConfigCmdError("Could not create specified directory", err)

        perms = 0o775
        if group is not None:
            # Mask out 'other' access.
            perms = perms & 0o770
            # Add the group sticky bit.
            perms = perms | stat.S_ISGID
            try:
                os.chown(path, -1, group.gr_gid)
            except OSError as err:
                shutil.rmtree(path)
                raise ConfigCmdError("Could not set config dir group to '{}'"
                                     .format(group.gr_name), err)

        try:
            path.chmod(perms)
        except OSError as err:
            shutil.rmtree(path)
            raise ConfigCmdError("Could not set permissions on config dir '{}'"
                                 .format(path), err)

        if working_dir is not None:
            config_data['working_dir'] = str(working_dir)

        if group is not None:
            config_data['group'] = group.gr_name

        config_file_path = path/'config.yaml'
        try:
            with (path/'config.yaml').open('w') as config_file:
                yaml.dump(config_data, config_file)
        except OSError as err:
            shutil.rmtree(path)
            raise ConfigCmdError("Error writing config file at '{}'"
                                 .format(config_file_path), err)

        for subdir in 'hosts', 'modes', 'tests', 'os', 'test_src', 'plugins', 'collections':
            subdir = path/subdir
            try:
                subdir.mkdir()
            except OSError as err:
                shutil.rmtree(path)
                raise ConfigCmdError("Could not make config subdir '{}'".format(subdir), err)

        # The working dir will be created automatically when Pavilion next runs.
        pav_cfg.config_dirs.append(path)
        return self.write_pav_cfg(pav_cfg)

    @sub_cmd()
    def _add_cmd(self, pav_cfg, args):

        path: Path = args.path
        path = path.resolve()

        if not path.exists():
            fprint(self.errfile, "Config path '{}' does not exist.".format(path))
            return 1

        pav_cfg['config_dirs'].append(path)

        return self.write_pav_cfg(pav_cfg)

    @staticmethod
    def write_pav_cfg(pav_cfg):
        """Add the given config path (which should already exist) to the pavilion.yaml file."""

        loader = config.PavilionConfigLoader()
        pav_cfg_file = pav_cfg.pav_cfg_file
        tmp_suffix = uuid.uuid4().hex[:10]
        pav_cfg_file_tmp = pav_cfg_file.with_suffix(pav_cfg_file.suffix + '.' + tmp_suffix)
        try:
            with pav_cfg_file_tmp.open('w') as tmp_file:
                loader.dump(tmp_file, values=pav_cfg)
            pav_cfg_file_tmp.rename(pav_cfg_file)
        except OSError as err:
            fprint(sys.stderr,
                   "Failed to write pav config file at '{}'".format(pav_cfg_file), err)
            if pav_cfg_file_tmp.exists():
                try:
                    pav_cfg_file_tmp.unlink()
                except OSError:
                    pass

            return 1

        return 0

    @sub_cmd('rm')
    def _remove_cmd(self, pav_cfg: config.PavConfig, args):
        """Remove the given config path from the pavilion config."""

        if args.config in pav_cfg.configs:
            path = pav_cfg.configs[args.config].path
        else:
            path: Path = Path(args.config).resolve()

        resolved_dirs = {}
        for config_dir in pav_cfg.config_dirs:
            resolved_dirs[config_dir.resolve()] = config_dir

        if path not in resolved_dirs:
            fprint(self.errfile,
                   "Couldn't remove config dir '{}'. It was not in the list of known "
                   "configuration directories.".format(args.config))
            fprint(self.errfile, "Known dirs:")
            for conf_dir in pav_cfg.config_dirs:
                fprint(self.errfile, '  {}'.format(conf_dir))
            return 1

        found_dir = resolved_dirs[path]
        pav_cfg.config_dirs.remove(found_dir)

        self.write_pav_cfg(pav_cfg)

    @sub_cmd('ls')
    def _list_cmd(self, pav_cfg: config.PavConfig, args):
        _ = args

        rows = []
        for label, cfg in pav_cfg.configs.items():
            cfg_data = {}
            cfg_data.update(cfg)
            cfg_data['label'] = label
            rows.append(cfg_data)

        draw_table(
            outfile=self.outfile,
            fields=['label', 'path', 'working_dir'],
            rows=rows,
        )
