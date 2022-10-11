from __future__ import print_function

from pavilion.test_config import file_format
from pavilion.unittest import PavTestCase
from pavilion.config import PavilionConfigLoader
from pavilion import resolver
from pavilion import errors
import tempfile


class TestConfig(PavTestCase):
    def test_valid_test_config(self):
        """Check that a valid config is read correctly."""

        f = (self.TEST_DATA_ROOT/'config_tests.basics.yaml').open()

        data = file_format.TestConfigLoader().load(f)

        self.assertEqual(data.inherits_from, 'something_else')
        self.assertEqual(data.scheduler, 'slurm')
        self.assertEqual(data.run.cmds[0], 'true')

        variables = data['variables']
        self.assertEqual(len(variables), 4)
        self.assertEqual(variables['fish'], [{None: 'halibut'}])
        self.assertEqual(variables['animal'], [{None: 'squirrel'}])
        self.assertEqual(variables['bird'], [
            {None: 'eagle'},
            {None: 'mockingbird'},
            {None: 'woodpecker'}])
        self.assertEqual(variables['horse'][0]['legs'], '4')

    def test_pav_config_recycle(self):
        """Make sure a config template file is a valid config."""

        tmp_fn = tempfile.mktemp('yaml', dir='/tmp')

        cfg = PavilionConfigLoader().load_empty()
        with open(tmp_fn, 'w') as cfg_file:
            PavilionConfigLoader().dump(cfg_file, cfg)

        with open(tmp_fn) as cfg_file:
            reloaded = PavilionConfigLoader().load(cfg_file)

        self.assertEqual(cfg, reloaded)

    def test_default_vars(self):
        """Make sure variable defaults work as intended."""

        self.maxDiff = 1000
        rslvr = resolver.TestConfigResolver(self.pav_cfg)
        tests = rslvr.load(['default_vars_test'], host='default_vars_host')
        def_test = [test for test in tests if 'def' in test.config['name']][0]
        itest = [test for test in tests if 'inh' in test.config['name']][0]

        def_expected = {
            'str': ['hello_base'],
            'list': ['a_base', 'b_base'],
            'dict': [{'a': 'a_base', 'b': 'b_def'}],
            'ldict': [{'c': 'c_base1', 'd': 'd_base1'}, {'c': 'c_def', 'd': 'd_base2'}],
            'd_str': ['hello_def'],
            'd_list': ['a_def', 'b_def'],
            'd_dict': [{'a': 'a_def', 'b': 'b_def'}],
            'd_ldict': [{'c': 'c_def1', 'd': 'd_def1'}],
        }
        inh_expected = {
            'str': ['hello_inh'],
            'd_str': ['hello_def', 'hello_inh'],
            'list': ['a_inh'],
            'd_list': ['a_def', 'b_def', 'a_inh', 'b_inh'],
            'dict': [
                {'a': 'a_inh', 'b': 'b_def'},
                {'a': 'a_def', 'b': 'b_inh'}],
            'd_dict': [{'a': 'a_def', 'b': 'b_def'},
                       {'a': 'a_inh', 'b': 'b_def'},
                       {'a': 'a_def', 'b': 'b_inh'}],
            'd_ldict': [{'c': 'c_def1', 'd': 'd_def1'}],
            'ldict': [{'c': 'c_base1', 'd': 'd_base1'},
                      {'c': 'c_def', 'd': 'd_base2'}],
        }

        self.assertEqual(def_test.var_man.as_dict()['var'], def_expected)
        self.assertEqual(itest.var_man.as_dict()['var'], inh_expected)

        # Ensure that errors are thrown when loading tests with unset default vars.
        with self.assertRaises(errors.TestConfigError):
            tests = rslvr.load(['required_vars.req_base_var'])

        with self.assertRaises(errors.TestConfigError):
            rslvr.load(['required_vars.req_sub_var'])

