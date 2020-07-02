import matplotlib.pyplot as plt
import numpy as np
import os
import re
from datetime import datetime

from pavilion import commands
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
            help='Filter tests to graph by test_name.'
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

        tests_dir = pav_cfg.working_dir / 'test_runs'

        # No tests provided, check filters, append tests.
        if not args.tests:
            for test_path in tests_dir.iterdir():
                if not test_path.is_dir():
                    continue
                # Filter excluded test ids.
                if test_path.name.strip('0') in args.exclude:
                   continue
                # Filter tests by date.
                if args.date:
                    pass
                # Filter tests by user.
                owner = test_path.owner()
                if owner in args.exclude:
                    continue
                if args.user and owner not in args.user:
                    continue
                args.tests.append(test_path.name)

        test_list = []
        for test_id in args.tests:
            # Expand series provided, as long as it wasn't meant to be excluded.
            if test_id.startswith('s'):
                if test_id in args.exclude:
                    continue
                else:
                    test_list.extend(series.TestSeries.from_id(pav_cfg,
                                                               test_id).tests)
            else:
                test_list.append(int(test_id))

        test_objects = []
        for test_id in test_list:
            test = TestRun.load(pav_cfg, test_id)
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
            test_objects.append(test)

        # All tests should be filtered at this point.

        KEYS_RE = re.compile(r'keys\((.*)\)')

        for test in test_objects:
            y_data_list = []
            x_data = []
            if 'keys' in args.x[0]:
                arg = KEYS_RE.match(args.x[0]).groups()[0]
                r = test.results.get(arg)
                # Get X Values.
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
                x_data.append(float(test.results.get(args.x[0])))
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
