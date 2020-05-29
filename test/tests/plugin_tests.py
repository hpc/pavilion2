from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import module_wrapper
from pavilion import plugins
from pavilion.result import parsers
from pavilion import system_variables
from pavilion import expression_functions
from pavilion.test_config import variables
from pavilion.unittest import PavTestCase
import io
import logging
import subprocess

LOGGER = logging.getLogger(__name__)


class PluginTests(PavTestCase):

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()

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
        pav_cfg = config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [self.TEST_DATA_ROOT/'pav_config_dir',
                               self.TEST_DATA_ROOT/'pav_config_dir2']

        plugins.initialize_plugins(pav_cfg)

        commands.get_command('poof').run(pav_cfg, [])
        commands.get_command('blarg').run(pav_cfg, [])

        # Clean up our plugin initializations.
        plugins._reset_plugins()

        pav_cfg.config_dirs.append(
            self.TEST_DATA_ROOT/'pav_config_dir_conflicts')

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
        pav_cfg = config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [self.TEST_DATA_ROOT/'pav_config_dir',
                               self.TEST_DATA_ROOT/'pav_config_dir2']

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
        plugins.initialize_plugins(self.pav_cfg)

        self.assertFalse(system_variables._LOADED_PLUGINS is None)

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

        sys_vars = system_variables.get_vars(defer=False)

        self.assertFalse('sys_arch' in sys_vars)
        self.assertEqual(host_arch, sys_vars['sys_arch'])
        self.assertTrue('sys_arch' in sys_vars)

        self.assertFalse('sys_host' in sys_vars)
        self.assertEqual(host_name, sys_vars['sys_host'])
        self.assertTrue('sys_host' in sys_vars)

        self.assertFalse('sys_os' in sys_vars)
        self.assertEqual(host_os['name'], sys_vars['sys_os']['name'])
        self.assertEqual(host_os['version'],
                         sys_vars['sys_os']['version'])
        self.assertTrue('sys_os' in sys_vars)

        self.assertFalse('host_arch' in sys_vars)
        self.assertEqual(host_arch, sys_vars['host_arch'])
        self.assertTrue('host_arch' in sys_vars)

        self.assertFalse('host_name' in sys_vars)
        self.assertEqual(host_name, sys_vars['host_name'])
        self.assertTrue('host_name' in sys_vars)

        self.assertFalse('host_os' in sys_vars)
        self.assertEqual(host_os['name'], sys_vars['host_os']['name'])
        self.assertEqual(host_os['version'],
                         sys_vars['host_os']['version'])
        self.assertTrue('host_os' in sys_vars)

        # Re-initialize the plugin system.
        plugins._reset_plugins()
        # Make sure these have been wiped
        self.assertIsNone(system_variables._LOADED_PLUGINS)
        # Make sure these have been wiped.
        self.assertIsNone(system_variables._SYS_VAR_DICT)

        plugins.initialize_plugins(self.pav_cfg)

        # but these are back
        self.assertIsNotNone(system_variables._LOADED_PLUGINS)

        sys_vars = system_variables.get_vars(defer=True)

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

    def test_result_parser_plugins(self):
        """Check basic result parser structure."""

        plugins.initialize_plugins(self.pav_cfg)

        regex = parsers.get_plugin('regex')

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

        pav_cfg = self.pav_cfg.copy()
        cfg_dirs = list(pav_cfg.config_dirs)
        cfg_dirs.append(self.TEST_DATA_ROOT/'bad_plugins')
        pav_cfg.config_dirs = cfg_dirs

        # A bunch of plugins should fail to load, but this should be fine
        # anyway.
        plugins.initialize_plugins(pav_cfg)

        yapsy_logger.removeHandler(hndlr)

        stream.seek(0)
        logs = stream.read()
        for error_str in error_strs:
            self.assertIn(error_str, logs)

        plugins._reset_plugins()
