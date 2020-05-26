import datetime
import logging

import pavilion.result
import yaml_config as yc
from pavilion import arguments
from pavilion import plugins
from pavilion.result import parsers, ResultError, base
from pavilion.unittest import PavTestCase

LOGGER = logging.getLogger(__name__)


class ResultParserTests(PavTestCase):

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_parse_results(self):
        """Check all the different ways in which we handle parsed results."""

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
                'parse': {
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
                            'action': parsers.ACTION_TRUE,
                        },
                        {
                            # As before, but false. Also, with lists of data.
                            'key': 'false',
                            # By multiple globs.
                            'files': ['../run.log', 'other.*'],
                            'regex': r'.* World',
                            'action': parsers.ACTION_FALSE,
                        },
                        {
                            # As before, but keep match counts.
                            'key': 'count',
                            'files': ['../run.log', '*.log'],
                            'regex': r'.* World',
                            'match_type': parsers.MATCH_ALL,
                            'action': parsers.ACTION_COUNT,
                            'per_file': parsers.PER_FULLNAME,
                        },
                        {
                            # Store matches by fullname
                            'key': 'fullname',
                            'files': ['../run.log', '*.log'],
                            'regex': r'.* World',
                            'per_file': parsers.PER_FULLNAME,
                        },
                        {
                            # Store matches by name stub
                            # Note there is a name conflict here between other.txt
                            # and other.log.
                            'key': 'name',
                            'files': ['other.*'],
                            'regex': r'.* World',
                            'per_file': parsers.PER_NAME,
                        },
                        {
                            # Store matches by name stub
                            # Note there is a name conflict here between other.txt
                            # and other.log.
                            'key': 'name_list',
                            'files': ['*.log'],
                            'regex': r'World',
                            'per_file': parsers.PER_NAME_LIST,
                        },
                        {
                            # Store matches by name stub
                            # Note there is a name conflict here between other.txt
                            # and other.log.
                            'key': 'fullname_list',
                            'files': ['*.log'],
                            'regex': r'World',
                            'per_file': parsers.PER_FULLNAME_LIST,
                        },
                        {
                            'key': 'lists',
                            'files': ['other*'],
                            'regex': r'.* World',
                            'match_type': parsers.MATCH_ALL,
                            'per_file': parsers.PER_LIST,
                        },
                        {
                            'key': 'all',
                            'files': ['other*'],
                            'regex': r'.* World',
                            'action': parsers.ACTION_TRUE,
                            'per_file': parsers.PER_ALL
                        },
                        {
                            'key': 'result',
                            'files': ['other*'],
                            'regex': r'.* World',
                            'action': parsers.ACTION_TRUE,
                            'per_file': parsers.PER_ANY
                        },
                    ]
                }
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.run()

        results = parsers.parse_results(
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

        self.assertEqual(results['fn']['run.log']['count'], 2)
        self.assertEqual(results['fn']['other.log']['count'], 1)

        self.assertEqual(results['fn']['other.log']['fullname'],
                         'In a World')

        self.assertEqual(results['name_list'],
                         ['other', 'other3'])

        self.assertEqual(results['fullname_list'],
                         ['other.log', 'other3.log'])

        self.assertIn(results['n']['other']['name'],
                      ['In a World', "I'm here to cause World"])
        self.assertIn("Duplicate file key 'other' matched by name",
                      [e['msg'] for e in results['pav_result_errors']])

        self.assertEqual(sorted(results['lists']),
                         sorted(['and someone saves the World',
                                 'In a World',
                                 "I'm here to cause World"]))

        self.assertEqual(results['all'], False)
        self.assertEqual(results['result'], True)

    def test_check_config(self):

        # A list of regex
        parser_tests = [
            # Should work fine.
            ([{'key': 'ok', 'regex': r'foo'}], None),
            # Repeated key
            ([{'key': 'repeated', 'regex': r'foo'},
             {'key': 'repeated', 'regex': r'foo'}], ResultError),
            # Reserved key
            ([{'key': 'created', 'regex': r'foo'}], ResultError),
            # Missing key
            ([{'regex': r'foo'}], yc.RequiredError),
            ([{'key': 'started', 'regex': r'foo'}], ResultError),
            # Missing regex
            ([{'key': 'nope'}], yc.RequiredError),
            ([{'key': 'test', 'regex': '[[['}], ResultError),
        ]

        for parsers_conf, err_type in parser_tests:

            test_cfg = self._quick_test_cfg()
            test_cfg['results'] = {
                    'parse': {
                        'regex': parsers_conf,
                    },
                    'evaluate': {},
                }

            if err_type is not None:
                with self.assertRaises(err_type,
                                       msg="Error '{}' not raised for '{}'"
                                           .format(err_type, parsers_conf)):

                    # We want a finalized, validated config. This may raise
                    # errors too.
                    test = self._quick_test(test_cfg)

                    pavilion.result.check_config(test.config['results'])
            else:
                test = self._quick_test(test_cfg)
                pavilion.result.check_config(test.config['results'])

        analysis_confs = [
            # Reserved key
            {'started': 'bar'},
            {'foo': 'bar.3 +'}
        ]

        for analysis_conf in analysis_confs:
            result_cfg = {
                'evaluate': analysis_conf,
                'parse': {},
            }
            pavilion.result.check_config(result_cfg)

    def test_base_results(self):
        """Make all base result functions work."""

        test = self._quick_test(
            cfg={
                # The only required param.
                'name': 'blank_test',
                'scheduler': 'raw',
            })

        now = datetime.datetime.now()

        # Any test that tries to run will have these, and only tests that
        # try to run get results.
        test.started = now
        test.finished = now + datetime.timedelta(seconds=3)
        test.job_id = 'test'

        base_results = base.base_results(test)
        # This one has to be set manually.
        base_results['return_value'] = 0

        for key in base.BASE_RESULTS.keys():
            self.assertIn(key, base_results)
            # Base result keys should have a non-None value, even from an
            # empty config file.
            self.assertIsNotNone(
                base_results[key],
                msg="Base result key '{}' was None.".format(key))

    def test_table_result_parser(self):
        """
        Makes sure Table Result Parser Works
        :return:
        """

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
                'parse': {
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
        }

        test = self._quick_test(table_test1, 'result_parser_test')
        test.run()

        results = parsers.parse_results(
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
                'parse': {
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
        }

        test = self._quick_test(table_test2, 'result_parser_test')
        test.run()

        results = parsers.parse_results(
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
                'parse': {
                    'table': [
                        {
                            'key': 'table3',
                            'delimiter': ',',
                            'col_num': '8',
                            'has_header': 'True',
                            'by_column': 'True',
                            'col_names': [
                                ' ', 'calc_deposit', 'OMP Barrier',
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
        }

        test = self._quick_test(table_test3, 'result_parser_test')
        test.run()

        results = parsers.parse_results(
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

    def test_analysis(self):

        # (anaysis_conf, expected values)
        analysis_tests = [
            ({'result': 'True'}, {'result': 'PASS'}),
            ({'result': 'return_value != 0'}, {'result': 'FAIL'}),
            ({'sum': 'sum([1,2,3])'}, {'sum': 6}),
        ]

        for analysis_conf, exp_results in analysis_tests:

            cfg = self._quick_test_cfg()
            cfg['results'] = {}
            cfg['results']['evaluate'] = analysis_conf

            test = self._quick_test(cfg)
            test.run()

            results = test.gather_results(0)

            for rkey, rval  in exp_results.items():
                self.assertEqual(
                    results[rkey],
                    exp_results[rkey],
                    msg="Result mismatch for {}.".format(analysis_conf))





