"""Graph pavilion results data."""

import errno
import re
import statistics
from typing import Dict

from pavilion import cmd_utils
from pavilion import commands
from pavilion import filters
from pavilion import output
from pavilion.commands import CommandError
from pavilion.result.base import ResultError
from pavilion.result.evaluations import check_evaluations, evaluate_results
from pavilion.test_run import TestRun, TestRunError


try:
    import matplotlib

    matplotlib.use('agg')
    import matplotlib.pyplot

    matplotlib.pyplot.ioff()

    HAS_MATPLOT_LIB = True

except ImportError:

    HAS_MATPLOT_LIB = False


class GraphCommand(commands.Command):
    """Command to graph Pavilion results data."""

    def __init__(self):
        super().__init__(
            'graph',
            'Command used to produce graph for a set of test results.',
            short_help="Produce a graph from a set of test results."
        )

    def _setup_arguments(self, parser):

        filters.add_test_filter_args(parser)

        parser.add_argument(
            'tests', nargs='*', action='store',
            help='Specific Test Ids to graph.'
        )
        parser.add_argument(
            '--filename', action='store', required=True,
            help='File name to use for saving graph.'
        )
        parser.add_argument(
            '--exclude', nargs='*', default=[], action='store',
            help='Exclude Test Ids from the graph.'
        )
        parser.add_argument(
            '--y', nargs='+', action='store', required=True,
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        )
        parser.add_argument(
            '--x', nargs=1, action='store', required=True,
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
        """"""

        if HAS_MATPLOT_LIB:
            output.fprint(
                "The command requires matplotlib to function. Matplotlib is an"
                "optional requirement of Pavilion.")

            return errno.EINVAL

        try:
            exclude = [int(test) for test in args.exclude]
        except ValueError as err:
            output.fprint(
                "Invalid '--exclude' test id:\n{}".format(err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL

        output.fprint("Generating Graph...", file=self.outfile)
        # Get filtered Test IDs.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)

        # Load TestRun for all tests, skip those that are to be excluded.
        tests = []
        for test_id in test_ids:
            if test_id in exclude:
                continue

            try:
                TestRun.load(pav_cfg, test_id)
            except TestRunError as err:
                output.fprint(
                    "Error loading test run {}. Use '--exclude' to stop "
                    "seeing this message.\n{}"
                    .format(test_id, err.args[0]),
                    color=output.YELLOW, file=self.errfile)

        if not tests:
            output.fprint("Test filtering resulted in an empty list.")
            return errno.EINVAL

        y_evals = {'y' + str(i): args.y for i in range(len(args.y))}
        stats_dict = {key: {'x': [], 'y': []} for key in y_evals}

        all_evals = y_evals.copy()
        all_evals['x'] = args.x
        try:
            check_evaluations(all_evals)
        except ResultError as err:
            output.fprint(
                "Invalid graph evaluation:\n{}".format(err.args[0]),
                file=self.errfile, color=output.RED)

        colormap = matplotlib.pyplot.get_cmap('tab20')
        colormap = self.set_colors(evaluations, colormap.colors)

        # Rename 'graph data' or something'
        results = {}
        for test in tests:
            try:
                test_results = self.gather_results(evaluations, test.results)
            except (ResultError, ResultTypeError) as err:
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

                try:
                    matplotlib.pyplot.scatter(x=x_list, y=y_list, marker=".",
                                              color=color,
                                              label=label)
                except ValueError:
                    output.fprint("Evaluations '{}, {}' resulted in "
                                  "un-plottable point with types ({}, {})."
                                  .format(evaluations['x'], evaluations[evl],
                                          type(x_list[-1]).__name__,
                                          type(y_list[-1]).__name__))

                    return errno.EINVAL

                if evaluations[evl] in args.plot_average:
                    stats_dict[evl]['x'].append(x)
                    stats_dict[evl]['y'].append(statistics.mean(y_list))

        for evl, values in stats_dict.items():
            if evaluations[evl] not in args.plot_average:
                continue
            label = evaluations[evl].split(".")[0]
            matplotlib.pyplot.scatter(values['x'], values['y'],
                                      marker="+",
                                      color=colormap[evl]['stat'],
                                      label="average({})".format(label))

        matplotlib.pyplot.ylabel(args.ylabel)
        matplotlib.pyplot.xlabel(args.xlabel)
        matplotlib.pyplot.legend()

        matplotlib.pyplot.savefig(args.filename)
        output.fprint("Completed. Graph saved as '{}.png'."
                      .format(args.filename), color=output.GREEN,
                      file=self.outfile)

    def gather_results(self, x_eval, y_evals, test_results) -> Dict:
        """
        Gather and format a test run objects results.

        :param evaluations: The evaluations dictionary to be used to gather
               results.
        :param test_results: A test run's result dictionary.
        :return: result, a dictionary containing parsed/formatted results for
                 the given test run.
        """

        all_evals = y_evals.copy()
        all_evals['x'] = x_eval
        try:
            evaluate_results(test_results, all_evals)
        except ResultError as err:
            output.fprint(
                "Invalid graph evaluation:\n{}".format(err.args[0]),
                file=self.errfile, color=output.RED)

        x_vals = test_results['x']

        # X value evaluations should only result in a list when graphing
        # individual node results from a single test run.
        if isinstance(test_results['x'], list):
            if not isinstance(test_results['x'][-1], (int, str, float)):
                raise ResultTypeError("x value evaluation '{}' resulted in a "
                                      "list of invalid type {}."
                                      .format(x_eval,
                                              type(test_results['x'][-1])
                                              .__name__))
            results = {}
            for i in range(len(test_results['x'])):
                x = test_results['x'][i]

                # Determines if x value is node name, if so convert name to int.
                if isinstance(x, str):
                    node = re.match(r'[a-zA-Z]*(\d*)$', x)
                    if node:
                        x = int(node.groups()[0])

                evals = {}
                for key in y_evals.keys():
                    if key == 'x':
                        continue
                    if not isinstance(test_results[key], list):
                        raise ResultTypeError("y value evaluation '{}' resulted"
                                              " in invalid type {}."
                                              .format(y_evals[key],
                                                      type(test_results[key])
                                                      .__name__))
                    evals.update({key: test_results[key][i]})

                results[x] = evals

        elif isinstance(test_results['x'], (int, float, str)):
            results = {}
            evals = {}

            x = test_results['x']

            for key in y_evals.keys():
                if key == 'x':
                    continue
                evals.update({key: test_results[key]})
            results[x] = evals

        else:
            raise ResultTypeError("x value  evaluation '{}' resulted in invalid"
                                  " type {}."
                                  .format(y_evals['x'],
                                          type(test_results['x']).__name__))

        return results

    def set_colors(self, y_evals, colors) -> Dict:
        """
        Set color for each y value to be plotted.
        :param y_evals: y axis evaluations dictionary.
        :param colors: Tuple of colors from a matplotlib color map.
        :return: A dictionary with color lookups, by y value.
        """

        colormap = {}
        colors = [color for color in colors]

        for key in y_evals.keys():
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


class ResultTypeError(RuntimeError):
    """Raise when evaluation results in an invalid type"""
