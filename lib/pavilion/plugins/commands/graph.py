import errno
from datetime import datetime
from typing import Dict

from pavilion import cmd_utils
from pavilion import commands
from pavilion import filters
from pavilion import output
from pavilion.commands import Command, CommandError
from pavilion.result.evaluations import check_evaluations, evaluate_results
from pavilion.result.base import ResultError
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

        filters.add_test_filter_args(parser)

        parser.add_argument(
            'tests', nargs='*', action='store',
            help='Specific Test Ids to graph.'
        )

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
            '--xlabel', action='store', default="",
            help='Specify the x axis label.'
        ),
        parser.add_argument(
            '--ylabel', action='store', default="",
            help='Specify the y axis label.'
        ),

    def run(self, pav_cfg, args):

        try:
            import matplotlib.pyplot
        except ImportError:
            output.fprint("matplotlib not found.", color=output.RED)
            return errno.EINVAL

        try:
            self.validate_args(args)
        except CommandError as err:
            output.fprint("Invalid command arguments: \n{}".format(err),
                          color=output.RED)
            return errno.EINVAL

        # Get filtered Test IDs, and then load TestRun objects.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)
        tests = [TestRun.load(pav_cfg, test_id) for test_id in test_ids]

        if not tests:
            output.fprint("Test filtering resulted in an empty list.")
            return errno.EINVAL

        evaluations = self.build_evaluations_dict(args.x, args.y)

        colormap = matplotlib.pyplot.get_cmap('Accent')
        colormap = self.set_colors(evaluations, colormap.colors)

        for test in tests:
            try:
                results = self.gather_results(evaluations, test.results)
            except ResultError as err:
                output.fprint("Error while gathering results: \n{}"
                              .format(err))
                return errno.EINVAL
            print(results)
            for key, values in results.items():
                for evl, value in values.items():
                    color = colormap[evl]
                    if isinstance(value, list):
                        for item in value:
                            matplotlib.pyplot.plot(key, item, marker="o",
                                                   color=color,
                                                   label=evaluations[evl])

                    else:
                        matplotlib.pyplot.plot(key, value, marker="o",
                                               color=color,
                                               label=evaluations[evl])

        matplotlib.pyplot.ylabel(args.ylabel)
        matplotlib.pyplot.xlabel(args.xlabel)
        handles, labels = matplotlib.pyplot.gca().get_legend_handles_labels()
        labels = list(dict.fromkeys(labels))
        matplotlib.pyplot.legend(handles, labels)
        matplotlib.pyplot.show()

    def gather_results(self, evaluations, test_results) -> Dict:
        """
        Gather and format a test run objects results.
        :param evaluations: The evaluations dictionary to be used to gather
               results.
        :param test_results: A test run's result dictionary.
        :return: result, a dictionary containing parsed/formatted results for
                 the given test run.
        """
        evaluate_results(test_results, evaluations)

        if isinstance(test_results['x'], list):
            results = {}
            for i in range(len(test_results['x'])):
                evals = {}
                for key in evaluations.keys():
                    if key == 'x':
                        continue
                    evals.update({key: test_results[key][i]})
                results[test_results['x'][i]] = evals

        else:
            results = {}
            evals = {}
            for key in evaluations.keys():
                if key == 'x':
                    continue
                evals.update({key: test_results[key]})
            results[test_results['x']] = evals

        return results

    def validate_args(self, args) -> None:
        """
        Validate command arguments.
        :param args: the passed args parse object.
        :return:
        """

        if not args.x:
            raise CommandError("No value was given to graph on X-axis. Use "
                               "'--x' flag to specify.")
        if not args.y:
            raise CommandError("No values were given to graph on y-axis. "
                               "Use '--y' flag to specify.")

    def build_evaluations_dict(self, x_eval, y_eval) -> Dict:
        """
        Take the parsed command arguments for --x and  --y and build an
        evaluations dictionary to be used later for gathering results.
        :param x_eval: List of evaluation string for x value.
        :param y_eval: List of evaluation string for y values.
        :return: A dictionary to be used with pavilion's evaluations module.
        """

        evaluations = dict()
        evaluations['x'] = x_eval[0]
        for i in range(len(y_eval)):
            evaluations['y'+str(i)] = y_eval[i]

        check_evaluations(evaluations)

        return evaluations

    def set_colors(self, evaluations, colors):
        """
        Set color for each y value to be plotted.
        :param evaluations: evaluations dictionary.
        :param colors: Tuple of colors from a matplotlib color map.
        :return: A dictionary with color lookups, by y value.
        """

        colormap = {}
        colors = [color for color in colors]

        for key in evaluations.keys():
            if key == 'x':
                continue
            colormap[key] = colors.pop()

        return colormap
