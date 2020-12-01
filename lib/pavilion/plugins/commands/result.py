"""Print the test results for the given test/suite."""

import datetime
import errno
import io
import pprint
import shutil
from typing import List, IO

from pavilion import cmd_utils
from pavilion import commands
from pavilion import filters
from pavilion import output
from pavilion import result
from pavilion.test_config import resolver
from pavilion.test_run import (TestRun, TestRunError, TestRunNotFoundError)


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
            help="Re-run the results based on the latest version of the test "
                 "configs, though only changes to the 'result' section are "
                 "applied. This will not alter anything in the test's run "
                 "directory; the new results will be displayed but not "
                 "otherwise saved or logged."
        )
        parser.add_argument(
            '-s', '--save',
            action='store_true', default=False,
            help="Save the re-run to the test's results json and log. Will "
                 "not update the general pavilion result log."
        )
        parser.add_argument(
            '-L', '--show-log', action='store_true', default=False,
            help="Also show the result processing log. This is particularly"
                 "useful when re-parsing results, as the log is not saved."
        )

        parser.add_argument(
            "tests",
            nargs="*",
            help="The tests to show the results for. Use 'last' to get the "
                 "results of the last test series you ran on this machine."
        )
        filters.add_test_filter_args(parser)

    def run(self, pav_cfg, args):
        """Print the test results in a variety of formats."""

        test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args)

        tests = []
        for id_ in test_ids:
            try:
                tests.append(TestRun.load(pav_cfg, id_))
            except TestRunError as err:
                self.logger.warning("Could not load test %s - %s", id_, err)
            except TestRunNotFoundError as err:
                self.logger.warning("Could not find test %s - %s", id_, err)

        log_file = None
        if args.show_log and args.re_run:
            log_file = io.StringIO()

        if args.re_run:
            if not self.update_results(pav_cfg, tests, log_file):
                return errno.EINVAL

        if args.save:
            if not self.update_results(pav_cfg, tests, log_file, save=True):
                return errno.EINVAL

        if args.json or args.full:
            if len(tests) > 1:
                results = {test.name: test.results for test in tests}
            elif len(tests) == 1:
                results = tests[0].results
            else:
                output.fprint("Could not find any matching tests.",
                              color=output.RED, file=self.outfile)
                return errno.EINVAL

            width = shutil.get_terminal_size().columns or 80

            try:
                if args.json:
                    output.json_dump(results, self.outfile)
                else:
                    pprint.pprint(results,  # ext-print: ignore
                                  stream=self.outfile, width=width,
                                  compact=True)
            except OSError:
                # It's ok if this fails. Generally means we're piping to
                # another command.
                pass

        else:
            fields = self.BASE_FIELDS + args.key
            results = [test.results for test in tests]

            def fix_timestamp(ts_str: str) -> str:
                """Read the timestamp text and get a minimized,
                formatted value."""
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

        if args.show_log:
            if log_file is not None:
                output.fprint(log_file.getvalue(), file=self.outfile,
                              color=output.GREY)
            else:
                for test in tests:
                    output.fprint("\nResult logs for test {}\n"
                                  .format(test.name), file=self.outfile)
                    if test.results_log.exists():
                        with test.results_log.open() as log_file:
                            output.fprint(
                                log_file.read(), color=output.GREY,
                                file=self.outfile)
                    else:
                        output.fprint("<log file missing>", file=self.outfile,
                                      color=output.YELLOW)

        return 0

    def update_results(self, pav_cfg: dict, tests: List[TestRun],
                       log_file: IO[str], save: bool = False) -> bool:
        """Update each of the given tests with the result section from the
        current version of their configs. Then rerun result processing and
        update the results in the test object (but change nothing on disk).

        :param pav_cfg: The pavilion config.
        :param tests: A list of test objects to update.
        :param log_file: The logfile to log results to. May be None.
        :param save: Whether to save the updated results to the test's result
                     log. It will not update the general result log.
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
            updates = {}

            for section in 'result_parse', 'result_evaluate':
                # Try to resolve the updated result section of the config using
                # the original variable values.
                try:
                    updates[section] = reslvr.resolve_section_values(
                        component=cfg[section],
                        var_man=test.var_man,
                    )
                except resolver.TestConfigError as err:
                    output.fprint(
                        "Test '{}' had a {} section that could not be "
                        "resolved with it's original variables: {}"
                        .format(test.name, section, err.args[0]),
                        file=self.errfile, color=output.RED)
                    return False
                except RuntimeError as err:
                    output.fprint(
                        "Unexpected error updating {} section for test "
                        "'{}': {}".format(section, test.name, err.args[0]),
                        color=output.RED, file=self.errfile)
                    return False

            # Set the test's result section to the newly resolved one.
            test.config['result_parse'] = updates['result_parse']
            test.config['result_evaluate'] = updates['result_evaluate']

            try:
                result.check_config(
                    test.config['result_parse'],
                    test.config['result_evaluate'])

            except result.ResultError as err:
                output.fprint(
                    "Error found in results configuration: {}"
                    .format(err.args[0]),
                    color=output.RED, file=self.errfile)
                return False

            # The new results will be attached to the test (but not saved).
            results = test.gather_results(test.results.get('return_value', 1),
                                          regather=True, log_file=log_file)

            if save:
                test.save_results(results)
                with test.results_log.open('a') as log_file:
                    log_file.write(
                        "Results were re-ran and saved on {}\n"
                        .format(datetime.datetime.today()
                                .strftime('%m-%d-%Y')))
                    log_file.write("See results.json for updated results.\n")

        return True
