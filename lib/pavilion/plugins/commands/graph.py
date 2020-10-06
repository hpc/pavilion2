import errno
import re
import statistics
from datetime import datetime
from typing import Dict
import itertools

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
            '--exclude', nargs='*', default=[], action='store',
            help='Exclude Test Ids from the graph.'
        )
        parser.add_argument(
            '--y', nargs='+', action='store',
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        )
        parser.add_argument(
            '--x', nargs=1, action='store',
            help='Specify the value to be used on the X axis.'
        )
        parser.add_argument(
            '--xlabel', action='store', default="",
            help='Specify the x axis label.'
        )
        parser.add_argument(
            '--ylabel', action='store', default="",
            help='Specify the y axis label.'
        )
        parser.add_argument(
            '--plot-average', nargs='+', action='store', default=[],
            help='Generate an average plot for the specified x value(s).'
        )

    def run(self, pav_cfg, args):

        try:
            import matplotlib.pyplot
            matplotlib.pyplot.ioff()
        except ImportError as err:
            output.fprint("Error importing matplotlib: {}".format(err),
                          color=output.RED)
            return errno.EINVAL

        try:
            self.validate_args(args)
        except CommandError as err:
            output.fprint("Invalid command arguments:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL
        except ValueError as err:
            output.fprint("Invalid '--exclude' argument:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL

        # Get filtered Test IDs.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)

        # Load TestRun for all tests, skip those that are to be excluded.
        tests = [TestRun.load(pav_cfg, test_id) for test_id in test_ids
                 if test_id not in args.exclude]

        if not tests:
            output.fprint("Test filtering resulted in an empty list.")
            return errno.EINVAL

        evaluations, stats_dict = self.build_dicts(args.x, args.y)

        colormap = matplotlib.pyplot.get_cmap('tab20')
        colormap = self.set_colors(evaluations, colormap.colors)

        results = {}
        for test in tests:
            try:
                test_results = self.gather_results(evaluations, test.results)
            except ResultError as err:
                output.fprint("Error gathering results for test {}: \n{}"
                              .format(test.id, err))
                return errno.EINVAL

            results = self.update_results_dict(results, test_results)

        labels = set()
        for x, eval_dict in results.items():
            for evl, y_list in eval_dict.items():
                color = colormap[evl]['plot']

                label = evaluations[evl].split(".")[0]
                label = label if label not in labels else ""
                labels.add(label)

                x_list = [x] * len(y_list)

                matplotlib.pyplot.scatter(x=x_list, y=y_list, marker=".",
                                          color=color,
                                          label=label)

                if evaluations[evl] in args.plot_average:
                    stats_dict[evl]['x'].append(x)
                    stats_dict[evl]['y'].append(statistics.mean(y_list))

        for evl, values in stats_dict.items():
            if evaluations[evl] not in args.plot_average:
                continue
            xs, ys = zip(*sorted(zip(values['x'], values['y'])))
            label = evaluations[evl].split(".")[0]
            matplotlib.pyplot.scatter(xs, ys, marker="+",
                                      color=colormap[evl]['stat'],
                                      label="average({})".format(label))

        matplotlib.pyplot.ylabel(args.ylabel)
        matplotlib.pyplot.xlabel(args.xlabel)

        matplotlib.pyplot.legend()
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

        # X value evaluations should only result in a list when graphing
        # individual node results in a single test run.
        if isinstance(test_results['x'], list):
            results = {}
            for i in range(len(test_results['x'])):
                evals = {}
                for key in evaluations.keys():
                    if key == 'x':
                        continue
                    evals.update({key: test_results[key][i]})

                node = re.match(r'[a-zA-Z]*(\d*)$', test_results['x'][i])
                node = int(node.groups()[0])
                results[node] = evals

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

        # Convert test exclude args into integers
        args.exclude = [int(test) for test in args.exclude]

    def build_dicts(self, x_eval, y_eval) -> (Dict, Dict):
        """
        Take the parsed command arguments for --x and  --y and build an
        evaluations dictionary to be used later for gathering results.
        Additionally, build a statistics dict based on evaluations dict.
        :param x_eval: List of evaluation string for x value.
        :param y_eval: List of evaluation string for y values.
        :return: A dictionary to be used with pavilion's evaluations module.
        """

        evaluations = dict()
        stats_dict = dict()
        evaluations['x'] = x_eval[0]
        for i in range(len(y_eval)):
            key = 'y'+str(i)
            evaluations[key] = y_eval[i]
            stats_dict.update({key: {'x': [], 'y': []}})

        check_evaluations(evaluations)

        return evaluations, stats_dict

    def set_colors(self, evaluations, colors) -> Dict:
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
            colormap[key] = {'plot': colors.pop(0), 'stat': colors.pop(0)}

        return colormap

    def update_results_dict(self, results, test_results) -> Dict:
        """
        Update results dictionary with the passed test run results. Will extend
        lists of values for the same x value and evaluation so they can be
        graphed in a single pass.
        :param results: Passed  pav graph results dict.
        :param test_results: Passed individual TestRun's results dict.
        :return: Updated results dict.
        """

        for key, values in test_results.items():
            if key not in results:
                results[key] = {}
            for evl, value in values.items():
                if evl not in results[key]:
                    results[key][evl] = []
                if isinstance(value, list):
                    results[key][evl].extend(value)
                else:
                    results[key][evl].extend([value])

        return results
