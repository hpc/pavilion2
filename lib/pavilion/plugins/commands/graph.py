import errno
import matplotlib.pyplot as plt
import numpy as np
import os
import re
from datetime import datetime

from pavilion import commands
from pavilion import output
from pavilion import series
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

        # A list of tests or series was provided.
        if args.tests:
            args.tests = self.normalize_args_tests(pav_cfg, args.tests)

        # Check filters, append/remove tests.
        tests = self.filter_tests(pav_cfg, args, args.tests)
        if tests is None:
            output.fprint("No tests matched these filters.")
            return errno.EINVAL

        KEYS_RE = re.compile(r'keys\((.*)\)')
        for test in tests:
            y_data_list = []
            x_data = []
            if 'keys' in args.x[0]:
                arg = KEYS_RE.match(args.x[0]).groups()[0]
                r = test.results.get(arg)
                # Get X Values.
                if r is None:
                    output.fprint("{} does not exist in {}'s results."
                                  .format(arg, test.name))
                    return errno.EINVAL

                for elem in r.keys():
                    x_data.append(float(re.search(r'\d+',
                                              elem).group().strip('0')))
                # Get Y Values.
                for arg in args.y:
                    arg_data = []
                    for elem in r.keys():
                        elem_dict = r.get(elem)
                        for key in arg.split("."):
                            elem_dict = elem_dict[key]
                        arg_data.append(float(elem_dict))
                    y_data_list.append(arg_data)

            else:
                result = test.results.get(args.x[0])
                if result is None:
                    output.fprint("{} does not exist in {}'s "
                                  "results.".format(args.x[0]. test.name))
                    return errno.EINVAL

                x_data.append(float(result))
                for arg in args.y:
                    elem_dict = test.results
                    for key in arg.split("."):
                        elem_dict = elem_dict[key]
                    y_data_list.append(float(elem_dict))

            for y_data, arg in zip(y_data_list, args.y):
                plt.plot(x_data, y_data, 'o') # label = arg eventually.

        plt.ylabel(args.y_label)
        plt.xlabel(args.x_label)
        plt.legend()
        plt.show()

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

        # Validate date filter, if provided.
        if args.date:
            try:
                date = datetime.strptime(args.date, '%b %d %Y')
            except ValueError as err:
                output.fprint("{} is not a valid date "
                              "format: {}".format(args.date, err))
                return errno.EINVAL

        tests_dir = pav_cfg.working_dir / 'test_runs'
        test_list = []
        # Filter Tests
        for test_path in tests_dir.iterdir():
            if not test_path.is_dir():
                continue

            # Tests were provided, check additonal filters on those only.
            if tests and test_path.name not in tests:
                continue
            if test_path.name in args.exclude:
                continue

            # Filter tests by date.
            if args.date:
                test_date = datetime.fromtimestamp(test_path.stat().st_ctime)
                if test_date.date() != date.date():
                    continue

            # Filter tests by user.
            owner = test_path.owner()
            if owner in args.exclude:
                continue
            if args.user and owner not in args.user:
                continue

            # Load Test Object, to check Host name and Test Name
            test = TestRun.load(pav_cfg, int(test_path.name))

            host = test.config.get('host')
            # Filter tests by test name.
            if args.test_name and test.name not in args.test_name:
                continue
            if test.name in args.exclude:
                continue

            # Filter tests by sys name.
            if args.sys_name and host not in args.sys_name:
                continue
            if host in args.exclude:
                continue

            test_list.append(test)

        return test_list

