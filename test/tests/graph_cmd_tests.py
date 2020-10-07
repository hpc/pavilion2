import errno
import unittest

from pavilion import arguments
from pavilion import commands
from pavilion import output
from pavilion import plugins
from pavilion.unittest import PavTestCase
from pavilion.result.base import ResultError
from pavilion.plugins.commands.graph import ResultTypeError


def has_matplotlib():
    try:
        import matplotlib
    except ImportError:
        return False

    return True


class ResolverTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @unittest.skipIf(not has_matplotlib(), "matplotlib not found.")
    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_arg_validation(self):
        """Make sure arguments get validated correctly, and catch the right
        errors."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'cool',
            '--y', 'beans'
        ])

        graph_cmd = commands.get_command(args.command_name)
        graph_cmd.silence()

        self.assertEqual(graph_cmd.validate_args(args), None)

        args = arg_parser.parse_args([
            'graph'
        ])

        graph_cmd = commands.get_command(args.command_name)
        graph_cmd.silence()

        self.assertEqual(graph_cmd.run(self.pav_cfg, args), errno.EINVAL)

    def test_build_evaluations_dict(self):
        """Make sure the evaluations dictionary is built correctly."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'cool',
            '--y', 'beans'
        ])

        graph_cmd = commands.get_command(args.command_name)
        graph_cmd.silence()

        evals_dict, _ = graph_cmd.build_dicts(args.x, args.y)

        expected = {
             'x': 'cool',
             'y0': 'beans'
        }

        for key in evals_dict.keys():
            self.assertEqual(evals_dict[key], expected[key])

        args = arg_parser.parse_args([
            'graph',
            '--x', 'cool',
            '--y', 'beans', 'and', 'stuff'
        ])

        evals_dict, _ = graph_cmd.build_dicts(args.x, args.y)

        expected = {
             'x': 'cool',
             'y0': 'beans',
             'y1': 'and',
             'y2': 'stuff'
        }

        for key in evals_dict.keys():
            self.assertEqual(evals_dict[key], expected[key])

    def test_get_data(self):
        """Make sure data is pulled out of the test results and returned as
        expected."""

        results = {
            'test': 'Test1',
            'result': 'PASS',
            'Info': {
                'Read': 123424,
                'Write': 14214
            },
            'id': 235
        }

        # Get a single value out of results.
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'id',
            '--y', 'Info.Read'
        ])

        graph_cmd = commands.get_command(args.command_name)
        graph_cmd.silence()

        eval_dict, _ = graph_cmd.build_dicts(args.x, args.y)
        eval_res = graph_cmd.gather_results(eval_dict, results)

        eval_expected = {
            235: {'y0': 123424}
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of results.
        args = arg_parser.parse_args([
            'graph',
            '--x', 'id',
            '--y', 'Info.*'
        ])

        eval_dict, _ = graph_cmd.build_dicts(args.x, args.y)
        eval_res = graph_cmd.gather_results(eval_dict, results)

        eval_expected = {
            235: {'y0': [123424, 14214]}
        }

        self.assertEqual(eval_res, eval_expected)

        results = {
            'test': 'Test1',
            'result': 'PASS',
            'Info': {
                1: {
                    'Read': 123424,
                    'Write': 14214
                },
                2: {
                    'Read': 124342123,
                    'Write': 124
                },
                3: {
                    'Read': 33523,
                    'Write': 2425
                }
            },
            'id': 235
        }

        # Get a single value out of multiple keys in results.
        args = arg_parser.parse_args([
            'graph',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read'
        ])

        eval_dict, _ = graph_cmd.build_dicts(args.x, args.y)
        eval_res = graph_cmd.gather_results(eval_dict, results)

        eval_expected = {
            1: {'y0': 123424},
            2: {'y0': 124342123},
            3: {'y0': 33523}
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of multiple keys in results.
        args = arg_parser.parse_args([
            'graph',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read', 'Info.*.Write'
        ])

        eval_dict, _ = graph_cmd.build_dicts(args.x, args.y)
        eval_res = graph_cmd.gather_results(eval_dict, results)

        eval_expected = {
            1: {'y0': 123424, 'y1': 14214},
            2: {'y0': 124342123, 'y1': 124},
            3: {'y0': 33523, 'y1': 2425}
        }

        self.assertEqual(eval_res, eval_expected)
