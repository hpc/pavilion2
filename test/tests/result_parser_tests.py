from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import module_wrapper
from pavilion import plugins
from pavilion import result_parsers
from pavilion import system_variables
from pavilion.test_config import variables
from pavilion.unittest import PavTestCase
import logging
import subprocess

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

        regex = result_parsers.get_plugin('regex')

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
                        'file': ['../run.log'],
                        'regex': r'.* World',
                        'action': result_parsers.ACTION_TRUE,
                    },
                    {
                        # As before, but false. Also, with lists of data.
                        'key': 'false',
                        # By multiple globs.
                        'file': ['../run.log', 'other.*'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'action': result_parsers.ACTION_FALSE,
                    },
                    {
                        # As before, but keep match counts.
                        'key': 'count',
                        'file': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'action': result_parsers.ACTION_COUNT,
                        'per_file': result_parsers.PER_FULLNAME,
                    },
                    {
                        # Store matches by fullname
                        'key': 'fullname',
                        'file': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'per_file': result_parsers.PER_FULLNAME,
                    },
                    {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'key': 'name',
                        'file': ['other.*'],
                        'regex': r'.* World',
                        'per_file': result_parsers.PER_NAME,
                    },
                    {
                        'key': 'lists',
                        'file': ['other*'],
                        'regex': r'.* World',
                        'match_type': result_parsers.MATCH_ALL,
                        'per_file': result_parsers.PER_LIST,
                    },
                    {
                        'key': 'all',
                        'file': ['other*'],
                        'regex': r'.* World',
                        'action': result_parsers.ACTION_TRUE,
                        'per_file': result_parsers.PER_ALL
                    },
                    {
                        'key': 'result',
                        'file': ['other*'],
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

        import pprint
        pprint.pprint(results)

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

        self.assertEqual(results['name']['other']['name'], 'In a World')

        self.assertEqual(results['lists'],
                         ['and someone saves the World',
                          'In a World',
                          "I'm here to cause World"])

        self.assertEqual(results['all'], False)
        self.assertEqual(results['result'], result_parsers.PASS)

        plugins._reset_plugins()
