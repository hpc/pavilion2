"""Print the test results for the given test/suite."""

import datetime
import errno
import pprint
from typing import List

from pavilion import commands
from pavilion import output
from pavilion import series
from pavilion.result import check_config
from pavilion.test_config import resolver
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

    BASE_FIELDS = [
        'name',
        'id',
        'sys_name',
        'started',
        'finished',
        'result',
    ]

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

        test_ids = self._get_tests(pav_cfg, args.tests)

        tests = []
        for id_ in test_ids:
            try:
                tests.append(TestRun.load(pav_cfg, id_))
            except TestRunError as err:
                self.logger.warning("Could not load test %s - %s", id_, err)
            except TestRunNotFoundError as err:
                self.logger.warning("Could not find test %s - %s", id_, err)

        if args.re_run:
            if not self.update_results(pav_cfg, tests):
                return errno.EINVAL

        if args.json or args.full:
            results = {test.name: test.results for test in tests}
            try:
                if args.json:
                    output.json_dump(results, self.outfile)
                else:
                    pprint.pprint(results,  # ext-print: ignore
                                  stream=self.outfile)
            except OSError:
                # It's ok if this fails. Generally means we're piping to
                # another command.
                pass
            return 0

        else:
            fields = self.BASE_FIELDS + args.key
            results = [test.results for test in tests]

        def fix_timestamp(ts_str: str) -> str:
            """Read the timestamp text and get a minimized, formatted value."""
            try:
                when = datetime.datetime.strptime(ts_str,
                                                  '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                return ''

            return output.get_relative_timestamp(when)

        output.draw_table(
            outfile=self.outfile,
            field_info={
                'started': {'transform': fix_timestamp},
                'finished': {'transform': fix_timestamp},
            },
            fields=fields,
            rows=results,
            title="Test Results"
        )

    def _get_tests(self, pav_cfg, tests_arg):
        if not tests_arg:
            # Get the last series ran by this user.
            series_id = series.TestSeries.load_user_series_id(pav_cfg)
            if series_id is not None:
                tests_arg.append(series_id)

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

        return map(int, test_list)

    def update_results(self, pav_cfg: dict, tests: List[TestRun]) -> bool:
        """Update each of the given tests with the result section from the
        current version of their configs. Then rerun result processing and
        update the results in the test object (but change nothing on disk).

        :param pav_cfg: The pavilion config.
        :param tests: A list of test objects to update.
        :returns: True if successful, False otherwise. Will handle
            printing of any failure related errors.
        """

        reslvr = resolver.TestConfigResolver(pav_cfg)

        for test in tests:

            # Re-load the raw config using the saved name, host, and modes
            # of the original test.
            try:
                test_name = '.'.join((test.config['suite'],
                                      test.config['name']))

                configs = reslvr.load_raw_configs(
                    tests=[test_name],
                    host=test.config['host'],
                    modes=test.config['modes'],
                )
            except resolver.TestConfigError as err:
                output.fprint(
                    "Test '{}' could not be found: {}"
                    .format(test.name, err.args[0]),
                    color=output.RED, file=self.errfile)
                return False

            # These conditions guard against unexpected results from
            # load_raw_configs. They may not be possible.
            if not configs:
                output.fprint(
                    "No configs found for test '{}'. Skipping update."
                    .format(test.name), color=output.YELLOW, file=self.errfile)
                continue
            elif len(configs) > 1:
                output.fprint(
                    "Test '{}' somehow matched multiple configs."
                    "Skipping update.".format(test.name),
                    color=output.YELLOW, file=self.errfile)
                continue

            cfg = configs[0]
            results_section = cfg['results']

            # Try to resolve the updated result section of the config using
            # the original variable values.
            try:
                results_section = reslvr.resolve_section_values(
                    component=results_section,
                    var_man=test.var_man,
                    key_parts=('results',),
                )
            except resolver.TestConfigError as err:
                output.fprint(
                    "Test '{}' had a results section that could not be "
                    "resolved with it's original variables: {}"
                    .format(test.name, err.args[0])
                )
                return False
            except RuntimeError as err:
                output.fprint(
                    "Unexpected error updating result section for test '{}': "
                    "{}".format(test.name, err.args[0]),
                    color=output.RED, file=self.errfile)
                return False

            # Set the test's result section to the newly resolved one.
            test.config['results'] = results_section

            try:
                check_config(results_section)
            except TestRunError as err:
                output.fprint(
                    "Error found in results configuration: {}"
                    .format(err.args[0]))
                return False

            # The new results will be attached to the test (but not saved).
            test.gather_results(test.results['return_value'], regather=True)

        return True
