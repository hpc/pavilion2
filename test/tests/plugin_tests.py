"""Test plugin system functionality."""

import argparse
import io
import logging
import subprocess
import sys

import pavilion.deferred
from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import expression_functions
from pavilion import module_wrapper
from pavilion import output
from pavilion import plugins
from pavilion import result_parsers
from pavilion import sys_vars
from pavilion.resolver import variables
from pavilion.unittest import PavTestCase

LOGGER = logging.getLogger(__name__)


class PluginTests(PavTestCase):

    def set_up(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()

    def tear_down(self):
        pass

    def test_plugin_loading(self):
        """Check to make sure the plugin system initializes correctly. Separate
        tests will check the internal initialization of each plugin
        sub-system."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [self.TEST_DATA_ROOT/'pav_config_dir',
                               self.TEST_DATA_ROOT/'pav_config_dir2']

        for path in pav_cfg.config_dirs:
            self.assertTrue(path.exists())

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
        pav_cfg = self.make_pav_config(config_dirs=[
            self.TEST_DATA_ROOT/'pav_config_dir',
            self.TEST_DATA_ROOT/'pav_config_dir2'])

        plugins.initialize_plugins(pav_cfg)

        parser = argparse.ArgumentParser()
        args = parser.parse_args([])

        commands.get_command('poof').run(pav_cfg, args)
        commands.get_command('blarg').run(pav_cfg, args)

        plugins._reset_plugins()

    def test_plugin_conflicts(self):

        pav_cfg = self.make_pav_config(config_dirs=[
            self.TEST_DATA_ROOT/'pav_config_dir',
            self.TEST_DATA_ROOT/'pav_config_dir2',
            self.TEST_DATA_ROOT / 'pav_config_dir_conflicts'])

        self.assertRaises(plugins.PluginError,
                          lambda: plugins.initialize_plugins(pav_cfg))

        # Clean up our plugin initializations.
        plugins._reset_plugins()

    def test_function_plugins(self):
        """Make sure each of the core function plugins work."""

        plugins.initialize_plugins(self.pav_cfg)

        tests = {
            'int': ('0x123', 16),
            'floor': (1.2,),
            'ceil': (1.3,),
            'round': (1.4,),
            'sum': ([1, 2, 3, 2.4],),
            'avg': ([1, 2, 3, 2.4],),
            'len': ([1, 2, 3, 2.4],),
            'random': tuple(),
        }

        for func_name, args in tests.items():
            func = expression_functions.get_plugin(func_name)
            # Make sure this doesn't throw errors
            func(*args)

        # Make sure we have a test for all core plugins.
        for plugin in plugins.list_plugins()['function']:
            if plugin.priority == expression_functions.FunctionPlugin.PRIO_CORE:
                self.assertIn(plugin.name, tests)

        plugins._reset_plugins()

    def test_module_wrappers(self):
        """Make sure module wrapper loading is sane too."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = self.make_pav_config(config_dirs=[
            self.TEST_DATA_ROOT/'pav_config_dir',
            self.TEST_DATA_ROOT/'pav_config_dir2'])

        # We're loading multiple directories of plugins - AT THE SAME TIME!

        plugins.initialize_plugins(pav_cfg)

        module_wrapper.get_module_wrapper('foo', '1.0')
        bar1 = module_wrapper.get_module_wrapper('bar', '1.3')
        bar2 = module_wrapper.get_module_wrapper('bar', '1.2.0')
        self.assertIsNot(bar1, bar2)

        self.assertEqual('1.3', bar1.get_version('1.3'))
        self.assertEqual('1.2.0', bar2.get_version('1.2.0'))
        self.assertRaises(module_wrapper.ModuleWrapperError,
                          lambda: bar2.get_version('1.3.0'))

        vsm = variables.VariableSetManager()
        bar1.load(vsm)

        plugins._reset_plugins()

    def test_system_plugins(self):
        """Make sure system values appear as expected.  Also that deferred
        variables behave as expected."""

        # Get an empty pavilion config and set some config dirs on it.
        plugins.initialize_plugins(self.pav_cfg)

        host_arch = subprocess.check_output(['uname', '-i'])
        host_arch = host_arch.strip().decode('UTF-8')

        host_name = subprocess.check_output(['hostname', '-s'])
        host_name = host_name.strip().decode('UTF-8')

        with open('/etc/os-release', 'r') as release:
            rlines = release.readlines()

        host_os = {}
        for line in rlines:
            if line[:3] == 'ID=':
                host_os['name'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                host_os['version'] = line[11:].strip().strip('"')

        svars = sys_vars.get_vars(defer=False)

        self.assertFalse('sys_arch' in svars)
        self.assertEqual(host_arch, svars['sys_arch'])
        self.assertTrue('sys_arch' in svars)

        self.assertFalse('sys_host' in svars)
        self.assertEqual(host_name, svars['sys_host'])
        self.assertTrue('sys_host' in svars)

        self.assertFalse('sys_os' in svars)
        self.assertEqual(host_os['name'], svars['sys_os']['name'])
        self.assertEqual(host_os['version'],
                         svars['sys_os']['version'])
        self.assertTrue('sys_os' in svars)

        self.assertFalse('host_arch' in svars)
        self.assertEqual(host_arch, svars['host_arch'])
        self.assertTrue('host_arch' in svars)

        self.assertFalse('host_name' in svars)
        self.assertEqual(host_name, svars['host_name'])
        self.assertTrue('host_name' in svars)

        self.assertFalse('host_os' in svars)
        self.assertEqual(host_os['name'], svars['host_os']['name'])
        self.assertEqual(host_os['version'],
                         svars['host_os']['version'])
        self.assertTrue('host_os' in svars)

        # Re-initialize the plugin system.
        plugins._reset_plugins()
        # Make sure these have been wiped
        self.assertIsNone(sys_vars.base_classes._LOADED_PLUGINS)
        # Make sure these have been wiped.
        self.assertIsNone(sys_vars.base_classes._SYS_VAR_DICT)

        plugins.initialize_plugins(self.pav_cfg)

        # but these are back
        self.assertIsNotNone(sys_vars.base_classes._LOADED_PLUGINS)

        svars = sys_vars.get_vars(defer=True)

        # Check that the deferred values are actually deferred.
        self.assertFalse('host_arch' in svars)
        self.assertTrue(isinstance(svars['host_arch'],
                                   pavilion.deferred.DeferredVariable))
        self.assertFalse('host_name' in svars)
        self.assertTrue(isinstance(svars['host_name'],
                                   pavilion.deferred.DeferredVariable))
        self.assertFalse('host_os' in svars)
        self.assertTrue(isinstance(svars['host_os'],
                                   pavilion.deferred.DeferredVariable))

        plugins._reset_plugins()

    def test_result_parser_plugins(self):
        """Check basic result parser structure."""

        plugins.initialize_plugins(self.pav_cfg)

        _ = result_parsers.get_plugin('regex')

        plugins._reset_plugins()

    def test_bad_plugins(self):
        """Make sure bad plugins don't kill Pavilion and print appropriate
        errors."""

        error_strs = [
            'Plugin candidate rejected:',
            'Unable to create plugin object:',
            'Unable to import plugin:',
        ]

        yapsy_logger = logging.getLogger('yapsy')
        stream = io.StringIO()
        hndlr = logging.StreamHandler(stream)
        yapsy_logger.addHandler(hndlr)

        pav_cfg = self.make_pav_config(config_dirs=[
            self.TEST_DATA_ROOT/'bad_plugins',
        ])

        # A bunch of plugins should fail to load, but this should be fine
        # anyway.
        output.fprint(sys.stdout, "The following error message is expected; We're testing "
                                  "that such errors are caught and printed rather than "
                                  "crashing pavilion.", color=output.BLUE)
        plugins.initialize_plugins(pav_cfg)

        yapsy_logger.removeHandler(hndlr)

        stream.seek(0)
        logs = stream.read()
        for error_str in error_strs:
            self.assertIn(error_str, logs)

        plugins._reset_plugins()
