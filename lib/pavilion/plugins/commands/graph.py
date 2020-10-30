"""Graph pavilion results data."""

import collections
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

    HAS_MATPLOTLIB = True

except ImportError:

    HAS_MATPLOTLIB = False

DIMENSIONS_RE = re.compile(r'\d+x\d+')


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
            'tests', nargs='*', default=[], action='store',
            help='Specific Test Ids to graph. '
        )
        parser.add_argument(
            '--filename', action='store', required=True,
            help='Desired name of graph when saved to PNG.'
        )
        parser.add_argument(
            '--exclude', default=[], action='append',
            help='Exclude specific Test Ids from the graph.'
        )
        parser.add_argument(
            '--y', action='append', required=True,
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        )
        parser.add_argument(
            '--x', action='store', required=True,
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
            '--plot-average', action='append', default=[],
            help='Generate an average plot for the specified y value(s).'
        )
        parser.add_argument(
            '--dimensions', action='store', default='',
            help='Specify the image size. Expects a \'width x height\' format.'
        )

    def run(self, pav_cfg, args):
        """"""

        if not HAS_MATPLOTLIB:
            output.fprint(
                "The command requires matplotlib to function. Matplotlib is an "
                "optional requirement of Pavilion.",
                file=self.errfile)

            return errno.EINVAL

        try:
            exclude = [int(test) for test in args.exclude]
        except ValueError as err:
            output.fprint(
                "Invalid '--exclude' test id:\n{}".format(err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL

        if args.dimensions:
            match = DIMENSIONS_RE.match(args.dimensions)
            if not match:
                output.fprint(
                    "Invalid '--dimensions' string '{}', doesn't match "
                    "expected format. Using matplotlib default dimensions."
                    .format(args.dimensions),
                    color=output.YELLOW, file=self.errfile
                )
                args.dimensions = ''

        output.fprint("Generating Graph...", file=self.outfile)

        # Get filtered Test IDs.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)
        # Add any additional tests provided via the command line.
        test_ids.append(args.tests)

        # Load TestRun for all tests, skip those that are to be excluded.
        tests = []
        for test_id in test_ids:
            if test_id in exclude:
                continue

            try:
                tests.append(TestRun.load(pav_cfg, test_id))
            except TestRunError as err:
                output.fprint(
                    "Error loading test run {}. Use '--exclude' to stop "
                    "seeing this message.\n{}"
                    .format(test_id, err.args[0]),
                    color=output.YELLOW, file=self.errfile)
                pass

        if not tests:
            output.fprint("Test filtering resulted in an empty list.",
                          file=self.errfile)
            return errno.EINVAL

        # Build respective evaluation dictionaries.
        x_eval = {'x': args.x}
        y_evals = {'y' + str(i): args.y[i] for i in range(len(args.y))}
        stats_dict = {key: {'x': [], 'y': []} for key in y_evals}

        # Check to ensure all evaluations are valid.
        all_evals = y_evals.copy()
        all_evals.update(x_eval)

        try:
            check_evaluations(all_evals)
        except ResultError as err:
            output.fprint(
                "Invalid graph evaluation:\n{}".format(err.args[0]),
                file=self.errfile, color=output.RED)

        # Set colormap and build colormap dict
        colormap = matplotlib.pyplot.get_cmap('tab20')
        colormap = self.set_colors(y_evals, colormap.colors)

        # Populate graph data dict with evaluation data from all tests provided.
        graph_data = {}
        for test in tests:
            try:
                test_graph_data = self.gather_graph_data(x_eval, y_evals,
                                                         test.results)
            except (ResultError, ResultTypeError) as err:
                output.fprint("Error gathering results for test {}: \n{}"
                              .format(test.id, err),
                              file=self.errfile, color=output.RED)
                return errno.EINVAL

            graph_data = self.combine_graph_data(graph_data, test_graph_data)

        graph_data = collections.OrderedDict(sorted(graph_data.items()))

        # Graph the data.
        try:
            self.graph(args.xlabel, args.ylabel, y_evals, graph_data,
                       stats_dict, args.plot_average, colormap,
                       args.filename, args.dimensions)
        except PlottingError as err:
            output.fprint("Error while graphing data:\n{}".format(err),
                          file=self.errfile, color=output.RED)
            return errno.EINVAL

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

    def gather_graph_data(self, x_eval, y_evals, test_results) -> Dict:
        """
        Gather and format a test run objects results.

        :param x_eval:
        :param y_evals:
        :param test_results: A test run's result dictionary.
        :return: result, a dictionary containing parsed/formatted results for
                 the given test run.

        Builds a result data structure that looks like:

        graph_data = {
            x value: {
                y eval 1: [result values],
                y eval 2: [result values]
            }
        }
        """

        all_evals = y_evals.copy()
        all_evals.update(x_eval)

        try:
            evaluate_results(test_results, all_evals)
        except ResultError as err:
            output.fprint(
                "Invalid graph evaluation for test {}:\n{}"
                .format(test_results['id'], err.args[0]),
                file=self.errfile, color=output.RED)

        x_vals = test_results['x']

        if isinstance(x_vals, (int, float, str)):
            graph_data = {}
            evaluations = {}

            x = x_vals

            for key in y_evals.keys():
                evaluations.update({key: test_results[key]})
            graph_data[x] = evaluations

        # X value evaluations should only result in a list when graphing
        # individual node results from a single test run.
        elif isinstance(x_vals, list):
            if not x_vals:
                raise ResultTypeError("x value evaluation '{}' resulted in an "
                                      "empty list."
                                      .format(x_eval))
            for item in x_vals:
                if not isinstance(item, (int, str, float)):
                    raise ResultTypeError("x value evaluation '{}' resulted in "
                                          "a list, but contained invalid "
                                          "type {} '{}'."
                                          .format(x_eval, type(item).__name__,
                                                  item))
            graph_data = {}
            for i in range(len(x_vals)):
                x = x_vals[i]

                evaluations = {}
                for key in y_evals.keys():
                    if not isinstance(test_results[key], list):
                        raise ResultTypeError("y value evaluation '{}' "
                                              "resulted in {} '{}'. Since x "
                                              "value evaluation resulted in a "
                                              "list, this must be a list."
                                              .format(y_evals[key],
                                                      type(test_results[key])
                                                      .__name__,
                                                      test_results[key]))
                    evaluations.update({key: test_results[key][i]})

                graph_data[x] = evaluations

        else:
            raise ResultTypeError("x value  evaluation '{}' resulted in invalid"
                                  " type {}, '{}'."
                                  .format(x_eval, type(x_vals).__name__,
                                          x_vals))

        return graph_data

    def combine_graph_data(self, graph_data, test_graph_data) -> Dict:
        """
        Takes individual test run graph data and tries to extend
        lists of values for the same x value and y evaluation if they exist
        otherwise add the respective keys to the updated graph_data dict. This
        is so every y value for any given x value can be plotted in a single
        pass.
        :param graph_data: Passed  pav graph data dict.
        :param test_graph_data: Passed individual TestRun's graph data dict.
        :return: Updated/Combined graph_data dict.
        """

        for key, values in test_graph_data.items():
            if key not in graph_data:
                graph_data[key] = {}
            for evl, value in values.items():
                if evl not in graph_data[key]:
                    graph_data[key][evl] = []
                if isinstance(value, list):
                    graph_data[key][evl].extend(value)
                else:
                    graph_data[key][evl].extend([value])

        return graph_data

    def graph(self, xlabel, ylabel, y_evals, graph_data, stats_dict,
              plot_averages, colormap, filename, dimensions):
        """
        Graph the data collected from all test runs provided. Graph_data has
        formatted everything so you can graph every y value for each respective
        x value in a single pass.
        :param xlabel: Label for the graph's x-axis.
        :param ylabel: Label for the graph's y-axis.
        :param graph_data: Data to be plotted on the graph. Expects a nested
        dictionary.
        :param stats_dict:
        :param plot_averages: List of evaluations to plot averages of.
        :param colormap: dictionary of colors mapped to expected y value
        evaluations.
        :param filename: String name to save graph as.
        :param dimensions: String representing desired graph dimension in a
        'width x height' format.
        :return:
        """

        labels = set()
        for x, eval_dict in graph_data.items():
            for evl, y_list in eval_dict.items():
                color = colormap[evl]['plot']

                label = y_evals[evl].split(".")[-1]
                label = label if label not in labels else ""
                labels.add(label)

                x_list = [x] * len(y_list)

                try:
                    matplotlib.pyplot.scatter(x=x_list, y=y_list, marker="o",
                                              color=color,
                                              label=label)
                except ValueError:
                    raise PlottingError("Evaluations '{}, {}' resulted in "
                                        "un-plottable values.\n"
                                        "X list: {}\n"
                                        "Y list: {}\n"
                                        .format(evaluations['x'],
                                                evaluations[evl],
                                                x_list,
                                                y_list))

                if y_evals[evl] in plot_averages:
                    stats_dict[evl]['x'].append(x)
                    stats_dict[evl]['y'].append(statistics.mean(y_list))

        for evl, values in stats_dict.items():
            if y_evals[evl] not in plot_averages:
                continue
            label = y_evals[evl].split(".")[-1]
            matplotlib.pyplot.scatter(values['x'], values['y'],
                                      marker="+",
                                      color=colormap[evl]['stat'],
                                      label="average({})".format(label))

        matplotlib.pyplot.ylabel(ylabel)
        matplotlib.pyplot.xlabel(xlabel)
        matplotlib.pyplot.legend()

        fig = matplotlib.pyplot.gcf()

        if dimensions:
            width, height = dimensions.split('x')
            fig.set_size_inches(float(width), float(height))

        fig.savefig(filename)
        output.fprint("Completed. Graph saved as '{}.png'."
                      .format(filename), color=output.GREEN, file=self.outfile)


class ResultTypeError(RuntimeError):
    """Raise when evaluation results in an invalid type"""


class PlottingError(RuntimeError):
    """Raise when something goes wrong when graphing"""
