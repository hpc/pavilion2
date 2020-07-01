import matplotlib.pyplot as plt
import numpy as np
import os

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
            '--y', nargs='+', action='store',
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        ),
        parser.add_argument(
            '--x', nargs=1, action='store',
            help='Specify the value to be used on the X axis.'
        ),
        parser.add_argument(
            '--x_label', action='store', default=False,
            help='Specify the x axis label.'
        ),
        parser.add_argument(
            '--y_label', action='store', default=False,
            help='Specify the y axis label.'
        )
    def run(self, pav_cfg, args):

        print(args)
        pass

