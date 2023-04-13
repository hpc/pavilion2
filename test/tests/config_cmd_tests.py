"""These make sure python's built in config creation and editing commands work as expected."""
import grp
import stat

from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import unittest
from pavilion.utils import get_login


class ConfigCmdTests(unittest.PavTestCase):

    def test_config_cmds(self):

        test_config_root = self.pav_cfg.working_dir/'config_cmds_config'
        test_config_wd = self.pav_cfg.working_dir/'config_cmds_working_dir'
        test_pav_config_path = test_config_root/'pavilion.yaml'

        arg_parser = arguments.get_parser()

        config_cmd = commands.get_command('config')
        config_cmd.silence()

        # Find a group other than the user's default group to set group properties to.
        # This may fail, in which case we won't test this.
        user = get_login()
        groups = [group for group in grp.getgrall() if user in group.gr_mem]
        other_group = None
        for group in groups:
            if group.gr_name == user:
                continue
            else:
                other_group = group.gr_name

        # Check that the setup command creates a reasonable pav_cfg and the expected directories.
        base_args = ['config', 'setup']
        if other_group is not None:
            base_args.extend(['--group', other_group])

        args = arg_parser.parse_args(
            base_args + [test_config_root.as_posix(), test_config_wd.as_posix()])
        config_cmd.run(self.pav_cfg, args)

        # Reload our saved pav config.
        pav_cfg = config.find_pavilion_config(test_pav_config_path)
        msg = config_cmd.clear_output()
        self.assertEqual(pav_cfg.config_dirs, [test_config_root], msg=msg)
        self.assertTrue('main' in pav_cfg.configs)
        self.assertEqual(pav_cfg.working_dir, test_config_wd)
        # Make sure all created files exist.
        for subfile in ['config.yaml', 'test_src', 'tests', 'hosts', 'modes', 'plugins',
                        'pavilion.yaml', 'sys_os']:
            self.assertTrue((test_config_root / subfile).exists())
        # Make sure groups are sane.
        if other_group is not None:
            for path in (test_config_root, test_config_root/'tests', test_pav_config_path,
                         pav_cfg.working_dir):
                self.assertEqual(path.group(), other_group,
                                 msg="Path '{}' should have group '{}', but had group '{}'"
                                     .format(path, other_group, path.group()))
                if path.is_dir():
                    self.assertTrue(path.stat().st_mode | stat.S_ISGID,
                                    msg="Path '{}' does not have group sticky bit set."
                                        .format(path))

        pav_cfg = config.find_pavilion_config(target=test_pav_config_path)

        # Check that we can create additional config directories.
        foo_config_dir = test_config_root/'foo'
        args = arg_parser.parse_args(['config', 'create', 'foo', foo_config_dir.as_posix()])
        self.assertEqual(config_cmd.run(pav_cfg, args), 0)
        for subfile in ['config.yaml', 'test_src', 'tests', 'hosts', 'modes', 'plugins',
                        'sys_os']:
            self.assertTrue((foo_config_dir/subfile).exists())

        # Load and delete from the pavilion.yaml we created.
        pav_cfg = config.find_pavilion_config(target=test_config_root/'pavilion.yaml')
        args = arg_parser.parse_args(['config', 'remove', 'foo'])
        self.assertEqual(config_cmd.run(pav_cfg, args), 0)

        pav_cfg = config.find_pavilion_config(target=test_config_root/'pavilion.yaml')
        self.assertNotIn('foo', pav_cfg.configs)
        self.assertNotIn(foo_config_dir, pav_cfg.config_dirs)

        # Re-add the removed 'foo' config dir
        pav_cfg = config.find_pavilion_config(target=test_config_root/'pavilion.yaml')
        args = arg_parser.parse_args(['config', 'add', foo_config_dir.as_posix()])
        self.assertEqual(config_cmd.run(pav_cfg, args), 0)

        pav_cfg = config.find_pavilion_config(target=test_config_root/'pavilion.yaml')
        self.assertIn('foo', pav_cfg.configs)
        self.assertIn(foo_config_dir, pav_cfg.config_dirs)

        config_cmd.clear_output()
        args = arg_parser.parse_args(['config', 'list'])
        self.assertEqual(config_cmd.run(pav_cfg, args), 0)
