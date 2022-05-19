"""Graph pavilion results data."""

import collections
import pathlib
import errno
import re
import statistics
from argparse import RawDescriptionHelpFormatter
from typing import Dict

from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion.result.common import ResultError
from pavilion.result.evaluations import check_evaluations, evaluate_results
from .base_classes import Command

try:
    import matplotlib

    matplotlib.use('agg')
    import matplotlib.pyplot

    matplotlib.pyplot.ioff()

    HAS_MATPLOTLIB = True

except ImportError:
    HAS_MATPLOTLIB = False
    matplotlib = None

DIMENSIONS_RE = re.compile(r'\d+x\d+')


class GraphCommand(Command):
    """Command to graph Pavilion results data."""

    def __init__(self):
        super().__init__(
            'graph',
            description=(
                "Produce a graph from a set of test results. Each x value for"
                "each test run matched will be plotted. You can graph multiple "
                "result values , but it's up to you to make sure units and the "
                "plot as a whole makes sense. Wildcards in the x and y "
                "specifiers can be used to plot more complicated graphs."
                ".\n\n"
                "Graph Command Instructions:\n"
                "  1. Determine which test run results you want to\n"
                "     graph. Provide these test runs specifically\n"
                "     using test IDs or filter test runs using the\n"
                "     built in test filtering flags. You can use the result"
                "     command, which takes the same arguments, to narrow "
                "     the results down.\n\n"
                "  2. Add the values to be used on the X axis using\n"
                "     the '-x' flag. Each value must be a numeric\n"
                "     key from a test run's result dictionary or any\n"
                "     valid evaluation using a key from a test run's\n"
                "     result dictionary.\n\n"
                "  3. Add all the values to be plotted on the Y\n"
                "     axis, each one should be preceded by a '-y'\n"
                "     flag. These again have to be valid result keys\n"
                "     or evaluations.\n\n"
                "  4. Labels for both the X axis and Y axis can be \n"
                "     added using the '--xlabel' and '--ylabel'\n"
                "     flags, respectively.\n\n"
                "  5. Specify the filename to use when storing the \n"
                "     generated graph using the '--outfile' flag. \n"
                "     Note: The graph will be saved in the current\n"
                "     directory the user is in.\n\n"
                " X-axis and Y-axis specifiers can contain wildcards, just\n"
                " like with result evaluations. For example, given a test\n"
                " with per_file/per_node values, you could plot them by node\n"
                " using '-x per_file.*.some_key' and '-y keys(per_file).'\n"
                ),
            short_help="Produce a graph from a set of test results.",
            formatter_class=RawDescriptionHelpFormatter
        )

    def _setup_arguments(self, parser):

        filters.add_test_filter_args(parser)

        parser.add_argument(
            'tests', nargs='*', default=[], action='store',
            help='Specific Test Ids to graph. '
        )
        parser.add_argument(
            '--outfile', '-o', action='store', required=True,
            help='Desired name of graph when saved to PNG.'
        )
        parser.add_argument(
            '--exclude', default=[], action='append',
            help='Exclude specific Test Ids from the graph.'
        )
        parser.add_argument(
            '--y', '-y', action='append', required=True,
            help='Specify the value(s) graphed from the results '
                 'for each test.'
        )
        parser.add_argument(
            '--x', '-x', action='store', required=True,
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
            '--average', action='append', default=[],
            help='Generate an average plot for the specified y value(s).'
        )
        parser.add_argument(
            '--dimensions', action='store', default='',
            help='Specify the image size. Expects a \'width x height\' format.'
        )

    def run(self, pav_cfg, args):
        """Create a graph."""

        if not HAS_MATPLOTLIB:
            output.fprint(self.errfile,
                          "The command requires matplotlib to function. Matplotlib is an "
                          "optional requirement of Pavilion.")

            return errno.EINVAL

        if args.dimensions:
            match = DIMENSIONS_RE.match(args.dimensions)
            if not match:
                output.fprint(self.errfile,
                              "Invalid '--dimensions' string '{}', doesn't match expected "
                              "format. Using matplotlib default dimensions."
                              .format(args.dimensions), color=output.YELLOW)
                args.dimensions = ''

        output.fprint(self.outfile, "Generating Graph...")

        # Get filtered Test IDs.
        test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile)

        # Load TestRun for all tests, skip those that are to be excluded.
        tests = cmd_utils.get_tests_by_paths(
            pav_cfg, test_paths, self.errfile, exclude_ids=args.exclude)

        # Add any additional tests provided via the command line.
        if args.tests:
            cmdline_tests = cmd_utils.get_tests_by_id(pav_cfg, args.tests, self.errfile)
            tests.extend(cmdline_tests)

        if not tests:
            output.fprint(self.errfile, "Test filtering resulted in an empty list.")
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
            output.fprint(self.errfile, "Invalid graph evaluation:\n{}".format(err),
                          color=output.RED)

        # Set colormap and build colormap dict
        colormap = matplotlib.pyplot.get_cmap('tab20')
        colormap = GraphCommand.set_colors(y_evals, colormap.colors)

        # Populate graph data dict with evaluation data from all tests provided.
        graph_data = {}
        for test in tests:
            try:
                test_graph_data = GraphCommand.gather_graph_data(x_eval,
                                                                 y_evals,
                                                                 test.results)
            except InvalidEvaluationError as err:
                output.fprint(self.errfile, "Error gathering graph data for test {}: \n{}"
                              .format(test.id, err), color=output.YELLOW)
                continue
            except ResultTypeError as err:
                output.fprint(self.errfile, "Gather graph data for test {} resulted in "
                                            "invalid type: \n{}"
                              .format(test.id, err), color=output.RED)
                return errno.EINVAL

            graph_data = GraphCommand.combine_graph_data(graph_data,
                                                         test_graph_data)

        graph_data = collections.OrderedDict(sorted(graph_data.items()))

        # Graph the data.
        try:
            self.graph(args.xlabel, args.ylabel, y_evals, graph_data,
                       stats_dict, args.average, colormap,
                       args.outfile, args.dimensions)
        except PlottingError as err:
            output.fprint(self.errfile, "Error while graphing data:\n{}".format(err),
                          color=output.RED)
            return errno.EINVAL

    @staticmethod
    def set_colors(y_evals, colors) -> Dict:
        """Set color for each y value to be plotted.

        :param y_evals: y axis evaluations dictionary.
        :param colors: Tuple of colors from a matplotlib color map.
        :return: A dictionary with color lookups, by y value.
        """

        colormap = {}
        colors = [color for color in colors]

        for key in y_evals.keys():
            colormap[key] = {'plot': colors.pop(0), 'stat': colors.pop(0)}

        return colormap

    @staticmethod
    def gather_graph_data(x_eval, y_evals, test_results) -> Dict:
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
            evaluate_results(results=test_results, evaluations=all_evals)
        except ResultError as err:
            raise InvalidEvaluationError("Invalid graph evaluation for test "
                                         "{}:\n{}"
                                         .format(test_results['id'], err))
        x_vals = test_results['x']

        if isinstance(x_vals, (int, float, str)):
            graph_data = {}
            evaluations = {}

            for key in y_evals.keys():
                evaluations.update({key: test_results[key]})
            graph_data[x_vals] = evaluations

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
                x_val = x_vals[i]

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

                graph_data[x_val] = evaluations

        else:
            raise ResultTypeError("x value  evaluation '{}' resulted in invalid"
                                  " type {}, '{}'."
                                  .format(x_eval, type(x_vals).__name__,
                                          x_vals))

        return graph_data

    @staticmethod
    def combine_graph_data(graph_data, test_graph_data) -> Dict:
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
              averages, colormap, outfile, dimensions):
        """
        Graph the data collected from all test runs provided. Graph_data has
        formatted everything so you can graph every y value for each respective
        x value in a single pass.
        :param xlabel: Label for the graph's x-axis.
        :param ylabel: Label for the graph's y-axis.
        :param y_evals: Y axis eval strings.
        :param graph_data: Data to be plotted on the graph. Expects a nested
        dictionary.
        :param stats_dict:
        :param averages: List of evaluations to plot averages of.
        :param colormap: dictionary of colors mapped to expected y value
        evaluations.
        :param outfile: String name to save graph as.
        :param dimensions: String representing desired graph dimension in a
        'width x height' format.
        :return:
        """

        labels = set()
        for x_val, eval_dict in graph_data.items():
            for evl, y_list in eval_dict.items():
                color = colormap[evl]['plot']

                label = y_evals[evl].split(".")[-1]
                label = label if label not in labels else ""
                labels.add(label)

                x_list = [x_val] * len(y_list)

                try:
                    matplotlib.pyplot.scatter(x=x_list, y=y_list, marker="o",
                                              color=color,
                                              label=label)
                except ValueError:
                    raise PlottingError("Evaluations '{}, {}' resulted in "
                                        "un-plottable values.\n"
                                        "X list: {}\n"
                                        "Y list: {}\n"
                                        .format(eval_dict,
                                                y_evals[evl],
                                                x_list,
                                                y_list))

                if y_evals[evl] in averages:
                    stats_dict[evl]['x'].append(x_val)
                    stats_dict[evl]['y'].append(statistics.mean(y_list))

        for evl, values in stats_dict.items():
            if y_evals[evl] not in averages:
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

        if not pathlib.Path(outfile).suffix:
            outfile = outfile + '.png'

        output.fprint(self.outfile, "Completed. Graph saved as '{}'."
                      .format(outfile), color=output.GREEN)


class ResultTypeError(RuntimeError):
    """Raise when evaluation results in an invalid type"""


class InvalidEvaluationError(RuntimeError):
    """Raise when evaluations result in some error."""


class PlottingError(RuntimeError):
    """Raise when something goes wrong when graphing"""
