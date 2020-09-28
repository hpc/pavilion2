import errno
from datetime import datetime

from pavilion import cmd_utils
from pavilion import commands
from pavilion import filters
from pavilion import output
from pavilion.commands import Command, CommandError
from pavilion.result import evaluations
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
            '--x_label', action='store', default="",
            help='Specify the x axis label.'
        ),
        parser.add_argument(
            '--y_label', action='store', default="",
            help='Specify the y axis label.'
        ),
        parser.add_argument(
            '--title', action='store', default="",
            help='Specify the title of the graph.'
        ),

    def run(self, pav_cfg, args):

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            output.fprint("matplotlib not found.", color=output.RED)
            return errno.EINVAL

        # Validate Arguments.
        try:
            self.validate_args(args)
        except (CommandError, ValueError) as err:
            output.fprint("Invalid command arguments: \n{}".format(err),
                          color=output.RED)
            return errno.EINVAL

        # Get filtered Test IDs, and then load TestRun objects.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)
        tests = [TestRun.load(pav_cfg, test_id) for test_id in test_ids]

        evals = self.build_evaluations_dict(args.x, args.y)

        try:
            test_results = self.get_test_results(tests, evals)
        except (ValueError, TypeError, ResultError) as err:
            output.fprint("Evaluations resulted in error:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL
        output.fprint("Plotting...")
        ax = plt.gca()
        for test_id, results in test_results.items():
            color = next(ax._get_lines.prop_cycler)['color']
            for x, y_list in results.items():
                for y in y_list:
                    plt.plot(x, y, marker='o', color=color)

        plt.ylabel(args.y_label)
        plt.xlabel(args.x_label)
        plt.title(args.title)
        plt.legend()
        plt.show()

    def validate_args(self, args) -> None:
        if not args.x:
            raise CommandError("No value was given to graph on X-axis. Use "
                               "--x flag to specify.")
        if not args.y:
            raise CommandError("No values were given to graph on y-axis. "
                               "Use --y flag to specify.")

    def build_evaluations_dict(self, x_eval, y_eval):
        """Take the parsed command arguments for --x and --y and build
        an evaluations dictionary to be used later when gathering results.
        :param list x_eval: List of evaluation string for x value.
        :param list y_eval: List of evaluation strings for y values.
        :return dict evals: A dictionary of the evaluations.

            evals -> {
                 'x': evaluation string,
                'y0': evaluation string,
                'y1': evaluation string,
                .
                .
                .
            }
        """

        evals = {}
        evals['x'] = x_eval[0]
        for i in range(len(y_eval)):
            evals['y'+str(i)] = y_eval[i]

        return evals

    def transform_data_list(self, x_data_list, y_data_list):
        """ Transforms y_data_list to expected format even with multiple 
        x_values are present.
        :param list x_data_list: List of all x values to plot.
        :param list y_data_list: List of all y values to plot, Sublists will be
                                 ordered by evaluations, not x values.
        :return list y_data_list: This is a verified, reordered list of y
                                  values.
        """

        transformed = []
        if len(x_data_list) > 1:
            for index in range(len(x_data_list)):
                temp = []
                for item in y_data_list:
                    temp.append(item[index])
                transformed.append(temp)
            y_data_list = transformed

        return y_data_list

    def validate_result(self, result, evals):
        """Ensures that the evaluation result is of a type we can use.
        :param result: This is the result we are checking.
        :param str evals: This is the evaluation that generated this result.
        :return list result: Returns the given result in a list.
        """

        # Ensure results are values we can plot.
        if not isinstance(result, (float, int, list)):
            raise ResultError("'{}' evaluation resulted in '{}'. "
                              "Expected result of float, int, or list."
                              .format(evals,
                                      type(result).__name__))

        # Ensure that lists contain values that we can plot. 
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, (int, float)):
                    raise ResultError("'{}' evaluation resulted in a "
                                      "list that contains invalid type "
                                      "'{}'.".format(evals,
                                                     type(item).__name__))
            return result

        else:
            return [result]

    def get_evaluation_data(self, results, evals):
        """Get the evaluation data to plot out of results.
        :param dict results: The test results dictionary.
        :param dict evals: The graph command's evaluation arguments.
        :return list x_data_list: The list of x values to plot.
        :return list y_data_list: The list of y values to plot.
        """

        x_result = results['x']

        if isinstance(x_result, list):
            x_data_list = x_result
        else:
            x_data_list = [x_result]

        y_data_list = []

        # Store Evaluations results in a y_data_list
        for key in evals:
            if key is 'x':
                continue
            result = results[key]
            y_data_list.append(self.validate_result(result, evals[key]))

        y_data_list = self.transform_data_list(x_data_list, y_data_list)

        return x_data_list, y_data_list

    def evaluate_results(self, evals, results):
        """Get the data from the test's results. Use pavilion's
        evaluations to do so.
        :param evals: The evaluations dictionary.
        :param dict results: The loaded results dictionary.
        :return dict results: The data pulled out of a tests results
                              dictionary.
        The returned data structure looks like:
            results -> {
                x: [Y,...+]
                }
        """

        evaluations.evaluate_results(results, evals)

        x_data_list, y_data_list = self.get_evaluation_data(results, evals)

        results = {}
        for x, y in zip(x_data_list, y_data_list):
            results[x] = y

        return results

    def get_test_results(self, tests, evals):
        """Get all test results in a single dictionary.
        :param list tests: A list of test objects.
        :param dict evals: A dictionary of the result evaluations.
        :return dict test_results: A dictionary of test results in which the
                                   test id is the key, and the value is it's 
                                   respective results.
        The returned data structure looks like:
            test_results -> {
                test_id: {
                        x: [list of Y values]
                    }
                }
        """

        test_results = {}

        for test in tests:
            results = self.evaluate_results(evals, test.results)
            test_results[test.id] = results

        return test_results
