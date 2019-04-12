import os
import tempfile
import unittest

from pavilion import result_parsers
from pavilion import config
from pavilion.test_config import PavTest

class PavTestTests(unittest.TestCase):

    TEST_DATA_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    TEST_DATA_ROOT = os.path.join(TEST_DATA_ROOT, 'test_data')

    PAV_CONFIG_PATH = os.path.join(TEST_DATA_ROOT, 'pav_config_dir', 'pavilion.yaml')

    def __init__(self, *args, **kwargs):

        with open(self.PAV_CONFIG_PATH) as cfg_file:
            self.pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        self.pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir')]

        self.tmp_dir = tempfile.TemporaryDirectory()

        self.pav_cfg.working_dir = '/tmp/pav_test' # self.tmp_dir.name

        # Create the basic directories in the working directory
        for path in [self.pav_cfg.working_dir,
                     os.path.join(self.pav_cfg.working_dir, 'builds'),
                     os.path.join(self.pav_cfg.working_dir, 'tests'),
                     os.path.join(self.pav_cfg.working_dir, 'downloads')]:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

        super().__init__(*args, **kwargs)

    def test_obj(self):
        """Test pavtest object initialization."""

        # Initializing with a mostly blank config
        config = {
            'name': 'blank_test'
        }

        PavTest(self.pav_cfg, config)

        config = {
            'subtest': 'st',
            'name': 'test',
            'build': {
                'modules': ['gcc'],
                'cmds': ['echo "Hello World"'],
            },
            'run': {
                'modules': ['gcc', 'openmpi'],
                'cmds': ['echo "Running dis stuff"'],
                'env': {'BLARG': 'foo'},
            }
        }

        # Make sure we can create a test from a fairly populated config.
        t = PavTest(self.pav_cfg, config)

        # Make sure we can recreate the object from id.
        t2 = PavTest.from_id(self.pav_cfg, t.id)

        # Make sure the objects are identical
        # This tests the following functions
        #  - from_id
        #  - save_config, load_config
        #  - get_test_path
        #  - write_tmpl
        for key in set(t.__dict__.keys()).union(t2.__dict__.keys()):
            self.assertEqual(t.__dict__[key], t2.__dict__[key])

    def test_regex_value_parser(self):
        """Ensure the regex-value parser works appropriately."""

        output_loc = self.pav_cfg.working_dir + '/outfile.txt'

        parser = result_parsers.get_plugin('regex-value')

        # Testing the check_args functionality.

        # Test that it works when provided sensible values.
        valid_regex = '^User:(.*)$'
        parser.check_args(regex=valid_regex, results='all', expected=['12'])

        test_regex = '[[['

        # Test assertion is raised upon receiving an invalid regex.
        self.assertRaises(parser.check_args(regex=test_regex))

        # Test assertion is raised when an invalid range is provided.
        self.assertRaises(parser.check_args(regex=valid_regex, results='all',
                                            expected=['12-11']))

        self.assertRaises(parser.check_args(regex=valid_regex, results='all',
                                            expected=['-11--12']))

        self.assertRaises(parser.check_args(regex=valid_regex, results='all',
                                            expected=['11-12-13']))

        self.assertRaises(parser.check_args(regex=valid_regex, results='all',
                                            expected=['11-words']))

        test_output = [
            "Test Name: FakeTest",
            "User: Some-gal-or-guy",
            "result1=19",
            "result3=test",
            "result9=-12",
            "result98=",
            "overall=whatevs"
        ]

        with open(output_loc,'w') as outfile:
            outfile.writelines(test_output)

        self.assertEqual(parser(file=output_loc, regex=valid_regex,
                                results='all'), 'Some-gal-or-guy')

        self.assertEqual(parser(file=output_loc, regex='^result1=(.*)$',
                                results='first', expected=['19']), 'PASS')

        self.assertEqual(parser(file=output_loc, regex='^result9=(.*)$',
                                results='all', expected=['-13--9']), 'PASS')

        self.assertEqual(parser(file=output_loc, regex='^result3=(.*)$',
                                results='last'), 'test')

        self.assertIsNone(parser(file=output_loc, regex='^result2=(.*)$',
                                 results='first'))

        self.assertIsNone(parser(file=output_loc, regex='^result2=(.*)$',
                                 results='last'))

        self.assertEqual(parser(file=output_loc, regex='^result2=(.*)$',
                                results='all'), [])

        self.assertEqual(parser(file=output_loc, regex='^result?=(.*)$',
                                results='all', expected=['100','101']), 'FAIL')

        not_output = output_loc + ".false"

        self.assertRaises(parser(file=not_output, regex='^result1=(.*)$'))
