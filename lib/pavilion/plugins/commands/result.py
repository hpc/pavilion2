"""Print the test results for the given test/suite."""

import pprint
from typing import List

from pavilion import commands
from pavilion import output
from pavilion import series
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError
from pavilion.test_config import resolver


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
            '-r', '--re-run', dest="re_run",
            action='store_true', default=False,
            help="Re-run the results based on the latest version of the test"
                 "configs, though only changes to the 'result' section are "
                 "applied. This will not alter anything in the test's run "
                 "directory; the new results will be displayed but not "
                 "otherwise saved or logged."
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

        if args.re_run:
            self._update_results(tests)

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
                    file=self.errfile,
                )
                test_list = [test_list[0]]

        return map(int, test_list)

    def update_results(self, pav_cfg: dict, tests: List[TestRun]):
        """Update each of the given tests with the result section from the
        current version of their configs. Then rerun result processing and
        update the results in the test object (but change nothing on disk)."""

        reslvr = resolver.TestConfigResolver(pav_cfg)

        for test in tests:
            reslvr.load_raw_configs()


