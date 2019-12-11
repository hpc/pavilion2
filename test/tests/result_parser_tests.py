import logging
import os

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
        test.run()

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

        test_cfg = {
            'results': {
                'regex': [
                    {'key': 'test', 'regex': '[[['},
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': '^User:(.*)$',
                        'expected': ['12:11']
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': '^User:(.*)$',
                        'expected': ['-11:-12']
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': '^User:(.*)$',
                        'expected': ['11:12:13']
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': '^User:(.*)$',
                        'expected': ['11:words']
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': 'res',
                        'threshold': '-5',
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': 'res',
                        'threshold': 'A',
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        test_cfg = {
            'results': {
                'regex': [
                    {
                        'key': 'test',
                        'regex': 'res',
                        'threshold': 'A',
                        'expected': '10:12',
                    },
                ]
            }
        }
        test = self._quick_test(test_cfg, 'check_args_test')
        with self.assertRaises(result_parsers.ResultParserError):
            result_parsers.check_args(test.config['results'])

        plugins._reset_plugins()

    def test_regex_expected(self):
        """Ensure the regex-value parser works appropriately."""

        plugins.initialize_plugins(self.pav_cfg)

        test_cfg = {
            'scheduler': 'raw',
            'run': {
                # This will result in 4 output files.
                # run.log, other.log, other2.log, other3.log
                'cmds': [
                    'echo "Test Name: FakeTest\n"',
                    'echo "User: Some-gal-or-guy\n"',
                    'echo "result1=19\n"',
                    'echo "result3=test\n"',
                    'echo "result9=-12\n"',
                    'echo "result12=9.9\n"',
                    'echo "result13=-22.2\n"',
                    'echo "result98=\n"',
                    'echo "result50=18.2,result51=18.3\n"',
                    'echo "overall=whatevs"'
                ]
            },
            'results': {
                'regex': [
                    {
                        # Look at the default output file. (run.log)
                        # Test for storing the whole line
                        'key': 'key0',
                        'regex': r'^User:.*$',
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for storing a single value
                        'key': 'key1',
                        'regex': r'^result1=(.*)$',
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of negative integers
                        'key': 'key2',
                        'regex': r'^result9=(.*)$',
                        'expected': ['-13:-9'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of floats where the value
                        # is equal to the bottom of the range
                        'key': 'key3',
                        'regex': r'^result12=(.*)$',
                        'expected': ['9.0:9.9'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of floats that has zero
                        # span
                        'key': 'key4',
                        'regex': r'^result12=(.*)$',
                        'expected': ['9.9:9.9'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of floats where the value
                        # is equal to the top of the range
                        'key': 'key5',
                        'regex': r'^result12=(.*)$',
                        'expected': ['9.9:10.0'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of floats from negative to
                        # positive
                        'key': 'key6',
                        'regex': r'^result12=(.*)$',
                        'expected': ['-9.9:10.0'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range of negative integers
                        'key': 'key7',
                        'regex': r'^result13=(.*)$',
                        'expected': ['-32:-22'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range from a negative float to a
                        # positive integer
                        'key': 'key8',
                        'regex': r'^result13=(.*)$',
                        'expected': ['-32.0:22'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for expecting a range from a very large negative
                        # float to zero
                        'key': 'key9',
                        'regex': r'^result13=(.*)$',
                        'expected': ['-10000000000.0:0'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for checking a set of results that are NOT in a
                        # list of integer values
                        'key': 'key10',
                        'regex': r'^result.*=(.*)$',
                        'expected': ['100', '101'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results in a range of floats
                        'key': 'key11',
                        'regex': r'result5.=([0-9.]*)',
                        'expected': ['18.0:18.5'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results where one value is inside
                        # the expected range and the other is not
                        'key': 'key12',
                        'regex': r'^result50=(.*),result51=(.*)$',
                        'expected': ['18.0:18.2'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results in a one-side bounded
                        # range of floats
                        'key': 'key13',
                        'regex': r'result5.=([0-9.]*)',
                        'expected': [':18.5'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results in a one-side bounded
                        # range of floats
                        'key': 'key14',
                        'regex': r'result5.=([0-9.]*)',
                        'expected': ['18.0:'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results where one value is inside
                        # the expected range and the other is not
                        'key': 'key15',
                        'regex': r'^result50=(.*),result51=(.*)$',
                        'expected': [':18.2'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # Test for a list of results where one value is inside
                        # the expected range and the other is not
                        'key': 'key16',
                        'regex': r'^result50=(.*),result51=(.*)$',
                        'expected': ['18.0:'],
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                    },
                    {
                        # A test using the 'result' key is required.
                        'key': 'result',
                        'regex': r'^overall=(.*)$',
                        'action': result_parsers.ACTION_TRUE,
                    }
                ]
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.build()
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertEqual(results['key0'], ['User: Some-gal-or-guy'])

        self.assertEqual(results['key1'], ['19'])

        self.assertTrue(results['key2'])

        self.assertTrue(results['key3'])

        self.assertTrue(results['key4'])

        self.assertTrue(results['key5'])

        self.assertTrue(results['key6'])

        self.assertTrue(results['key7'])

        self.assertTrue(results['key8'])

        self.assertTrue(results['key9'])

        self.assertFalse(results['key10'])

        self.assertTrue(results['key11'])

        self.assertFalse(results['key12'])

    def test_regex_threshold(self):
        """Ensure the match_count parser works appropriately."""

        plugins.initialize_plugins(self.pav_cfg)

        test_cfg = {
            'scheduler': 'raw',
            'run': {
                # This will result in 4 output files.
                # run.log, other.log, other2.log, other3.log
                'cmds': [
                    'echo "Test Name: FakeTest\n"',
                    'echo "User: Some-gal-or-guy\n"',
                    'echo "result1=19\n"',
                    'echo "result3=test\n"',
                    'echo "result9=-12\n"',
                    'echo "result12=9.9\n"',
                    'echo "result13=-22.2\n"',
                    'echo "result98=\n"',
                    'echo "result50=18.2,result51=18.3\n"',
                    'echo "overall=whatevs"'
                ]
            },
            'results': {
                'regex': [
                    {
                        # Look at the default output file. (run.log)
                        # Test for finding greater than the threshold present
                        'key': 'key0',
                        'regex': r'result',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '7',
                    },
                    {
                        # Test for finding equal to the threshold present
                        'key': 'key1',
                        'regex': r'result',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '8',
                    },
                    {
                        # Test for finding fewer than the threshold present
                        'key': 'key2',
                        'regex': r'result',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '9',
                    },
                    {
                        # Test for finding equal to of a more specific search
                        'key': 'key3',
                        'regex': r'result1',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '3',
                    },
                    {
                        # Test for finding fewer than of a more specific search
                        'key': 'key4',
                        'regex': r'result1',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '4',
                    },
                    {
                        # Test for a threshold of zero
                        'key': 'key5',
                        'regex': r'overall=whatevs',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '0',
                    },
                    {
                        # Test for a more complex search
                        'key': 'key6',
                        'regex': r'overall=whatevs',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '1',
                    },
                    {
                        # Test for a more complex search that fails
                        'key': 'key7',
                        'regex': r'overall=whatevs',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '2',
                    },
                    {
                        # Test for a more complex search that fails
                        'key': 'key8',
                        'regex': r'totallynotthere',
                        'action': result_parsers.ACTION_TRUE,
                        'match_type': result_parsers.MATCH_ALL,
                        'threshold': '0',
                    },
                    {
                        # A test using the 'result' key is required.
                        'key': 'result',
                        'regex': r'^overall=(.*)$',
                        'action': result_parsers.ACTION_TRUE,
                    }
                ]
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.build()
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertTrue(results['key0'])

        self.assertTrue(results['key1'])

        self.assertFalse(results['key2'])

        self.assertTrue(results['key3'])

        self.assertFalse(results['key4'])

        self.assertTrue(results['key5'])

        self.assertTrue(results['key6'])

        self.assertFalse(results['key7'])

        self.assertFalse(results['key8'])

        self.assertTrue(results['result'])

    def test_regex_expected_sanity(self):
        """Sanity check for the expected parser."""

        plugins.initialize_plugins(self.pav_cfg)

        test_cfg = {
            'scheduler': 'raw',
            'run': {
                # This will result in 4 output files.
                # run.log, other.log, other2.log, other3.log
                'cmds': [
                    "echo I am a test's output.",
                    "echo Short and stout.",
                    "echo My min speed is 438.5",
                    "echo and my max is 968.3",
                    "echo What do you think of that, punk?",
                    "echo Also, here's another number to confuse you. 3.7. Take that."
                ]
            },
            'results': {
                'regex': [
                    {
                        # A test using the 'result' key is required.
                        'key': 'result',
                        'regex': r'max is',
                    },
                    {
                        'key': 'key',
                        'regex': r'max is (.*)$'
                    },
                    {
                        # A test using the 'result' key is required.
                        'key': 'key1',
                        'regex': r'max is (.*)$',
                        'expected': ['900-1000'],
                        'action': result_parsers.ACTION_TRUE,
                    },
                ]
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.build()
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertEqual(results['key'], '968.3')

        self.assertTrue(results['result'])

    def test_table_result_parser(self):
        """
        Makes sure Table Result Parser Works
        :return:
        """
        plugins.initialize_plugins(self.pav_cfg)

        # line+space delimiter
        table_test1 = {
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "SAMPLE TABLE"',
                    'echo "Col1 | Col2 | Col3"',
                    'echo "------------------"',
                    'echo "data1 | 3 | data2"',
                    'echo "data3 | 8 | data4"',
                    'echo "data5 |   | data6"',
                    'echo "some other text that doesnt matter"'
                ]
            },
            'results': {
                'table': [
                    {
                        'key': 'table1',
                        'delimiter': r'\\|',
                        'col_num': '3'
                    }
                ],
                'constant': [
                    {
                        'key': 'result',
                        'const': 'table1'
                    }
                ]
            }
        }

        test = self._quick_test(table_test1, 'result_parser_test')
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertEqual(['data1', 'data3', 'data5'], results['table1']['Col1'])
        self.assertEqual(['3', '8', ' '], results['table1']['Col2'])
        self.assertEqual(['data2', 'data4', 'data6'], results['table1']['Col3'])

        # space delimiter
        table_test2 = {
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "SAMPLE TABLE"',
                    'echo "d1 d2 d3"',
                    'echo "d4 d5 d6"',
                    'echo "d7   d9"',
                    'echo "some other text that doesnt matter"'
                ]
            },
            'results': {
                'table': [
                    {
                        'key': 'table2',
                        'delimiter': ' ',
                        'col_num': '3'
                    }
                ],
                'constant': [
                    {
                        'key': 'result',
                        'const': 'table2'
                    }
                ]
            }
        }

        test = self._quick_test(table_test2, 'result_parser_test')
        test.build()
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertEqual(['d4', 'd7'], results['table2']['d1'])
        self.assertEqual(['d5', ' '], results['table2']['d2'])
        self.assertEqual(['d6', 'd9'], results['table2']['d3'])

        # comma delimiter
        table_test3 = {
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "----------- Comma-delimited summary ---------"',
                    'echo "./clomp_hwloc 4 -1 256 10 32 1 100, calc_deposit, OMP Barrier, Scaled Serial Ref, Bestcase OMP, Static OMP, Dynamic OMP, Manual OMP"',
                    'echo "Runtime,   0.000,   0.919,   2.641,   0.517,   2.345,  16.392,   2.324"',
                    'echo "us/Loop,    0.00,    9.41,   27.04,    5.29,   24.01,  167.85,   23.79"',
                    'echo "Speedup,     N/A,     N/A,    1.00,     5.1,     1.1,     0.2,     1.1"',
                    'echo "Efficacy,    N/A,     N/A,     N/A,   100%,   22.0%,    3.2%, 22.2%"',
                    'echo "Overhead,    N/A,     N/A,     N/A,    0.00,   18.72,  162.56,   18.50"',
                    'echo "CORAL2 RFP, 4 -1 256 10 32 1 100, 1.00, 27.04, 27.04, 9.41, 5.1, 18.72, 1.1, 162.56, 0.2, 18.50, 1.1"'
                ]
            },
            'results': {
                'table': [
                    {
                        'key': 'table3',
                        'delimiter': ',',
                        'col_num': '8',
                        'has_header': 'True',
                        'col_names': [' ', 'calc_deposit', 'OMP Barrier',
                                      'Scaled Serial Ref', 'Bestcase OMP',
                                      'Static OMP', 'Dynamic OMP', 'Manual OMP']
                    }
                ],
                'constant': [
                    {
                        'key': 'result',
                        'const': 'table3'
                    }
                ]
            }
        }

        test = self._quick_test(table_test3, 'result_parser_test')
        test.build()
        test.run()

        results = result_parsers.parse_results(
            test=test,
            results={}
        )

        self.assertEqual('0.000', results['table3']['calc_deposit']['Runtime'])
        self.assertEqual('9.41', results['table3']['OMP Barrier']['us/Loop'])
        self.assertEqual('1.00',
                         results['table3']['Scaled Serial Ref']['Speedup'])
        self.assertEqual('100%', results['table3']['Bestcase OMP']['Efficacy'])
        self.assertEqual('18.72', results['table3']['Static OMP']['Overhead'])
        self.assertEqual('16.392', results['table3']['Dynamic OMP']['Runtime'])
        self.assertEqual('23.79', results['table3']['Manual OMP']['us/Loop'])
