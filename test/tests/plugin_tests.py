import os
import unittest
import traceback

from pavilion import plugins
from pavilion import commands
from pavilion import module_wrapper
from pavilion import pav_config
from pavilion import arguments


class PluginTests(unittest.TestCase):

    TEST_DATA_ROOT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        'test_data',
    )

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()

    def test_plugin_loading(self):
        """Check to make sure the plugin system initializes correctly. Separate tests will check
        the internal initialization of each plugin sub-system."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir2')]

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
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir2')]

        plugins.initialize_plugins(pav_cfg)

        commands.get_command('poof').run(pav_cfg, [])
        commands.get_command('blarg').run(pav_cfg, [])

        # Clean up our plugin initializations.
        plugins._reset_plugins()

        pav_cfg.config_dirs.append(os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir_conflicts'))

        self.assertRaises(plugins.PluginError, lambda: plugins.initialize_plugins(pav_cfg))

        # Clean up our plugin initializations.
        plugins._reset_plugins()

    def test_module_wrappers(self):
        """Make sure module wrapper loading is sane too."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir'),
                               os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir2')]

        plugins.initialize_plugins(pav_cfg)

        module_wrapper.get_module_wrapper('foo', '1.0')
        bar1 = module_wrapper.get_module_wrapper('bar', '1.3')
        bar2 = module_wrapper.get_module_wrapper('bar', '1.2.0')
        self.assertIsNot(bar1, bar2)

        self.assertEqual('1.3', bar1.get_version('1.3'))
        self.assertEqual('1.2.0', bar2.get_version('1.2.0'))
        self.assertRaises(module_wrapper.ModuleWrapperError, lambda: bar2.get_version('1.3.0'))

        bar1.load({})

        plugins._reset_plugins()
