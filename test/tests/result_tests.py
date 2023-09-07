"""Test Result gathering"""

import copy
import datetime
import io
import json
import logging
import pprint
from collections import OrderedDict

import pavilion.errors
import pavilion.result
import pavilion.result.common
import yaml_config as yc
from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import result
from pavilion import utils
from pavilion.result import base
from pavilion.errors import ResultError
from pavilion.result_parsers import base_classes
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase

LOGGER = logging.getLogger(__name__)


class ResultParserTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Don't limit the size of the error diff.
        self.maxDiff = None

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
                    'echo "Multipass 1, 2, 3"',
                    'echo "A: 5"',
                    'echo "B: 6"',
                    'echo "B: 2"',
                    'echo "C: 4"',
                    'echo "D: 8"',
                    'echo "B: 3"',
                    'echo "D: 1"',
                    'echo "E: 7"',
                    'echo "In a World where..." >> other.log',
                    'echo "What in the World" >> other.log',
                    'echo "something happens..." >> other2.log',
                    'echo "and someone saves the World." >> other3.log',
                    'echo "I\'m here to cause Worldwide issues." >> other.txt'
                ]
            },
            'result_parse': {
                'regex': {
                    'Basic': {'regex': r'.* World'},
                    'BC': {
                        'regex': r'.: (\d)',
                        'preceded_by': [r'^B:', r'^C:'],
                        'match_select': 'all',
                    },
                    'bcd': {
                        'regex': r'.: (\d)',
                        'preceded_by': [r'^B:', r'^C:'],
                        'for_lines_matching': r'^D:',
                        'match_select': 'all',
                    },
                    'bees': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select': 'all',
                    },
                    'last_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       'last',
                    },
                    'middle_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       '1',
                    },
                    'other_middle_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       '-2',
                    },
                    'no_lines_match': {
                        'regex':              r'.*',
                        'for_lines_matching': r'nothing',
                        'match_select':       base_classes.MATCH_ALL,
                    },
                    'no_lines_match_last': {
                        'regex':              r'.*',
                        'for_lines_matching': r'nothing',
                        'match_select':       base_classes.MATCH_FIRST,
                    },
                    'b_sum': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select': 'all',
                        'action': 'store_sum',
                    },
                    'min': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^[A-E]:',
                        'match_select': 'all',
                        'action': 'store_min',
                    },
                    'med': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^[A-E]:',
                        'match_select': 'all',
                        'action': 'store_median',
                    },
                    'mean': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^[A-E]:',
                        'match_select': 'all',
                        'action': 'store_mean',
                    },
                    'max': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^[A-E]:',
                        'match_select': 'all',
                        'action': 'store_max',
                    },
                    'mp1, _  ,   mp3': {
                        'regex': r'Multipass (\d), (\d), (\d)'
                    },
                    'mp4,mp5': {
                        'regex': r'Multipass (\d), (\d), (\d)'
                    },
                    'true': {
                        # Look all the log files, and save 'True' on match.
                        'files':  ['../run.log'],
                        'regex': r'.* World',
                        'action': base_classes.ACTION_TRUE,
                    },
                    'false': {
                        # As before, but false. Also, with lists of data.
                        # By multiple globs.
                        'files':  ['../run.log', 'other.*'],
                        'regex': r'.* World',
                        'action': base_classes.ACTION_FALSE,
                    },
                    'count': {
                        # As before, but keep match counts.
                        'files':        ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'match_select': base_classes.MATCH_ALL,
                        'action':       base_classes.ACTION_COUNT,
                        'per_file':     base_classes.PER_NAME,
                    },
                    'name': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files':    ['other.*'],
                        'regex': r'.* World',
                        'per_file': base_classes.PER_NAME,
                    },
                    'name_list': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files':    ['*.log'],
                        'regex': r'World',
                        'per_file': base_classes.PER_NAME_LIST,
                    },
                    'lists': {
                        'files':        ['other*'],
                        'regex': r'.* World',
                        'match_select': base_classes.MATCH_ALL,
                        'per_file':     base_classes.PER_LIST,
                    },
                    'all': {
                        'files':    ['other*'],
                        'regex': r'.* World',
                        'action':   base_classes.ACTION_TRUE,
                        'per_file': base_classes.PER_ALL
                    },
                    'result': {
                        'files':    ['other*'],
                        'regex': r'.* World',
                        'action':   base_classes.ACTION_TRUE,
                        'per_file': base_classes.PER_ANY
                    },
                }
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.run()

        results = test.gather_results(0)

        expected = {
            'Basic': 'Hello World',
            'BC': [8],
            'bcd': [8],
            'bees': [6, 2, 3],
            'b_sum': 11,
            'min': 1,
            'med': 4.5,
            'mean': 4.5,
            'max': 8,
            'last_b': 3,
            'middle_b': 2,
            'other_middle_b': 2,
            'no_lines_match': [],
            'no_lines_match_last': None,
            'true': True,
            'false': False,
            'per_file': {
                'other': {
                    'count': 2,
                    'name': "I'm here to cause World"},
                'other2': {
                    'count': 0},
                'other3': {
                    'count': 1},
                'run': {
                    'count': 2},
            },
            'mp1': 1,
            'mp3': 3,
            'mp4': 1,
            'mp5': 2,
            'name_list': ['other', 'other3'],
            'lists': [
                "In a World",
                "What in the World",
                "I'm here to cause World",
                "and someone saves the World"],
            'all': False,
            'result': 'PASS',  # Any test
        }

        for key in expected:
            self.assertEqual(results[key], expected[key],
                             msg="Difference for key {}".format(key))
        self.assertIn(
            "When storing value for key 'name' per 'name', multiple files "
            "normalized to the name 'other': other.log, other.txt",
            results[result.RESULT_ERRORS])

        def find_hidden(resultd: dict) -> set:
            """Find any result bits that start with underscore."""

            found = set()

            for rkey, value in resultd.items():
                if rkey.startswith('_'):
                    found.add(rkey)
                if isinstance(value, dict):
                    found.update(find_hidden(value))

            return found

        self.assertEqual(find_hidden(results), set(),
                         msg="All hidden ('_' prefixed) result keys were "
                             "supposed to be deleted.")

    def test_check_config(self):

        # A list of regex
        parser_tests = [
            # Should work fine.
            ({'ok': {'regex': r'foo'}}, None),
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

    def test_json_parser(self):
        """Check that JSON parser returns expected results."""

        cfg = self._quick_test_cfg()
        cfg['build'] = {'source_path': 'json-blob.txt'}
        cfg['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'include_only': ['foo.bar'],
                    'exclude': ['foo2'],
                    'stop_at': 'this is a',
                }
            }
        }

        expected_json = {'foo': {'bar': [1, 3, 5]}}

        test = self._quick_test(cfg=cfg)
        test.run()

        results = test.gather_results(0)

        self.assertEqual(results['myjson'], expected_json)

    def test_json_parser_errors(self):
        """Check that JSON parser raises correct errors for a
        variety of different inputs."""

        cfg_exclude_key_error = self._quick_test_cfg()
        cfg_exclude_key_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_exclude_key_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'exclude': ['foo.badkey'],
                    'stop_at': 'this is a',
                }
            }
        }

        cfg_exclude_type_error = self._quick_test_cfg()
        cfg_exclude_type_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_exclude_type_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'exclude': ['foo.bar.badkey'],
                    'stop_at': 'this is a',
                }
            }
        }

        cfg_include_key_error = self._quick_test_cfg()
        cfg_include_key_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_include_key_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'include_only': ['foo.badkey'],
                    'exclude': ['foo.bar'],
                    'stop_at': 'this is a',
                }
            }
        }

        cfg_include_type_error = self._quick_test_cfg()
        cfg_include_type_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_include_type_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'include_only': ['foo.buzz.badkey'],
                    'exclude': ['foo.bar'],
                    'stop_at': 'this is a',
                }
            }
        }

        cfg_stopat_none_error = self._quick_test_cfg()
        cfg_stopat_none_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_stopat_none_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'include_only': ['foo.bar'],
                    'exclude': ['foo.bar'],
                }
            }
        }

        cfg_stopat_bad_error = self._quick_test_cfg()
        cfg_stopat_bad_error['build'] = {'source_path': 'json-blob.txt'}
        cfg_stopat_bad_error['result_parse'] = {
            'json': {
                'myjson': {
                    'files': ['json-blob.txt'],
                    'include_only': ['foo.bar'],
                    'exclude': ['foo.bar'],
                    'stop_at': 'this string does not exist',
                }
            }
        }

        cfgs = [
            # config, expected error
            (cfg_exclude_key_error,"Excluded key foo.badkey doesn't exist"),
            (cfg_exclude_type_error, "but foo.bar's value isn't a mapping"),
            (cfg_include_key_error, "Explicitly included JSON key 'foo.badkey' doesn't exist"),
            (cfg_include_type_error, "Explicitly included key 'foo.buzz.badkey' doesn't exist "
                                     "in original JSON."),
            (cfg_stopat_none_error, "Invalid JSON: Extra data:"),
            (cfg_stopat_bad_error, "Invalid JSON: Extra data:"),
        ]

        for cfg, exp_err in cfgs:
            test = self._quick_test(cfg=cfg)
            test.run()
            log = io.StringIO()
            results = test.gather_results(0, log_file=log)
            self.assertIn(exp_err, results[result.RESULT_ERRORS][0]) #, msg=log.getvalue())

    def test_table_parser(self):
        """Check table result parser operation."""

        # start & nth start with line+space delimiter
        cfg = {
            'scheduler': 'raw',
            'build': {
                'source_path': 'tables.txt'
            },
            'run': {
                'cmds': [
                    'cat tables.txt'
                ]
            },
            'result_parse': {
                'table': {
                    'Table1': {
                        'delimiter_re': r'\|',
                        'col_names': ['cola', 'soda', 'pop'],
                        'preceded_by': ['table1', '', ''],
                        'for_lines_matching': '^- - -',
                    },
                    'table1b': {
                        'delimiter_re': r'\|',
                        'has_row_labels': 'False',
                        'preceded_by': ['table1'],
                        'for_lines_matching': '^--  --  --',
                    },
                    'table2': {
                        'delimiter_re':       r'\|',
                        'preceded_by':        ['table2'],
                        'for_lines_matching': '^--  --  --',
                    },
                    'table2_by_col': {
                        'delimiter_re':       r'\|',
                        'preceded_by':        ['table2'],
                        'for_lines_matching': '^--  --  --',
                        'by_column':          'True',
                    },
                    'table3': {
                        'delimiter_re':       r'\|',
                        'for_lines_matching': '^Col1',
                        'match_select': '1',
                    },
                    'table4': {
                        'for_lines_matching': 'colA',
                    },
                    'table5': {
                        'for_lines_matching': r'\s+col1',
                        'table_end_re': r'^some other words',
                    },
                    'clomp': {
                        'preceded_by': '-+ Comma-delimited summary -+',
                        'delimiter_re': r',',
                        'by_column': 'True',
                    },
                    'mdtest': {
                        'preceded_by': '^SUMMARY:',
                        'delimiter_re': r'[ :]{2,}',
                        'lstrip': 'True',
                    }
                }
            }
        }

        expected = {
            'Table1': {
                'data1': {'cola': 3,    'soda': 'data4', 'pop': None},
                'data2': {'cola': 8,    'soda': 'data5', 'pop': None},
                'data3': {'cola': None, 'soda': 'data6', 'pop': None},
            },
            'table1b': {
                'row_0': {'col1': 'data1', 'col2': 3, 'col3': 'data4'},
                'row_1': {'col1': 'data2', 'col2': 8, 'col3': 'data5'},
                'row_2': {'col1': 'data3', 'col2': None, 'col3': 'data6'},
            },
            'table2': {
                'data7': {'col2': 0, 'col3': 'data10'},
                'data8': {'col2': 9, 'col3': 'data11'},
                'data9': {'col2': None, 'col3': 'data12'},
                'row_0': {'col2': 90, 'col3': 'data90'}
            },
            'table2_by_col': {
                 'col2': {'data7': 0, 'data8': 9, 'data9': None, 'row_0': 90},
                 'col3': {'data7': 'data10', 'data8': 'data11',
                          'data9': 'data12', 'row_0': 'data90'}
            },
            'table3': {
                'data13': {'col2': 4, 'col3': None},
                'data14512': {'col2': 8, 'col3': 'data17'},
                'data15': {'col2': None, 'col3': 'data18'}
            },
            'table4': {
                '11111': {'colb': 12222, 'colc': 1333, 'cold': 14444},
                '41111': {'colb': 42222, 'colc': 43333, 'cold': 44444},
                'item1': {'colb': 'item2', 'colc': 'item3', 'cold': 'item4'},
                'item13': {'colb': 'item14', 'colc': 'item15', 'cold':
                           'item16'},
                'item5': {'colb': 'item6', 'colc': 'item7', 'cold': 'item8'},
                'item9': {'colb': 'item10', 'colc': 'item11', 'cold': 'item12'}
            },
            'table5': {
                'r1': {'col1': 1, 'col2': 2, 'col3': 3, 'col4': 4},
                'r2': {'col1': 5, 'col2': 6, 'col3': 7, 'col4': 7},
                'r3': {'col1': 8, 'col2': 9, 'col3': 10, 'col4': 11}
            },
            'clomp': {
                'bestcase_omp': {
                    'coral2_rfp': 27.04, 'efficacy': '100%', 'overhead': 0.0,
                    'runtime': 0.517, 'speedup': 5.1, 'us_loop': 5.29},
                'dynamic_omp': {
                    'coral2_rfp': 5.1, 'efficacy': '3.2%', 'overhead': 162.56,
                    'runtime': 16.392, 'speedup': 0.2, 'us_loop': 167.85},
                'manual_omp': {
                    'coral2_rfp': 18.72, 'efficacy': '22.2%', 'overhead': 18.5,
                    'runtime': 2.324, 'speedup': 1.1, 'us_loop': 23.79},
                'omp_barrier': {
                    'coral2_rfp': 1.0, 'efficacy': 'N/A', 'overhead': 'N/A',
                    'runtime': 0.919, 'speedup': 'N/A', 'us_loop': 9.41},
                'scaled_serial_ref': {
                    'coral2_rfp': 27.04, 'efficacy': 'N/A', 'overhead': 'N/A',
                    'runtime': 2.641, 'speedup': 1.0, 'us_loop': 27.04},
                'static_omp': {
                    'coral2_rfp': 9.41, 'efficacy': '22.0%', 'overhead': 18.72,
                    'runtime': 2.345, 'speedup': 1.1, 'us_loop': 24.01},
                'calc_deposit': {
                    'coral2_rfp': '4 -1 256 10 32 1 100', 'efficacy': 'N/A',
                    'overhead': 'N/A', 'runtime': 0.0, 'speedup': 'N/A',
                    'us_loop': 0.0},
            },
            'mdtest': {
                'directory_creation': {
                    'max': 56142.185, 'min': 51275.966, 'mean': 53720.139, 'std_dev': 1507.151},
                'directory_stat': {
                    'max': 82058.105, 'min': 73594.508, 'mean': 78318.159, 'std_dev': 2463.194},
                'directory_removal': {
                    'max': 60147.14, 'min': 38256.728, 'mean': 54513.053, 'std_dev': 8174.081},
                'file_creation': {
                    'max': 34165.337, 'min': 23620.775, 'mean': 31777.61, 'std_dev': 2874.459},
                'file_stat': {
                    'max': 35447.875, 'min': 16235.606, 'mean': 30449.403, 'std_dev': 6233.127},
                'file_read': {
                    'max': 44255.713, 'min': 40119.544, 'mean': 41821.671, 'std_dev': 1302.742},
                'file_removal': {
                    'max': 51791.173, 'min': 48547.479, 'mean': 50687.506, 'std_dev': 1104.267},
                'tree_creation': {
                    'max': 3394.929, 'min': 1559.637, 'mean': 2944.616, 'std_dev': 505.474},
                'tree_removal': {
                    'max': 1684.514, 'min': 1092.882, 'mean': 1483.38, 'std_dev': 171.119}
            },

        }

        test = self._quick_test(cfg, 'table_test')
        test.run()

        log_file = (test.path / 'results.log').open('w')
        results = test.gather_results(0, log_file=log_file)

        for key in expected:
            self.assertEqual(expected[key], results[key],
                             msg="Table {} doesn't match results.".format(key))

    def test_evaluate(self):

        ordered = OrderedDict()
        ordered['Val_a'] = '3'
        ordered['val_b'] = 'Val_a + 1'

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
            ({'Val_a': '3',
              'val_b': 'Val_a + val_c',
              'val_c': 'Val_a*2'},
             {'Val_a': 3, 'val_b': 9, 'val_c': 6}),

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

            with self.assertRaises(pavilion.errors.ResultError):
                result.evaluate_results({}, error_conf, utils.IndentedLog())

    def test_result_command(self):
        """Make sure the result command works as expected, including the
        re-run option."""

        arg_parser = arguments.get_parser()

        result_cmd = commands.get_command('result')
        result_cmd.silence()
        run_cmd = commands.get_command('run')
        run_cmd.silence()

        # We need to alter the config path for these, but those paths need
        # to be processed first.
        tmp_cfg = config.make_config({
            'config_dirs': [
                self.PAV_LIB_DIR,
                self.PAV_ROOT_DIR/'test/data/configs-rerun',
            ]})
        rerun_cfg = self.pav_cfg.copy()
        rerun_cfg['configs'] = tmp_cfg['configs']
        rerun_cfg['config_dirs'] = tmp_cfg['config_dirs']

        run_args = arg_parser.parse_args(['run', 'result_tests'])
        if run_cmd.run(self.pav_cfg, run_args) != 0:
            cmd_out, cmd_err = run_cmd.clear_output()
            self.fail("Run command failed: \n{}\n{}".format(cmd_out, cmd_err))

        for test in run_cmd.last_tests:
            test.wait(10)

        res_args = arg_parser.parse_args(
            ('result', '--full') + tuple(t.full_id for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        res_args = arg_parser.parse_args(
            ('result',) + tuple(t.full_id for t in run_cmd.last_tests))
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
            tuple(t.full_id for t in run_cmd.last_tests))
        result_cmd.run(rerun_cfg, res_args)

        data, err = result_cmd.clear_output()
        results = json.loads(data)
        results = {res['name']: res for res in results}

        basic = results['result_tests.basic']
        per1 = results['result_tests.permuted.1']
        per2 = results['result_tests.permuted.2']

        self.assertEqual(basic['result'], TestRun.PASS,
                         msg="Test did not produce the expected result.")
        self.assertEqual(per1['result'], TestRun.FAIL)
        self.assertEqual(per2['result'], TestRun.PASS)

        # Make sure we didn't save any of the changes.
        orig_test = run_cmd.last_tests[0]
        reloaded_test = TestRun.load(self.pav_cfg, orig_test.working_dir,
                                     orig_test.id)
        self.assertEqual(reloaded_test.results, orig_test.results)
        self.assertEqual(reloaded_test.config, orig_test.config)

        # Make sure the log argument doesn't blow up.
        res_args = arg_parser.parse_args(
            ('result', '--show-log') + (run_cmd.last_tests[0].full_id,))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        result_cmd.clear_output()

        # Make sure re-running results works even with a bad test.
        test_cfg = self._quick_test_cfg()
        test_cfg['build']['cmds'] = ['false']
        bad_test = self._quick_test(test_cfg)
        res_args = arg_parser.parse_args(
            ('result', '--re-run', bad_test.full_id))
        self.assertEqual(result_cmd.run(self.pav_cfg, res_args), 0)
        out, err = result_cmd.clear_output()
        self.assertIn(bad_test.full_id, err)

    def test_result_cmd_all_passed(self):
        """Check that the '--all-passed' option works."""

        arg_parser = arguments.get_parser()
        rslts_cmd = commands.get_command('result')
        rslts_cmd.silence()

        good = self._quick_test()
        rslts = good.gather_results(good.run())
        good.save_results(rslts)

        bad_cfg = self._quick_test_cfg()
        bad_cfg['run']['cmds'] = ['exit 1']
        bad_run = self._quick_test(bad_cfg)
        rslts = bad_run.gather_results(bad_run.run())
        bad_run.save_results(rslts)

        bad_build_cfg = self._quick_test_cfg()
        bad_build_cfg['build']['cmds'] = ['exit 1']
        bad_build = self._quick_test(bad_build_cfg)

        bad_rslts_cfg = self._quick_test_cfg()
        bad_rslts_cfg['result_evaluate']['foo'] = 'does_not_exist'
        bad_rslts = self._quick_test(bad_rslts_cfg)
        rslts = bad_rslts.gather_results(bad_rslts.run())
        bad_rslts.save_results(rslts)

        args = arg_parser.parse_args(['result', '--all-passed', good.full_id])
        self.assertEqual(rslts_cmd.run(self.pav_cfg, args), 0)

        args = arg_parser.parse_args(['result', '--all-passed', good.full_id, bad_run.full_id])
        self.assertEqual(rslts_cmd.run(self.pav_cfg, args), 1)

        args = arg_parser.parse_args(['result', '--all-passed', good.full_id, bad_build.full_id])
        self.assertEqual(rslts_cmd.run(self.pav_cfg, args), 1)

        args = arg_parser.parse_args(['result', '--all-passed', good.full_id, bad_rslts.full_id])
        self.assertEqual(rslts_cmd.run(self.pav_cfg, args), 1)

    def test_re_search(self):
        """Check basic re functionality."""

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

    def test_constant_parser(self):
        """Check the constant parser."""

        cfg = self._quick_test_cfg()
        cfg['variables'] = {
            'foo': ['bar']
        }
        cfg['result_parse'] = {
            'constant': {
                'foo': {
                    'const': '{{foo}}',
                },
                'baz': {
                    'const': '33',
                }
            }
        }

        expected = {
            'foo': 'bar',
            'baz': 33,
        }

        test = self._quick_test(cfg, 'const_parser_test')
        test.run()
        results = test.gather_results(0)

        for key in expected:
            self.assertEqual(results[key], expected[key])

    def test_forced_parser_defaults(self):
        """Make sure we honor the result parser's FORCED_DEFAULTS."""

        cfg = self._quick_test_cfg()
        cfg['result_parse'] = {
            'constant': {
                'foo': {
                    'const': 'bar',
                    'preceded_by': 'unsettable',
                }
            }
        }

        with self.assertRaises(pavilion.errors.ResultError):
            result.check_config(cfg['result_parse'], {})

        test = self._quick_test(cfg, 'split_test')
        test.run()
        results = test.gather_results(0)

        self.assertTrue(results[result.RESULT_ERRORS][0].endswith(
            "This parser requires that you not set the 'preceded_by' key, as "
            "the default value is the only valid option."
        ))

    def test_split_parser(self):
        """Check the split parser."""

        cfg = self._quick_test_cfg()

        cfg['run']['cmds'] = [
            'echo "Results1"',
            'echo " 1 1.2       hello "',
            'echo "Results2"',
            'echo "1, 3, 5, 9, blarg, 11"',
        ]

        cfg['result_parse'] = {
            'split': {
                'a1,b1,c1': {
                    'preceded_by': [r'Results1']
                },
                'a2, _, _, _, b2':      {
                    'sep': ',',
                    'preceded_by':        [r'Results2'],
                },
            }
        }

        expected = {
            'a1': 1,
            'b1': 1.2,
            'c1': 'hello',
            'a2': 1,
            'b2': 'blarg',
        }

        test = self._quick_test(cfg, 'split_test')
        test.run()
        results = test.gather_results(0)

        for key in expected:
            self.assertEqual(results[key], expected[key])

    def test_flatten_results(self):
        """Make sure result flattening works as expected, as well as regular
        result output while we're at it."""

        cfg = self._quick_test_cfg()

        cfg['run']['cmds'] = [
            'for i in 1 2 3 4; do echo "hello $i" > $i.out; done'
        ]
        cfg['result_parse']['regex'] = {
            'hello': {
                'regex':    r'hello \d+',
                'files':    '*.out',
                'per_file': 'name',
            }
        }

        test = self._quick_test(cfg, name="flatten_results_test1")

        run_result = test.run()
        results = test.gather_results(run_result)
        test.save_results(results)

        flattened = {}

        test2 = self._quick_test(cfg, name="flatten_results_test2")
        run_result = test2.run()
        results = test2.gather_results(run_result)
        test2._pav_cfg = test2._pav_cfg.copy()
        test2._pav_cfg['flatten_results'] = False
        test2.save_results(results)

        with self.pav_cfg['result_log'].open() as results_log:
            for line in results_log.readlines():
                _result = json.loads(line)

                # Reconstruct the per_file dict, so that flattened and
                # unflattened are the same. If there's a format error, this
                # will have problems.
                if _result['name'] == "unittest.flatten_results_test1":
                    flattened[_result['file']] = {'hello': _result['hello']}
                elif _result['name'] == "unittest.flatten_results_test2":
                    unflattened = _result['per_file']

        answer = {
            '1': {'hello': 'hello 1'},
            '2': {'hello': 'hello 2'},
            '3': {'hello': 'hello 3'},
            '4': {'hello': 'hello 4'},
        }

        self.assertEqual(flattened, answer)
        self.assertEqual(unflattened, answer)
