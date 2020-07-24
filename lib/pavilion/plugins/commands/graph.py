import errno
import os
import random
import re
from datetime import datetime

#from pavilion import commands
from pavilion import output
from pavilion import series
from pavilion.commands import Command, CommandError
from pavilion.result import evaluations
from pavilion.result.base import ResultError
from pavilion.status_file import STATES
from pavilion.test_run import TestRun


class GraphCommand(Command):

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
                 'test suites, or users by providing specific IDs '
                 'or names.'
        ),
        parser.add_argument(
            '--test_name', action='store', default=False,
            help='Filter tests by test_name.'
        ),
        parser.add_argument(
            '--suite', action='store', default=False,
            help='Filter tests by test suite.'
        ),
        parser.add_argument(
            '--sys_name', nargs='+', action='store', default=False,
            help='Filter tests by sys_name.'
        ),
        parser.add_argument(
            '--user', nargs='+', action='store', default=False,
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
        ),
        parser.add_argument(
            '--title', action='store', default="",
            help='Specify the title of the graph.'
        )

    def run(self, pav_cfg, args):

        try:
            import matplotlib.pyplot as plt
        except (ImportError, ModuleNotFoundError) as err:
            output.fprint("matplotlib not found.", color=output.RED)
            return errno.EINVAL

        # Validate Arguments.
        try:
            self.validate_args(args)
        except (ValueError, CommandError) as err:
            output.fprint("Invalid command arguments:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL

        # Expand series, convert test_ids (if provided).
        try:
            args.tests = self.normalize_args_tests(pav_cfg, args.tests)
        except (ValueError, series.TestSeriesError) as err:
            output.fprint("Invalid test arguments:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL

        # Check filters, append/remove tests.
        try:
            tests = self.filter_tests(pav_cfg, args, args.tests)
        except CommandError as err:
            output.fprint(err)
            return errno.EINVAL

        evals = self.build_evaluations_dict(args.x, args.y)

        try:
            test_results = self.get_test_results(tests, evals)
        except (ValueError, TypeError, ResultError) as err:
            output.fprint("Evaluations resulted in error:", color=output.RED)
            output.fprint(err)
            return errno.EINVAL

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

    def validate_args(self, args):
        """Validates all arguments passed to the graph command. Will change
        :param args: The parsed command line argument object.
        """

        # Validate Date.
        if args.date:
            args.date = args.date.strip("'")
            try:
                args.date = datetime.strptime(args.date, '%b %d %Y')
            except ValueError as err:
                raise ValueError("{} is not a valid date "
                              "format: {}".format(args.date, err))

        if not args.x:
            raise CommandError("No value was given to graph on X-axis. Use "
                               "--x flag to specify.")
        if not args.y:
            raise CommandError("No values were given to graph on y-axis. "
                               "Use --y flag to specify.")

    def expand_ranges(self, test_list):
        """Converts a string range of test IDs or series IDs into a list of
        tests or series strings. Note, this is inclusive. Therefore a range of
        123-126 will include 126.
        :param list test_list: A list of tests, series, or ranges strings.
        :return list update_test_list: A list of test or series strings.
        """

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
        """Converts test strings into string format used on test_run folder
        names in the working directory, also expands series into their
        respective test ids.
        :param pav_cfg: The pavilion configuration.
        :param list test_lists: A list of test or series strings.
        :return list normalized_test_list: A list of tests strings, normalized
                                           to appear as they do in the
                                           working_dir.
        """

        if not test_list:
            return []

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

    def apply_filters(self, pav_cfg, args, test_path):
        """Apply the search filters to a given test.
        :param pav_cfg: The pavilion configuration.
        :param args: The parsed command line argument object.
        :param test_path: A test path to check.
        :return none: If a test is filtered out.
        :return test: A test object is returned if not filtered out.
        """

        # Make sure given path is a directory.
        if not test_path.is_dir():
            return None

        if test_path.name in args.exclude:
            return None

        # Filter tests by date.
        if args.date:
            test_date = datetime.fromtimestamp(test_path.stat().st_ctime)
            if test_date.date() != args.date.date():
                return None

        # Filter tests by user.
        owner = test_path.owner()
        if args.user and owner not in args.user:
            return None
        if owner in args.exclude:
            return None

        # Load Test Object, to check Host name and Test Name
        test = TestRun.load(pav_cfg, int(test_path.name))

        # Ensure test has completed, and successfully run.
        status = test.status.current()
        if status.state != STATES.COMPLETE:
            return None

        # Filter tests by test name.
        if args.test_name and test.name not in args.test_name:
            return None
        if test.name in args.exclude:
            return None

        # Filter tests by suite name.
        suite = test.config.get('suite')
        if args.suite and suite not in args.suite:
            return None
        if suite in args.exclude:
            return None

        # Filter tests by sys name.
        host = test.config.get('host')
        if args.sys_name and host not in args.sys_name:
            return None
        if host in args.exclude:
            return None

        return test

    def filter_tests(self, pav_cfg, args, tests):
        """Filter provided tests, or entire directory, returns a list of tests
        that match the search critetia.
        :param pav_cfg: The pavilion configuration.
        :param args: The parsed command line argument object.
        :return list test_list: A list of valid test objects.
        """

        tests_dir = pav_cfg.working_dir / 'test_runs'
        test_list = []
        # Filter All Tests.
        if not tests:
            for test_path in tests_dir.iterdir():
                test = self.apply_filters(pav_cfg, args, test_path)
                if test is None:
                    continue
                test_list.append(test)

        # Filter provided list of tests.
        else:
            for test_id in tests:
                test_path = tests_dir / test_id
                test = self.apply_filters(pav_cfg, args, test_path)
                if test is None:
                    continue
                test_list.append(test)

        if not test_list:
            raise CommandError("No successful, completed tests "
                               "matched these filters.")

        return test_list

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

    def verify_and_transform_data_list(self, x_data_list, y_data_list):
        """ Transforms y_data_list to work if multiple x_values are present.
        Also checks to ensure lists are of equal length.
        :param list x_data_list: List of all x values to plot.
        :param list y_data_list: List of all y values to plot, Sublists will be
                                 ordered by evaluations, not x values.
        :return list y_data_list: This is a verified, reordered list of y
                                  values.
        """

        #if len(x_data_list) > 1:
        transformed = []
        for index in range(len(x_data_list)):
            transformed.append([item[index] for item in y_data_list])
        y_data_list = transformed

        if len(x_data_list) != len(y_data_list):
            raise ValueError("Evaluations resulted in lists of different "
                             "lengths.")

        return y_data_list

    def validate_result(self, result, evals):
        """Ensures that the evaluation result is of a type we can use.
        :param result: This is the result we are checking.
        :param str evals: This is the evaluation that generated this result.
        :return list result: Returns the given result in a list.
        """

        result_type = type(result)

        # Ensure results are values we can plot.
        if result_type not in (float, int, list):
            raise TypeError("'{}' evaluation resulted in '{}'. "
                            "Expected result of float, int, or list."
                            .format(evals,
                                    result_type.__name__))

        # Ensure that lists contain values that we can plot. 
        if result_type is list:
            for item in result:
                if type(item) not in (int, float):
                    raise TypeError("'{}' evaluation resulted in a "
                                    "list that contains invalid type "
                                    "'{}'.".format(evals,
                                                   type(item).__name__))
            return result

        else:
            return [result]

    def get_evaluation_data(self, results, evals):
        """Get the evaluation data to plot out of results.
        :param dict results: The test results dictionary.
        :param dict evals: The graph command's evalaution arguments.
        :return list x_data_list: The list of x values to plot.
        :return list y_data_list: The list of y values to plot.
        """

        x_result = results['x']

        if type(x_result) is list:
            x_data_list = x_result
        else:
            x_data_list = [x_result]

        y_data_list = []

        # Store Evaluations results in a y_data_list
        for key in evals:
            if key is 'x':
                continue

            result = results[key]

            if '*' in evals[key]:
                for item in result:
                    y_data_list.append(self.validate_result(item,
                                                            evals[key]))
            else:
                y_data_list.append(self.validate_result(result,
                                                    evals[key]))

        y_data_list = self.verify_and_transform_data_list(x_data_list,
                                                          y_data_list)

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

