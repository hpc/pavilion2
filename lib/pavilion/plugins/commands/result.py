"""Print the test results for the given test/suite."""

import pprint
import sys

from pavilion import commands
from pavilion import output
from pavilion import series
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


class ResultsCommand(commands.Command):
    """Plugin for result printing."""

    def __init__(self):

        super().__init__(
            name="results",
            aliases=['result'],
            description="Displays results from the given tests.",
            short_help="Displays results from the given tests."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            "-j", "--json",
            action="store_true", default=False,
            help="Give the results in json."
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-k", "--key",
            action='append', nargs="*", default=[],
            help="Additional result keys to display."
        )
        group.add_argument(
            "-f", "--full", action="store_true", default=False,
            help="Show all result keys."
        )
        parser.add_argument(
            "tests",
            nargs="*",
            help="The tests to show the results for."
        )

    def run(self, pav_cfg, args):
        """Print the test results in a variety of formats."""

        test_ids = self._get_tests(pav_cfg, args.tests, args.full)

        tests = []
        for id_ in test_ids:
            try:
                tests.append(TestRun.load(pav_cfg, id_))
            except TestRunError as err:
                self.logger.warning("Could not load test %s - %s", id_, err)
            except TestRunNotFoundError as err:
                self.logger.warning("Could not find test %s - %s", id_, err)

        results = [test.results for test in tests]

        all_keys = set()
        for res in results:
            all_keys = all_keys.union(res.keys())

        all_keys = list(all_keys.difference(['result', 'name', 'id']))
        # Sort the keys by the size of the data
        # all_keys.sort(key=lambda k: max([len(res[k]) for res in results]))
        all_keys.sort(key=lambda k: max([len(r) for r in results]))

        if args.json:
            output.json_dump(results, self.outfile)
            return 0

        if args.full:
            try:
                pprint.pprint(results)  # ext-print: ignore
            except OSError:
                # It's ok if this fails. Generally means we're piping to
                # another command.
                pass
            return 0
        else:
            fields = ['name', 'id', 'result'] + sum(args.key, list())

        output.draw_table(
            outfile=self.outfile,
            field_info={},
            fields=fields,
            rows=results,
            title="Test Results"
        )

    def _get_tests(self, pav_cfg, tests_arg, full_arg):
        if not tests_arg:
            # Get the last series ran by this user.
            series_id = series.TestSeries.load_user_series_id(pav_cfg)
            if series_id is not None:
                tests_arg.append(series_id)

        if len(tests_arg) > 1 and full_arg:
            tests_arg = [tests_arg[0]]

        test_list = []
        for test_id in tests_arg:
            if test_id.startswith('s'):
                try:
                    test_list.extend(
                        series.TestSeries.from_id(
                            pav_cfg,
                            int(test_id[1:])).tests)
                except series.TestSeriesError as err:
                    self.logger.warning(
                        "Suite %s could not be found.\n%s", test_id[1:], err
                    )
                    continue
            else:
                test_list.append(test_id)

        if full_arg:
            if len(test_list) > 1:
                output.fprint(
                    "Requested full test results but provided multiple tests. "
                    "Giving results for only the first found.",
                    color=output.YELLOW,
                    file=sys.stdout,
                )
                test_list = [test_list[0]]

        return map(int, test_list)
