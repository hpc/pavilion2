import matplotlib.pyplot as plt
import numpy as np

from pavilion import commands


class GraphCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'graph',
            'Command used to produce graph for a group of tests.',
            short_help="Produce graph for tests."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '--exclude', nargs='*',
            help='Excludes tests and tests series, must provide '
                 'specific IDs.'
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
            'values', nargs='+', action='store',
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        ),
        parser.add_argument(
            'Xaxis', nargs=1, action='store',
            help='Specify the X axis.'
        )
    def run(self, pav_cfg, args):

        print(args)

