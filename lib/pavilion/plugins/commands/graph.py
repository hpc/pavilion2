import errno
import matplotlib.pyplot as plt
import numpy as np
import os
import re
from datetime import datetime

from pavilion import commands
from pavilion import output
from pavilion import series
from pavilion.result import evaluations
from pavilion.status_file import STATES
from pavilion.test_run import TestRun


class GraphCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'graph',
            'Command used to produce graph for a group of tests.',
            short_help="Produce graph for tests."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '--exclude', nargs='*', default=[],
            help='Exclude tests, series, sys_names, test_names, '
                 'or users by providing specific IDs or names.'
        ),
        parser.add_argument(
            '--test_name', action='store', default=False,
            help='Filter tests by test_name.'
        ),
        parser.add_argument(
            '--sys_name', action='store', default=False,
            help='Filter tests by sys_name.'
        ),
        parser.add_argument(
            '--user', action='store', default=False,
            help='Filter tests by user.'
        ),
        parser.add_argument(
            '--date', action='store', default=False,
            help='Filter tests by date.'
        ),
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The names of the tests to graph'
        ),
        parser.add_argument(
            '--y', nargs='+', action='store',
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        ),
        parser.add_argument(
            '--x', nargs=1, action='store',
            help='Specify the value to be used on the X axis.'
        ),
        parser.add_argument(
            '--x_label', action='store', default="",
            help='Specify the x axis label.'
        ),
        parser.add_argument(
            '--y_label', action='store', default="",
            help='Specify the y axis label.'
        )

    def run(self, pav_cfg, args):

        # Validate Arguments.
        result = self.validate_args(args)
        if result:
            return result

        # Expand series, convert test_ids (if provided). 
        args.tests = self.normalize_args_tests(pav_cfg, args.tests)

        # Check filters, append/remove tests.
        tests = self.filter_tests(pav_cfg, args, args.tests)
        if not tests:
            output.fprint("No completed, successful tests matched these filters.")
            return errno.EINVAL

        evals = self.build_evaluations_dict(args.x, args.y)
        for test in tests:

            x_data, y_data = self.get_data(evals, test.results)

            # Plot this test.
            for y_val, arg in zip(y_data, args.y):
                plt.plot(x_data, y_val, 'o', label = arg) # label = arg eventually.

        plt.ylabel(args.y_label)
        plt.xlabel(args.x_label)
        plt.legend()
        plt.show()

    def validate_args(self, args):

        # Validate Date.
        if args.date:
            try:
                args.date = datetime.strptime(args.date, '%b %d %Y')
            except ValueError as err:
                output.fprint("{} is not a valid date "
                              "format: {}".format(args.date, err))
                return errno.EINVAL

        if not args.x:
            output.fprint("No value was given to graph on x-axis. Use --x "
                          "flag to specify.")
        if not args.y:
            output.fprint("No values were given to graph on y-axis. Use --y "
                          "flag to specify.")
        if not args.x or not args.y:
            return errno.EINVAL


    def build_evaluations_dict(self, x_eval, y_eval):

        evals = {}
        evals['x'] = x_eval[0]
        for i in range(len(y_eval)):
            evals['y'+str(i)] = y_eval[i]

        return evals

    def expand_ranges(self, test_list):

        updated_test_list = []
        for test in test_list:
            if '-' in test:
                lower, higher = test.split('-')
                if lower.startswith('s') and higher.startswith('s'):
                    range_list = range(int(lower.strip('s')),
                                       int(higher.strip('s'))+1)
                    updated_test_list.extend(['s'+str(x) for x in range_list])
                else:
                    range_list = range(int(lower), int(higher)+1)
                    updated_test_list.extend([str(x) for x in range_list])
            else:
                updated_test_list.append(test)

        return updated_test_list

    def normalize_args_tests(self, pav_cfg, test_list):

        if not test_list:
            return []

        test_list = self.expand_ranges(test_list)

        normalized_test_list = []
        for test in test_list:
            # Normalize test string to appear as it would in test_runs dir.
            if not test.startswith('s'):
                normalized_test_list.append(test.zfill(7))
            # If series, expand and normalize
            else:
                for s_test in series.TestSeries.from_id(pav_cfg,
                                                        test).tests:
                    normalized_test_list.append(str(s_test).zfill(7))

        return normalized_test_list

    def filter_tests(self, pav_cfg, args, tests):

        tests_dir = pav_cfg.working_dir / 'test_runs'
        test_list = []
        # Filter All Tests.
        if not tests:
            for test_path in tests_dir.iterdir():
                test = self.apply_filters(pav_cfg, args, test_path)
                if test is None:
                    continue
                test_list.append(test)

        # Filter provided list of tests.
        else:
            for test_id in tests:
                test_path = tests_dir / test_id
                test = self.apply_filters(pav_cfg, args, test_path)
                if test is None:
                    continue
                test_list.append(test)

        return test_list

    def apply_filters(self, pav_cfg, args, test_path):

        # Make sure given path is a directory.
        if not test_path.is_dir():
            return None

        if test_path.name in args.exclude:
            return None

        # Filter tests by date.
        if args.date:
            test_date = datetime.fromtimestamp(test_path.stat().st_ctime)
            if test_date.date() != args.date.date():
                return None

        # Filter tests by user.
        owner = test_path.owner()
        if args.user and owner not in args.user:
            return None
        if owner in args.exclude:
            return None

        # Load Test Object, to check Host name and Test Name
        test = TestRun.load(pav_cfg, int(test_path.name))

        # Ensure test has completed, and successfully run.
        status = test.status.current()
        if status.state != STATES.COMPLETE:
            return None

        host = test.config.get('host')
        # Filter tests by test name.
        if args.test_name and test.name not in args.test_name:
            return None
        if test.name in args.exclude:
            return None

        # Filter tests by sys name.
        if args.sys_name and host not in args.sys_name:
            return None
        if host in args.exclude:
            return None

        return test

    def get_data(self, evals, results):

        evaluations.evaluate_results(results, evals)

        x_data = results['x']
        y_data_list = []

        for key in evals:
            if key is 'x':
                continue
            else:
                y_data_list.append(results[key])

        return x_data, y_data_list
