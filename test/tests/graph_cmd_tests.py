import errno

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class ResolverTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        self.graph_cmd = commands.get_command('graph')

    def tearDown(self):
        plugins._reset_plugins()

    def test_expand_ranges(self):
        """Make sure test ranges get expanded correctly."""

        test_list = ['167-170']
        test_list = self.graph_cmd.expand_ranges(test_list)

        self.assertEqual(test_list, ['167', '168', '169', '170'])

        test_list = ['s123-s125']
        test_list = self.graph_cmd.expand_ranges(test_list)

        self.assertEqual(test_list, ['s123', 's124', 's125'])

    def test_arg_validation(self):
        """Make sure arguments get validated correctly, and catch the right
        errors."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--date', 'July 13 2020',
            '--x', 'cool',
            '--y', 'beans'
        ])

        self.assertEqual(self.graph_cmd.validate_args(args), errno.EINVAL)

        args = arg_parser.parse_args([
            'graph',
            '--date', 'Jul 13 2020',
            '--x', 'cool',
            '--y', 'beans'
        ])

        self.assertEqual(self.graph_cmd.validate_args(args), None)

        args = arg_parser.parse_args([
            'graph'
        ])

        self.assertEqual(self.graph_cmd.validate_args(args), errno.EINVAL)

    def test_build_evaluations_dict(self):
        """Make sure the evaluations dictionary is built correctly."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'cool',
            '--y', 'beans'
        ])

        evals_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)

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

        evals_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)

        expected = {
             'x': 'cool',
            'y0': 'beans',
            'y1': 'and',
            'y2': 'stuff'
        }

        for key in evals_dict.keys():
            self.assertEqual(evals_dict[key], expected[key])

    def test_normalize_test_args(self):
        """Make sure test normalization works as it is supposed to."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph', '123-126'
        ])

        test_list = self.graph_cmd.normalize_args_tests(self.pav_cfg,
                                                        args.tests)

        self.assertEqual(test_list, ['0000123', '0000124', '0000125',
                                     '0000126'])

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

        eval_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)
        eval_res = self.graph_cmd.evaluate_results(eval_dict, results)

        eval_expected = {
            235: [123424]
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of results.
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'id',
            '--y', 'Info.*'
        ])

        eval_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)
        eval_res = self.graph_cmd.evaluate_results(eval_dict, results)

        eval_expected = {
            235: [123424, 14214]
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
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read'
        ])

        eval_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)
        eval_res = self.graph_cmd.evaluate_results(eval_dict, results)

        eval_expected = {
            1: [123424],
            2: [124342123],
            3: [33523]
        }

        self.assertEqual(eval_res, eval_expected)

        # Get multiple values out of multiple keys in results.
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'graph',
            '--x', 'keys(Info)',
            '--y', 'Info.*.Read', 'Info.*.Write'
        ])

        eval_dict = self.graph_cmd.build_evaluations_dict(args.x, args.y)
        eval_res = self.graph_cmd.evaluate_results(eval_dict, results)

        eval_expected = {
            1: [123424, 14214],
            2: [124342123, 124],
            3: [33523, 2425]
        }

        self.assertEqual(eval_res, eval_expected)


