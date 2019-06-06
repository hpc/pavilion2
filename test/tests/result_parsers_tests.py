import logging
import os
import tempfile
import unittest

from pavilion import config
from pavilion import plugins
from pavilion import result_parsers

LOGGER = logging.getLogger(__name__)

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

    def test_regex_value_parser(self):
        """Ensure the regex-value parser works appropriately."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = config.PavilionConfigLoader().load_empty()

        plugins.initialize_plugins(pav_cfg)

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir')]

        output_loc = self.pav_cfg.working_dir + '/outfile.txt'

        parser = result_parsers.get_plugin('regex_value')

        # Testing the check_args functionality.
        # Test that it works when provided sensible values.
        valid_regex = '^User:(.*)$'
        parser.check_args(None, regex=valid_regex, results='all', expected=['12'])

        test_regex = '[[['

        exc = result_parsers.ResultParserError

        # Test assertion is raised upon receiving an invalid regex.
        self.assertRaises(exc, parser.check_args, None, regex=test_regex)

        # Test assertion is raised when an invalid range is provided.
        self.assertRaises(exc, parser.check_args, None, regex=valid_regex,
                          results='all', expected=['12-11'])

        self.assertRaises(exc, parser.check_args, None, regex=valid_regex,
                          results='all', expected=['-11--12'])

        self.assertRaises(exc, parser.check_args, None, regex=valid_regex,
                          results='all',  expected=['11-12-13'])

        self.assertRaises(exc, parser.check_args, None, regex=valid_regex,
                          results='all', expected=['11-words'])

        test_output = [
            "Test Name: FakeTest\n",
            "User: Some-gal-or-guy\n",
            "result1=19\n",
            "result3=test\n",
            "result9=-12\n",
            "result12=9.9\n",
            "result13=-22.2\n",
            "result98=\n",
            "result50=18.2,result51=18.3\n",
            "overall=whatevs"
        ]

        passing = result_parsers.PASS
        failing = result_parsers.FAIL

        with open(output_loc,'w') as outfile:
            outfile.writelines(test_output)

        self.assertRaises(exc, parser, None, file='notfile.txt',
                          regex=valid_regex)

        self.assertEqual(parser(None, file=output_loc, regex='^result1=(.*)$',
                                results='first', expected=['19']), passing)

        self.assertEqual(parser(None, file=output_loc, regex=valid_regex,
                                results='all'), ['User: Some-gal-or-guy'])

        self.assertEqual(parser(None, file=output_loc, regex='^result9=(.*)$',
                                results='all', expected=['-13--9']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result12=(.*)$',
                                results='all', expected=['9.0-9.9']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result12=(.*)$',
                                results='all', expected=['9.9-9.9']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result12=(.*)$',
                                results='all', expected=['9.9-10.0']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result12=(.*)$',
                                results='all', expected=['-9.9-10.0']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result13=(.*)$',
                                results='all', expected=['-32--22']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result13=(.*)$',
                                results='all', expected=['-32.0-22']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result13=(.*)$',
                                results='all',
                                expected=['-10000000000.0-0']), passing)

        self.assertEqual(parser(None, file=output_loc, regex='^result3=(.*)$',
                                results='last'), ['result3=test'])

        self.assertIsNone(parser(None, file=output_loc, regex='^result2=(.*)$',
                                 results='first'))

        self.assertIsNone(parser(None, file=output_loc, regex='^result2=(.*)$',
                                 results='last'))

        self.assertEqual(parser(None, file=output_loc, regex='^result2=(.*)$',
                                results='all'), [])

        self.assertEqual(parser(None, file=output_loc, regex='^result.*=(.*)$',
                                results='all', expected=['100','101']), failing)

        self.assertEqual(parser(None, file=output_loc,
                                regex='^result50=(.*),result51=(.*)$',
                                results='all', expected=['18.0-18.5']), passing)

        self.assertEqual(parser(None, file=output_loc,
                                regex='^result50=(.*),result51=(.*)$',
                                results='all', expected=['18.0-18.2']), failing)

        not_output = output_loc + ".false"

        self.assertRaises(exc, parser, None, file=not_output,
                          regex='^result1=(.*)$')

    def test_match_parser(self):
        """Ensure the match parser works appropriately."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = config.PavilionConfigLoader().load_empty()

        plugins.initialize_plugins(pav_cfg)

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir')]

        output_loc = self.pav_cfg.working_dir + '/outfile_match.txt'

        parser = result_parsers.get_plugin('match')

        test_output = [
            "Test Name: FakeTest\n",
            "User: Some-gal-or-guy\n",
            "result1=19\n",
            "result3=test\n",
            "result9=-12\n",
            "result12=9.9\n",
            "result13=-22.2\n",
            "result98=\n",
            "result50=18.2,result51=18.3\n",
            "overall=whatevs"
        ]

        passing = result_parsers.PASS
        failing = result_parsers.FAIL

        with open(output_loc,'w') as outfile:
            outfile.writelines(test_output)

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                results='pass'), 'pass')

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                results='fail'), 'fail')

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                results=passing), passing)

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                results=failing), failing)

        self.assertEqual(parser(None, file=output_loc, search='result2',
                                results=passing), failing)

        self.assertEqual(parser(None, file=output_loc, search='result2',
                                results=failing), passing)

        self.assertEqual(parser(None, file=output_loc, search='result2',
                                results='pass'), failing)

        self.assertEqual(parser(None, file=output_loc, search='result2',
                                results='fail'), passing)

    def test_match_count_parser(self):
        """Ensure the match_count parser works appropriately."""

        # Get an empty pavilion config and set some config dirs on it.
        pav_cfg = config.PavilionConfigLoader().load_empty()

        plugins.initialize_plugins(pav_cfg)

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir')]

        output_loc = self.pav_cfg.working_dir + '/outfile_match_count.txt'

        parser = result_parsers.get_plugin('match_count')

        test_output = [
            "Test Name: FakeTest\n",
            "User: Some-gal-or-guy\n",
            "result1=19\n",
            "result3=test\n",
            "result9=-12\n",
            "result12=9.9\n",
            "result13=-22.2\n",
            "result98=\n",
            "result50=18.2,result51=18.3\n",
            "overall=whatevs"
        ]

        passing = result_parsers.PASS
        failing = result_parsers.FAIL

        with open(output_loc,'w') as outfile:
            outfile.writelines(test_output)

        self.assertEqual(parser(None, file=output_loc, search='result',
                                threshold='7'), passing)

        self.assertEqual(parser(None, file=output_loc, search='result',
                                threshold='8'), passing)

        self.assertEqual(parser(None, file=output_loc, search='result',
                                threshold='9'), failing)

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                threshold='3'), passing)

        self.assertEqual(parser(None, file=output_loc, search='result1',
                                threshold='4'), failing)

        self.assertEqual(parser(None, file=output_loc, search='overall=whatevs',
                                threshold='0'), passing)

        self.assertEqual(parser(None, file=output_loc, search='overall=whatevs',
                                threshold='1'), passing)

        self.assertEqual(parser(None, file=output_loc, search='overall=whatevs',
                                threshold='2'), failing)

        with self.assertRaises(result_parsers.ResultParserError):
            tmp = parser.check_args(None, file=output_loc, search='res',
                                    threshold='-5')

        with self.assertRaises(result_parsers.ResultParserError):
            tmp = parser.check_args(None, file=output_loc, search='res',
                                    threshold='A')
