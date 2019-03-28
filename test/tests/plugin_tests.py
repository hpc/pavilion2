import logging
import os
import subprocess
import unittest
import traceback

from pavilion import plugins
from pavilion import commands
from pavilion import module_wrapper
from pavilion import pav_config
from pavilion import system_plugins
from pavilion import scheduler_plugins
from pavilion import arguments
from pavilion import variables


LOGGER = logging.getLogger(__name__)


class PluginTests(unittest.TestCase):

    TEST_DATA_ROOT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        'test_data',
    )

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()

    def test_plugin_loading(self):
        """Check to make sure the plugin system initializes correctly. Separate
        tests will check the internal initialization of each plugin
        sub-system."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir2')]

        for path in pav_cfg.config_dirs:
            self.assertTrue(os.path.exists(path))

        plugins.initialize_plugins(pav_cfg)

        created_manager = plugins._PLUGIN_MANAGER

        # Make sure this can run multiple times,
        plugins.initialize_plugins(pav_cfg)

        # Make sure only one of these is ever created.
        self.assertIs(created_manager, plugins._PLUGIN_MANAGER)

        # Clean up our plugin initializations.
        plugins._reset_plugins()

    def test_command_plugins(self):
        """Make sure command plugin loading is sane."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir2')]

        plugins.initialize_plugins(pav_cfg)

        commands.get_command('poof').run(pav_cfg, [])
        commands.get_command('blarg').run(pav_cfg, [])

        # Clean up our plugin initializations.
        plugins._reset_plugins()

        pav_cfg.config_dirs.append(os.path.join(self.TEST_DATA_ROOT,
                                                'pav_config_dir_conflicts'))

        self.assertRaises(plugins.PluginError,
                          lambda: plugins.initialize_plugins(pav_cfg))

        # Clean up our plugin initializations.
        plugins._reset_plugins()

    def test_module_wrappers(self):
        """Make sure module wrapper loading is sane too."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir2')]

        plugins.initialize_plugins(pav_cfg)

        module_wrapper.get_module_wrapper('foo', '1.0')
        bar1 = module_wrapper.get_module_wrapper('bar', '1.3')
        bar2 = module_wrapper.get_module_wrapper('bar', '1.2.0')
        self.assertIsNot(bar1, bar2)

        self.assertEqual('1.3', bar1.get_version('1.3'))
        self.assertEqual('1.2.0', bar2.get_version('1.2.0'))
        self.assertRaises(module_wrapper.ModuleWrapperError,
                          lambda: bar2.get_version('1.3.0'))

        bar1.load({})

        plugins._reset_plugins()

    def test_system_plugins(self):
        """Make sure system values appear as expected.  Also that deferred
        variables behave as expected."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        plugins.initialize_plugins(pav_cfg)

        self.assertFalse(system_plugins._LOADED_PLUGINS is None)

        host_arch = subprocess.check_output(['uname', '-i'])
        host_arch = host_arch.strip().decode('UTF-8')

        host_name = subprocess.check_output(['hostname', '-s'])
        host_name = host_name.strip().decode('UTF-8')

        with open('/etc/os-release', 'r') as release:
            rlines = release.readlines()

        host_os = {}
        for line in rlines:
            if line[:3] == 'ID=':
                host_os['ID'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                host_os['Version'] = line[11:].strip().strip('"')

        sys_vars = system_plugins.get_system_plugin_dict(defer=False)

        self.assertFalse('sys_arch' in sys_vars)
        self.assertEqual(host_arch, sys_vars['sys_arch'])
        self.assertTrue('sys_arch' in sys_vars)

        self.assertFalse('sys_name' in sys_vars)
        self.assertEqual(host_name, sys_vars['sys_name'])
        self.assertTrue('sys_name' in sys_vars)

        self.assertFalse('sys_os' in sys_vars)
        self.assertEqual(host_os['ID'], sys_vars['sys_os']['ID'])
        self.assertEqual(host_os['Version'],
                         sys_vars['sys_os']['Version'])
        self.assertTrue('sys_os' in sys_vars)

        self.assertFalse('host_arch' in sys_vars)
        self.assertEqual(host_arch, sys_vars['host_arch'])
        self.assertTrue('host_arch' in sys_vars)

        self.assertFalse('host_name' in sys_vars)
        self.assertEqual(host_name, sys_vars['host_name'])
        self.assertTrue('host_name' in sys_vars)

        self.assertFalse('host_os' in sys_vars)
        self.assertEqual(host_os['ID'], sys_vars['host_os']['ID'])
        self.assertEqual(host_os['Version'],
                         sys_vars['host_os']['Version'])
        self.assertTrue('host_os' in sys_vars)

        # Re-initialize the plugin system.
        plugins._reset_plugins()
        # Make sure these have been wiped
        self.assertIsNone(system_plugins._LOADED_PLUGINS)
        # Make sure these have been wiped.
        self.assertIsNone(system_plugins._SYS_VAR_DICT)

        plugins.initialize_plugins(pav_cfg)

        # but these are back
        self.assertIsNotNone(system_plugins._LOADED_PLUGINS)

        sys_vars = system_plugins.get_system_plugin_dict(defer=True)

        self.assertTrue(len(system_plugins._SYS_VAR_DICT.items()) == 0)

        # Check that the deferred values are actually deferred.
        self.assertFalse('host_arch' in sys_vars)
        self.assertTrue(isinstance(sys_vars['host_arch'],
                                   variables.DeferredVariable))
        self.assertFalse('host_name' in sys_vars)
        self.assertTrue(isinstance(sys_vars['host_name'],
                                   variables.DeferredVariable))
        self.assertFalse('host_os' in sys_vars)
        self.assertTrue(isinstance(sys_vars['host_os'],
                                   variables.DeferredVariable))

        plugins._reset_plugins()
