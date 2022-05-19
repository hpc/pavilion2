"""Print the test results for the given test/suite."""

import datetime
import errno
import io
import pathlib
import pprint
import shutil
from typing import List, IO

from pavilion.errors import TestConfigError
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import resolver
from pavilion import resolve
from pavilion import result
from pavilion import result_utils
from pavilion import utils
from pavilion.status_file import STATES
from pavilion.test_run import (TestRun)
from .base_classes import Command


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
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-k", "--key", type=str, default='',
            help="Comma separated list of additional result keys to display."
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

        test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile)
        tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, self.errfile)

        log_file = None
        if args.show_log and args.re_run:
            log_file = io.StringIO()

        if args.re_run:
            if not self.update_results(pav_cfg, tests, log_file, save=args.save):
                return errno.EINVAL

        results = result_utils.get_results(pav_cfg, tests)
        flat_results = []
        for rslt in results:
            flat_results.append(utils.flatten_dictionary(rslt))

        field_info = {}

        if args.list_keys:
            flat_keys = result_utils.keylist(flat_results)
            flatter_keys = result_utils.make_key_table(flat_keys)

            fields = ["default", "common"]
            test_fields = [f for f in flat_keys.keys() if f not in fields]
            fields = fields + sorted(test_fields)

            output.draw_table(outfile=self.outfile,
                              field_info=field_info,
                              fields=fields,
                              rows=flatter_keys,
                              border=True,
                              title="AVAILABLE KEYS")

        elif args.json or args.full:
            if not results:
                output.fprint(self.outfile, "Could not find any matching tests.",
                              color=output.RED)
                return errno.EINVAL

            width = shutil.get_terminal_size().columns or 80

            for rslt in results:
                rslt['finish_date'] = output.get_relative_timestamp(
                                      rslt['finished'], fullstamp=True)

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
                                      color=output.RED)
                else:
                    fields.append(k)

            field_info = {
                'created': {'transform': output.get_relative_timestamp},
                'started': {'transform': output.get_relative_timestamp},
                'finished': {'transform': output.get_relative_timestamp},
                'duration': {'transform': output.format_duration},
                }

            output.draw_table(
                outfile=self.outfile,
                field_info=field_info,
                fields=fields,
                rows=flat_results,
                title="Test Results"
            )

        if args.show_log:
            if log_file is not None:
                output.fprint(self.outfile, log_file.getvalue(), color=output.GREY)
            else:
                if len(results) > 1:
                    output.fprint(self.errfile,
                                  "Please give a single test id when requesting the full"
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
            except TestConfigError as err:
                output.fprint(self.errfile, "Test '{}' could not be found: {}"
                              .format(test.name, err), color=output.RED)
                return False

            # These conditions guard against unexpected results from
            # load_raw_configs. They may not be possible.
            if not configs:
                output.fprint(self.errfile, "No configs found for test '{}'. Skipping update."
                              .format(test.name), color=output.YELLOW)
                continue
            elif len(configs) > 1:
                output.fprint(self.errfile, "Test '{}' somehow matched multiple configs."
                                            "Skipping update.".format(test.name),
                              color=output.YELLOW)
                continue

            cfg = configs[0]
            updates = {}

            for section in 'result_parse', 'result_evaluate':
                # Try to resolve the updated result section of the config using
                # the original variable values.
                try:
                    updates[section] = resolve.section_values(
                        component=cfg[section],
                        var_man=test.var_man,
                    )
                except TestConfigError as err:
                    output.fprint(self.errfile, "Test '{}' had a {} section that could not be "
                                                "resolved with it's original variables: {}"
                                  .format(test.name, section, err), color=output.RED)
                    return False
                except RuntimeError as err:
                    output.fprint(self.errfile, "Unexpected error updating {} section for test "
                                                "'{}': {}".format(section, test.name,
                                                                  err), color=output.RED)
                    return False

            # Set the test's result section to the newly resolved one.
            test.config['result_parse'] = updates['result_parse']
            test.config['result_evaluate'] = updates['result_evaluate']

            try:
                result.check_config(
                    test.config['result_parse'],
                    test.config['result_evaluate'])

            except result.ResultError as err:
                output.fprint(self.errfile, "Error found in results configuration: {}"
                              .format(err), color=output.RED)
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
