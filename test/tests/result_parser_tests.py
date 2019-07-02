import logging

import yaml_config as yc
from pavilion import arguments
from pavilion import plugins
from pavilion import result_parsers
from pavilion.unittest import PavTestCase

LOGGER = logging.getLogger(__name__)


class ResultParserTests(PavTestCase):

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()

    def test_parse_results(self):
        """Check all the different ways in which we handle parsed results."""

        plugins.initialize_plugins(self.pav_cfg)

        # We should have exactly one test plugin.
        self.assertEqual(len(result_parsers.list_plugins()), 1)

        test_cfg = {
            'scheduler': 'raw',
            'run': {
                # This will result in 4 output files.
                # run.log, other.log, other2.log, other3.log
                'cmds': [
                    'echo "Hello World."',
                    'echo "Goodbye Cruel World."',
                    'echo "In a World where..." >> other.log',
                    'echo "something happens..." >> other2.log',
                    'echo "and someone saves the World." >> other3.log',
                    'echo "I\'m here to cause Worldwide issues." >> other.txt'
                ]
            },
            'results': {
                'regex': [
                    {
                        # Look at the default output file. (run.log)
                        'key': 'basic',
                        'regex': r'.* World',
                    },
                    {
                        # Look all the log files, and save 'True' on match.
                        'key': 'true',
                        'files': ['../run.log'],
                        'regex': r'.* World',
                        'action': result_parsers.ACTION_TRUE,
                    },
                    {
                        # As before, but false. Also, with lists of data.
                        'key': 'false',
                        # By multiple globs.
                        'files': ['../run.log', 'other.*'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'action': result_parsers.ACTION_FALSE,
                    },
                    {
                        # As before, but keep match counts.
                        'key': 'count',
                        'files': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'action': result_parsers.ACTION_COUNT,
                        'per_file': result_parsers.PER_FULLNAME,
                    },
                    {
                        # Store matches by fullname
                        'key': 'fullname',
                        'files': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'per_file': result_parsers.PER_FULLNAME,
                    },
                    {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'key': 'name',
                        'files': ['other.*'],
                        'regex': r'.* World',
                        'per_file': result_parsers.PER_NAME,
                    },
                    {
                        'key': 'lists',
                        'files': ['other*'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'per_file': result_parsers.PER_LIST,
                    },
                    {
                        'key': 'all',
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': result_parsers.ACTION_TRUE,
                        'per_file': result_parsers.PER_ALL
                    },
                    {
                        'key': 'result',
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': result_parsers.ACTION_TRUE,
                        'per_file': result_parsers.PER_ANY
                    },
                ]
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.build()
        test.run({}, {})

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        # Check all the different results to make sure they're what we expect.
        self.assertEqual(
            results['basic'],
            'Hello World')

        self.assertEqual(
            results['true'],
            True,
        )

        self.assertEqual(
            results['false'],
            False,
        )

        self.assertEqual(results['fullname']['run.log']['count'], 2)
        self.assertEqual(results['fullname']['other.log']['count'], 1)

        self.assertEqual(results['fullname']['other.log']['fullname'],
                         'In a World')

        self.assertIn(results['name']['other']['name'], 
                      ['In a World', "I'm here to cause World"])
        self.assertIn("Duplicate file key 'other' matched by name",
                      [e['msg'] for e in results['errors']])

        self.assertEqual(sorted(results['lists']),
                         sorted(['and someone saves the World',
                                 'In a World',
                                 "I'm here to cause World"]))

        self.assertEqual(results['all'], False)
        self.assertEqual(results['result'], result_parsers.PASS)

        plugins._reset_plugins()

    def test_check_args(self):
        plugins.initialize_plugins(self.pav_cfg)

        # We should have exactly one test plugin.
        self.assertEqual(len(result_parsers.list_plugins()), 1)

        # Make sure we can check arguments.
        test_cfg = {
            'results': {
                'regex': [
                    {'key': 'ok', 'regex': r'foo'},
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        result_parsers.check_args(test.config['results'])

        # Make sure duplicate keys aren't allowed.
        test_cfg = {
            'results': {
                'regex': [
                    {'key': 'repeated', 'regex': r'foo'},
                    {'key': 'repeated', 'regex': r'foo'},
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        # Make sure we handle bad key names.
        test_cfg = {
            'results': {
                'regex': [
                    {'key': '#!@123948aa', 'regex': r'foo'},
                ]
            }
        }
        with self.assertRaises(ValueError):
            self._quick_test(test_cfg, 'check_args_test')

        # Make sure we handle missing the 'key' attribute as expected.
        test_cfg = {
            'results': {
                'regex': [
                    {'regex': r'foo'},
                ]
            }
        }
        with self.assertRaises(ValueError):
            self._quick_test(test_cfg, 'check_args_test')

        # Make sure reserved keys aren't allowed.
        test_cfg = {
            'results': {
                'regex': [
                    {'key': 'started', 'regex': r'foo'},
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        # Missing a key for the parser plugin
        test_cfg = {
            'results': {
                'regex': [
                    {'key': 'nope'},
                ]
            }
        }
        with self.assertRaises(yc.RequiredError):
            self._quick_test(test_cfg, 'check_args_test')

        plugins._reset_plugins()

    def test_regex_value_parser(self):
        """Ensure the regex-value parser works appropriately."""

        # Get an empty pavilion config and set some config dirs on it.
        # pav_cfg = config.PavilionConfigLoader().load_empty()

        plugins.initialize_plugins(self.pav_cfg)

        # We're loading multiple directories of plugins - AT THE SAME TIME!
        pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                            'pav_config_dir')]

        output_loc = self.pav_cfg.working_dir + '/outfile.txt'

        parser = result_parsers.get_plugin('regex')

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
