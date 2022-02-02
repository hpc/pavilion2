import unittest

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


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

    def test_get_graph_data(self):
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
            '-o', '/tmp/foo.png',
            '--x', 'id',
            '--y', 'Info.Read'
        ])

        graph_cmd = commands.get_command(args.command_name)
        graph_cmd.silence()

        x_eval = {'x': args.x}
        y_evals = {'y' + str(i): args.y[i] for i in range(len(args.y))}
        eval_res = graph_cmd.gather_graph_data(x_eval, y_evals, results)

        eval_expected = {
            235: {'y0': 123424}
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of results.
        args = arg_parser.parse_args([
            'graph',
            '-o', '/tmp/foo2.png',
            '--x', 'id',
            '--y', 'Info.*'
        ])

        x_eval = {'x': args.x}
        y_evals = {'y' + str(i): args.y[i] for i in range(len(args.y))}
        eval_res = graph_cmd.gather_graph_data(x_eval, y_evals, results)

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
            '-o', '/tmp/foo3.png',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read'
        ])

        x_eval = {'x': args.x}
        y_evals = {'y' + str(i): args.y[i] for i in range(len(args.y))}
        eval_res = graph_cmd.gather_graph_data(x_eval, y_evals, results)

        eval_expected = {
            1: {'y0': 123424},
            2: {'y0': 124342123},
            3: {'y0': 33523}
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of multiple keys in results.
        args = arg_parser.parse_args([
            'graph',
            '-o', '/tmp/foo4.png',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read',
            '--y', 'Info.*.Write'
        ])

        x_eval = {'x': args.x}
        y_evals = {'y' + str(i): args.y[i] for i in range(len(args.y))}
        eval_res = graph_cmd.gather_graph_data(x_eval, y_evals, results)

        eval_expected = {
            1: {'y0': 123424, 'y1': 14214},
            2: {'y0': 124342123, 'y1': 124},
            3: {'y0': 33523, 'y1': 2425}
        }

        self.assertEqual(eval_res, eval_expected)

    def test_graph_cmd(self):
        """Test the full graph command."""

        cmd = commands.get_command('graph')
        cmd.silence()
        parser = arguments.get_parser()

        tests = [self._quick_test() for i in range(10)]
        for test in tests:
            test.run()
            test.gather_results(0)
            test.set_run_complete()

        args = parser.parse_args([
            'graph',
            '-o', '/tmp/foo.png',
            '--x', 'id',
            '--y', 'id',
        ] + [test.full_id for test in tests])

        cmd.run(self.pav_cfg, args)
