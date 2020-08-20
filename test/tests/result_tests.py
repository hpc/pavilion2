import copy
import datetime
import json
import logging
import pprint
from collections import OrderedDict

import pavilion.result
import yaml_config as yc
from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import result
from pavilion.plugins.commands import run
from pavilion.result import parsers, ResultError, base
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase
from pavilion.test_config import resolver

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
            'result_parse': {
                'regex': {

                    'basic': {'regex': r'.* World'},
                    'true': {
                        # Look all the log files, and save 'True' on match.
                        'files': ['../run.log'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                    },
                    'false': {
                        # As before, but false. Also, with lists of data.
                        # By multiple globs.
                        'files': ['../run.log', 'other.*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_FALSE,
                    },
                    'count': {
                        # As before, but keep match counts.
                        'files': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'match_type': parsers.MATCH_ALL,
                        'action': parsers.ACTION_COUNT,
                        'per_file': parsers.PER_FULLNAME,
                    },
                    'fullname': {
                        # Store matches by fullname
                        'files': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'per_file': parsers.PER_FULLNAME,
                    },
                    'name': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files': ['other.*'],
                        'regex': r'.* World',
                        'per_file': parsers.PER_NAME,
                    },
                    'name_list': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files': ['*.log'],
                        'regex': r'World',
                        'per_file': parsers.PER_NAME_LIST,
                    },
                    'fullname_list': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files': ['*.log'],
                        'regex': r'World',
                        'per_file': parsers.PER_FULLNAME_LIST,
                    },
                    'lists': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'match_type': parsers.MATCH_ALL,
                        'per_file': parsers.PER_LIST,
                    },
                    'all': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                        'per_file': parsers.PER_ALL
                    },
                    'result': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                        'per_file': parsers.PER_ANY
                    },
                }
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.run()

        results = base.base_results(test)
        parsers.parse_results(test, results)

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

        self.assertEqual(results['per_file']['run.log']['count'], 2)
        self.assertEqual(results['per_file']['other.log']['count'], 1)

        self.assertEqual(results['per_file']['other.log']['fullname'],
                         'In a World')

        self.assertEqual(results['name_list'],
                         ['other', 'other3'])

        self.assertEqual(results['fullname_list'],
                         ['other.log', 'other3.log'])

        self.assertIn(results['per_file']['other']['name'],
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
            ({'ok':{'regex': r'foo'}}, None),
            # Reserved key
            ({'created': {'regex': r'foo'}}, ResultError),
            # Missing regex
            ({'nope': {}}, yc.RequiredError),
            # Error in result parser specific args
            ({'test': {'regex': '[[['}}, ResultError),
            # You can't store the 'result' key 'per_file'.
            ({'result': {'per_file': 'name', 'regex': 'foo'}},
             ResultError),
        ]

        for parsers_conf, err_type in parser_tests:

            test_cfg = self._quick_test_cfg()
            test_cfg['result_parse'] = {
                    'regex': parsers_conf,
                }

            if err_type is not None:
                with self.assertRaises(err_type,
                                       msg="Error '{}' not raised for '{}'"
                                           .format(err_type, parsers_conf)):

                    # We want a finalized, validated config. This may raise
                    # errors too.
                    test = self._quick_test(test_cfg)

                    pavilion.result.check_config(test.config['result_parse'],
                                                 {})
            else:
                test = self._quick_test(test_cfg)
                pavilion.result.check_config(test.config['result_parse'], {})

        evaluate_confs = [
            # Reserved key
            {'started': 'bar'},
            {'foo': 'bar.3 +'}
        ]

        for eval_conf in evaluate_confs:
            with self.assertRaises(ResultError):
                pavilion.result.check_config({}, eval_conf)

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
            'result_parse': {
                'table': {
                    'table1': {
                        'delimiter': r'\|',
                        'col_num': '3'
                    },
                },
            }
        }

        test = self._quick_test(table_test1, 'result_parser_test')
        test.run()

        results = {'pav_result_errors': []}
        parsers.parse_results(test, results)

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
            'result_parse': {
                'table': {
                    'table2': {
                        'delimiter': ' ',
                        'col_num': '3'
                    },
                },
            }
        }

        test = self._quick_test(table_test2, 'result_parser_test')
        test.run()

        results = {'pav_result_errors': []}
        parsers.parse_results(test, results)

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
            'result_parse': {
                'table': {
                    'table3': {
                        'delimiter': ',',
                        'col_num': '8',
                        'has_header': 'True',
                        'by_column': 'True',
                        'col_names': [
                            ' ', 'calc_deposit', 'OMP Barrier',
                            'Scaled Serial Ref', 'Bestcase OMP',
                            'Static OMP', 'Dynamic OMP', 'Manual OMP']
                    }
                }
            }
        }

        test = self._quick_test(table_test3, 'result_parser_test')
        test.run()

        results = {'pav_result_errors': []}
        parsers.parse_results(test, results)

        self.assertEqual('0.000', results['table3']['calc_deposit']['Runtime'])
        self.assertEqual('9.41', results['table3']['OMP Barrier']['us/Loop'])
        self.assertEqual('1.00',
                         results['table3']['Scaled Serial Ref']['Speedup'])
        self.assertEqual('100%', results['table3']['Bestcase OMP']['Efficacy'])
        self.assertEqual('18.72', results['table3']['Static OMP']['Overhead'])
        self.assertEqual('16.392', results['table3']['Dynamic OMP']['Runtime'])
        self.assertEqual('23.79', results['table3']['Manual OMP']['us/Loop'])

    def test_evaluate(self):

        ordered = OrderedDict()
        ordered['val_a'] = '3'
        ordered['val_b'] = 'val_a + 1'

        base_cfg = self._quick_test_cfg()
        base_cfg['run']['cmds'] = [
            'echo True > bool.out',
            'echo 1 > int.out',
            'echo 2.3 > float.out',
            'echo "blarg" > str.out',
        ]
        base_cfg['result_parse'] = {
            'regex': {
                'data': {
                    'regex': r'.*',
                    'per_file': 'name',
                    'files': '*.out',
                }
            }
        }

        # (evaluate_conf, expected values)
        evaluate_tests = [
            ({'result': 'True'}, {'result': 'PASS'}),
            ({'result': 'return_value != 0',
              'blarg': 'return_value != 0'}, {'result': 'FAIL'}),
            # Make sure functions work.
            ({'sum': 'sum([1,2,3])'}, {'sum': 6}),

            # Check basic math.
            ({'val_a': '3',
              'val_b': 'val_a + val_c',
              'val_c': 'val_a*2'},
             {'val_a': 3, 'val_b': 9, 'val_c': 6}),

            # Check list operations.
            ({'list_ops': '[1, 2, 3] == 2'},
             {'list_ops': [False, True, False]}),
            ({'type_conv': 'per_file.*.data'},
             # The order here should be consistent
             {'type_conv': [True, 2.3, 1, "blarg"]})
        ]

        for evaluate_conf, exp_results in evaluate_tests:

            cfg = copy.deepcopy(base_cfg)
            cfg['result_evaluate'] = evaluate_conf

            test = self._quick_test(cfg)
            test.run()

            results = test.gather_results(0)

            for rkey, rval in exp_results.items():
                self.assertEqual(
                    results[rkey],
                    exp_results[rkey],
                    msg="Result mismatch for {}.\n"
                        "Expected '{}', got '{}'\n"
                        "Full Results:\n{}"
                        .format(evaluate_conf, exp_results[rkey],
                                results[rkey], pprint.pformat(results)))

    def test_evaluate_errors(self):
        error_confs = (
            {'val_a': 'undefined_a'},  # No such variable
            {'val_b': 'parse_error ++'},  # Parse error
            {'val_c': '"hello" + 3'},  # Value Error
            {'val_d': 'val_e + 3', 'val_e': 'val_d + 1'},  # Reference loop.
            {'val_f': 'really.complicated.*.variable.error'}
        )

        for error_conf in error_confs:
            cfg = self._quick_test_cfg()
            cfg['result_evaluate'] = error_conf

            test = self._quick_test(cfg)
            test.run()

            with self.assertRaises(result.ResultError):
                result.evaluate_results({}, error_conf)

    def test_result_cmd(self):
        """Make sure the result command works as expected, including the
        re-run option."""

        result_cmd = commands.get_command('result')
        result_cmd.silence()
        run_cmd = commands.get_command('run')  # type: run.RunCommand
        run_cmd.silence()

        rerun_cfg = self.pav_cfg.copy()
        rerun_cfg['config_dirs'] = [
            self.PAV_LIB_DIR,
            self.PAV_ROOT_DIR/'test/data/configs-rerun',
        ]

        arg_parser = arguments.get_parser()
        run_args = arg_parser.parse_args(['run', 'result_tests.*'])
        if run_cmd.run(self.pav_cfg, run_args) != 0:
            cmd_out, cmd_err = run_cmd.clear_output()
            self.fail("Run command failed: \n{}\n{}".format(cmd_out, cmd_err))

        for test in run_cmd.last_tests:
            test.wait(3)

        res_args = arg_parser.parse_args(
            ('result', '--full') + tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        res_args = arg_parser.parse_args(
            ('result',) + tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        for test in run_cmd.last_tests:
            # Each of these tests should have a 'FAIL' as the result.
            self.assertEqual(test.results['result'], TestRun.FAIL)

        # Make sure we can re-run results, even with permutations.
        # Check that the changed results are what we expected.
        result_cmd.clear_output()
        res_args = arg_parser.parse_args(
            ('result', '--re-run', '--json') +
            tuple(str(t.id) for t in run_cmd.last_tests))
        result_cmd.run(rerun_cfg, res_args)

        data, err = result_cmd.clear_output()
        results = json.loads(data)

        basic = results['result_tests.basic']
        per1 = results['result_tests.permuted.1']
        per2 = results['result_tests.permuted.2']

        self.assertEqual(basic['result'], TestRun.PASS)
        self.assertEqual(per1['result'], TestRun.FAIL)
        self.assertEqual(per2['result'], TestRun.PASS)

        # Make sure we didn't save any of the changes.
        orig_test = run_cmd.last_tests[0]
        reloaded_test = TestRun.load(self.pav_cfg, orig_test.id)
        self.assertEqual(reloaded_test.results, orig_test.results)
        self.assertEqual(reloaded_test.config, orig_test.config)

        # Make sure the log argument doesn't blow up.
        res_args = arg_parser.parse_args(
            ('result', '--show-log') +
            tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

    def test_re_search(self):
        """"""

        answers = {
            'hello': '33',
            'ip': '127.33.123.43',
            'all_escapes': r'.^$*\+?\{}\[]|'
        }

        test = self._load_test('re_search')[0]
        test.run()

        results = test.gather_results(0)

        for key, answer in answers.items():
            self.assertEqual(results[key], answer)

    def test_flatten_results(self):
        """Make sure result flattening workds as expected."""

        config = self._quick_test_cfg()

        config['run']['cmds'] = [
            'for i in 1 2 3 4; do echo "hello $i" > $i.out; done'
        ]
        config['result_parse']['regex'] = {
            'hello': {
                'regex':    r'hello \d+',
                'files':    '*.out',
                'per_file': 'name',
            }
        }

        test = self._quick_test(config, name="flatten_results_test")

        run_result = test.run()
        results = test.gather_results(run_result)
        test.save_results(results)

        records = {}

        with open(self.pav_cfg['result_log']) as results_log:
            for line in results_log.readlines():
                _result = json.loads(line)

                if _result['name'] != "unittest.flatten_results_test":
                    continue

                records[_result['file']] = _result['hello']

        self.assertEqual(records, {
            '1': 'hello 1',
            '2': 'hello 2',
            '3': 'hello 3',
            '4': 'hello 4',
        })

