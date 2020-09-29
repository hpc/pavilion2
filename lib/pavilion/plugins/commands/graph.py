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

        try:
            self.validate_args(args)
        except CommandError as err:
            output.fprint("Invalid command arguments: \n{}".format(err),
                          color=output.RED)
            return errno.EINVAL

        # Get filtered Test IDs, and then load TestRun objects.
        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)
        tests = [TestRun.load(pav_cfg, test_id) for test_id in test_ids]

        evals = self.build_evaluations_dict(args.x, args.y)

        for test in tests:
            results = self.gather_results(evals, test.results)
            for key, vals in results.items():
                for yval in vals.values():
                    if isinstance(yval, list):
                        for item in yval:
                            plt.plot(key, item, marker="o")
                    else:
                        plt.plot(key, yval, marker="o")

        plt.ylabel(args.y_label)
        plt.xlabel(args.x_label)
        plt.title(args.title)
        plt.legend()
        plt.show()

    def gather_results(self, evals, test_results) -> Dict(results):
        """
        Gather and format a test run objects results.
        :param evals: The evaluations dictionary to be used to gather results.
        :param test_results: A test run's result dictionary.
        :return: result, a dictionary containing parsed/formatted results for
                 the given test run.
        """
        evaluations.evaluate_results(test_results, evals)

        if isinstance(test_results['x'], list):
            results = {}
            for i in range(len(test_results['x'])):
                result_dict = {}
                for key in evals.keys():
                    if key == 'x':
                        continue
                    result_dict.update({key: test_results[key][i]})
                results[test_results['x'][i]] = result_dict

        else:
            results = {}
            result_dict = {}
            for key in evals.keys():
                if key == 'x':
                    continue
                result_dict.update({key: test_results[key]})
            results[test_results['x']] = result_dict

        return results

    def validate_args(self, args) -> None:
        """Validate command arguments.
        :param args: the passed args parse object.
        :return: None.
        """

        if not args.x:
            raise CommandError("No value was given to graph on X-axis. Use "
                               "--x flag to specify.")
        if not args.y:
            raise CommandError("No values were given to graph on y-axis. "
                               "Use --y flag to specify.")

    def build_evaluations_dict(self, x_eval, y_eval) -> Dict(evals):
        """Take the parsed command arguments for --x and  --y and build an
        evaluations dictionary to be used later for gathering results.
        :param x_eval: List of evaluation string for x value.
        :param y_eval: List of evaluation string for y values.
        :return: A dictionary to be used with pavilion's evaluations module.
        """

        evals = {}
        evals['x'] = x_eval[0]
        for i in range(len(y_eval)):
            evals['y'+str(i)] = y_eval[i]

        evaluations.check_evaluations(evals)

        return evals
