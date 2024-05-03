"""Print the test results for the given test/suite."""

from collections import defaultdict
import datetime
import errno
import io
import pathlib
import pprint
import shutil
from math import log10, floor
import re
from typing import List, IO, Union, Optional, Any

from pavilion.errors import TestConfigError, ResultError
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion import resolver
from pavilion import resolve
from pavilion import result
from pavilion import result_utils
from pavilion import utils
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from .base_classes import Command


def _num_digits(n: int) -> int: # pylint: disable=invalid-name
    """Only attempt to count number digits for ints, since
    precision error makes it nonsensical for floats."""
    if n < 0:
        n = abs(n)
    elif n == 0:
        return 1
    return floor(log10(n)) + 1


def format_numeric(value: Any) -> str:
    if isinstance(value, int) or isinstance(value, float):
        return "{:g}".format(value)
    else:
        return str(value)


class ResultsCommand(Command):
    """Plugin for result printing."""

    def __init__(self):

        super().__init__(
            name="result",
            aliases=['results'],
            description="Displays results from the given tests.",
            short_help="Displays results from the given tests."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            "-j", "--json",
            action="store_true", default=False,
            help="Give the results in json."
        )
        parser.add_argument(
            "--by-key", type=str, default='',
            help="Show the data in the given results key instead of the regular results. \n"
                 "Such keys must contain a dictionary of dictionaries. Use the `--by-key-compat`\n"
                 "argument to find out which keys are compatible. Results from all matched \n"
                 "tests are combined (duplicates are ignored).\n"
                 "Example `pav results --by-key=per_file`.")
        parser.add_argument(
            "--by-key-compat", action="store_true",
            help="List keys compatible with the '--by-key' argument.")
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-k", "--key", type=str, default='',
            help="Comma separated list of additional result keys to display. "
                 "Use ~ (tilda) in front of default key to remove from default list."
        )
        group.add_argument(
            "--list-keys", dest="list_keys",
            action="store_true", default=False,
            help="List all available keys for test run or series."
        )
        group.add_argument(
            "-f", "--full", action="store_true", default=False,
            help="Print results as json with all keys."
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
            help="Also show the result processing log. This is particularly "
                 "useful when re-parsing results, as the log is not saved."
        )
        parser.add_argument(
            '--all-passed', action='store_true', default=False,
            help="The result command will return zero only if all tests passed.")

        parser.add_argument(
            "tests",
            nargs="*",
            help="The tests to show the results for. Use 'last' to get the results of the last test"
                 " series you ran on this machine. Use 'all' to get results of all tests. By "
                 "default, 'all' will only display tests newer than 1 day ago, but setting any "
                 "filter argument will override that."
        )
        filters.add_test_filter_args(parser)

    def run(self, pav_cfg, args):
        """Print the test results in a variety of formats."""

        test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args,
                                verbose=self.errfile).paths
        tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, self.errfile)

        log_file = None
        if args.show_log and args.re_run:
            log_file = io.StringIO()

        skipped_reruns = [test for test in tests if test.finished is None]
        if args.re_run:
            tests = [test for test in tests if test.finished is not None]
            if not self.update_results(pav_cfg, tests, log_file, save=args.save):
                return errno.EINVAL

        serieses = ",".join(
            set([test.series for test in tests if test.series is not None]))
        results = result_utils.get_results(pav_cfg, tests)

        if args.by_key_compat:
            compat_keys = set()
            for rslt in results:
                for key in rslt:
                    if isinstance(rslt[key], dict):
                        for subkey, val in rslt[key].items():
                            if isinstance(val, dict):
                                compat_keys.add(key)
                                break

            if 'var' in compat_keys:
                compat_keys.remove("var")

            output.fprint(self.outfile, "Keys compatible with '--by-key'")
            for key in compat_keys:
                output.fprint(self.outfile, "  ", key)

            return 0

        elif args.by_key:
            reorged_results = defaultdict(dict)
            fields = set()
            for rslt in results:
                subtable = rslt.get(args.by_key, None)
                if not isinstance(subtable, dict):
                    continue
                for key, values in subtable.items():
                    if not isinstance(values, dict):
                        continue
                    reorged_results[key].update(values)
                    fields = fields.union(values.keys())

            fields = ['--tag'] + sorted(fields)
            flat_results = []
            for key, values in reorged_results.items():
                values['--tag'] = key
                flat_results.append(values)

            flat_results.sort(key=lambda val: val['--tag'])

            field_info = {
                '--tag': {'title': ''},
            }

        else:
            fields = self.key_fields(args)
            flat_results = []
            all_passed = True
            for rslt in results:
                flat_results.append(utils.flatten_dictionary(rslt))
                if rslt['result'] != TestRun.PASS:
                    all_passed = False
            field_info = {
                'created': {'transform': output.get_relative_timestamp},
                'started': {'transform': output.get_relative_timestamp},
                'finished': {'transform': output.get_relative_timestamp},
                'duration': {'transform': output.format_duration},
                }


        if args.list_keys:
            flat_keys = result_utils.keylist(flat_results)
            flatter_keys = result_utils.make_key_table(flat_keys)

            fields = ["default", "common"]
            test_fields = [f for f in flat_keys.keys() if f not in fields]
            fields = fields + sorted(test_fields)
            title_str=f"Available keys for specified tests in {serieses}."

            output.draw_table(outfile=self.outfile,
                              fields=fields,
                              rows=flatter_keys,
                              border=True,
                              title=title_str)

        elif args.json or args.full:
            if not results:
                output.fprint(self.outfile, "Could not find any matching tests.",
                              color=output.RED)
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
            flat_sorted_results = utils.sort_table(args.sort_by, flat_results)

            title_str=f"Test Results: {serieses}."
            output.draw_table(
                outfile=self.outfile,
                field_info=field_info,
                fields=fields,
                rows=flat_sorted_results,
                title=title_str,
                default_format=format_numeric
            )

        if args.show_log:
            if log_file is not None:
                output.fprint(self.outfile, log_file.getvalue(), color=output.GREY)
            else:
                if len(results) > 1:
                    output.fprint(self.errfile,
                                  "Please give a single test id when requesting the full "
                                  "result log.", color=output.YELLOW)
                    return 1

                result_set = results[0]
                log_path = pathlib.Path(result_set['results_log'])
                output.fprint(self.outfile, "\nResult logs for test {}\n"
                              .format(result_set['name']))
                if log_path.exists():
                    with log_path.open() as log_file:
                        output.fprint(self.outfile, log_file.read(), color=output.GREY)
                else:
                    output.fprint(self.outfile, "Log file '{}' missing>".format(log_path),
                                  color=output.YELLOW)

        if skipped_reruns:
            output.fprint(
                self.errfile,
                "One or more of the requested tests never completed, and therefore have no "
                "results to 're-run'. Check the status and/or logs for these tests to see why:\n"
                + ", ".join([test.full_id for test in skipped_reruns]),
                color=output.YELLOW)

        if args.all_passed and not all_passed:
            return 1
        else:
            return 0

    def key_fields(self, args):
        """Update default fields with keys given as arguments.
        Returns a list of fields (columns) to be shown as output.
        """

        argkeys = args.key.replace(',', ' ').split()
        fields = result_utils.BASE_FIELDS.copy()

        for k in argkeys:
            if k.startswith('~'):
                key = k[1:]
                try:
                    fields.remove(key)
                except ValueError:
                    output.fprint(self.errfile,
                                    "Warning: Given key,{}, is not in default".format(k),
                                    color=output.YELLOW)
            else:
                fields.append(k)

        return fields

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

        rslvr = resolver.TestConfigResolver(pav_cfg)

        for test in tests:

            # Re-load the raw config using the saved name, sys_os, host,
            # and modes of the original test.
            try:
                ptests = rslvr.load(
                    tests=[test.name],
                    modes=test.config['modes'],
                    overrides=test.config['overrides'])
            except TestConfigError as err:
                output.fprint(self.errfile, "Test '{}' could not be reloaded."
                              .format(test.name), color=output.RED)
                output.fprint(self.errfile, err.pformat())
                return False

            ptest = ptests[0]

            # Set the test's result section to the newly resolved one.
            test.config['result_parse'] = ptest.config['result_parse']
            test.config['result_evaluate'] = ptest.config['result_evaluate']

            try:
                result.check_config(
                    test.config['result_parse'],
                    test.config['result_evaluate'])

            except ResultError as err:
                output.fprint(self.errfile, "Error found in results configuration.", err,
                              color=output.RED)
                return False

            if save:
                test.status.set(STATES.RESULTS, note="Re-running results.")

            # The new results will be attached to the test (but not saved).
            results = test.gather_results(test.results.get('return_value', 1),
                                          regather=True if not save else False,
                                          log_file=log_file)

            if save:
                test.save_results(results)
                with test.results_log.open('a') as log_file:
                    log_file.write(
                        "Results were re-ran and saved on {}\n"
                        .format(datetime.datetime.today()
                                .strftime('%m-%d-%Y')))
                    log_file.write("See results.json for updated results.\n")
                test.status.set(state=STATES.COMPLETE,
                                note="The test completed with result: {}"
                                     .format(results["result"]))

        return True
