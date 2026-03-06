"""Wait for the specified tests to finish, printing progress reports along
the way."""

import datetime
import os
import time
from typing import List

from pavilion import cmd_utils
from pavilion import status_utils
from pavilion.output import fprint
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from pavilion.test_ids import resolve_mixed_ids, SeriesID
from pavilion.series import TestSeries, TestSeriesError
from .base_classes import Command


def check_pgid(pgid):
    """Checks if pgid still exists. Returns false if pgid does not exist."""

    try:
        # PGID needs to be negative
        if pgid > 0:
            pgid = -1*pgid

        # No signal is sent, but an OS Error will be raised if the PID doesn't
        # exist
        os.kill(pgid, 0)
    except OSError:
        return False
    else:
        return True


class WaitCommand(Command):
    """A command to wait for test completion."""

    def __init__(self):
        super().__init__('wait', 'Wait for the specified test or series to '
                         'complete or fail and return the status.',
                         short_help="Wait for statuses of tests.")

    OUT_SILENT = 'silent'
    OUT_SUMMARY = 'summary'
    OUT_FULL = 'full'

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-t', '--timeout', action='store',
            help='Maximum time to wait for results in seconds. Default is to '
                 'wait indefinitely.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The ID(s) of the tests to check.  These may be any mix of '
                 'test IDs and series IDs.  If no value is provided, the most '
                 'recent series submitted by this user is checked.'
        )

        parser.add_argument(
            '--update-period', '-p', action='store', type=int, default=5,
            help='How often to print status updates.')

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-s', '--silent',
            action='store_const', dest='out_mode', const=self.OUT_SILENT,
            help="No periodic status output."
        )
        group.add_argument(
            '--summary',
            action='store_const', dest='out_mode', const=self.OUT_SUMMARY,
            help="Prints a summary of the status."
        )

    def run(self, pav_cfg, args):
        """Wait for the requested tests to complete."""

        # get start time
        start_time = time.time()

        ids = resolve_mixed_ids(args.tests, auto_last=True)
        test_ids = ids["tests"]
        series_ids = ids["series"]

        if args.out_mode is None:
            args.out_mode = self.OUT_FULL

        tests = cmd_utils.get_tests_by_id(pav_cfg, test_ids, self.errfile)

        series = []
        for sid in series_ids:
            if sid == SeriesID("last"):
                series_obj = cmd_utils.load_last_series(pav_cfg, self.errfile)
                if series_obj is None:
                    output.fprint(self.errfile,
                        "The 'last' series was specified, by default or explicitely, but no "
                        "'last' series could be found.")
                    continue
            else:
                try:
                    series_obj = TestSeries.load(pav_cfg, sid, self.errfile)
                except TestSeriesError as err:
                    output.fprint(self.errfile, "Could not load series '{sid}': {err}")
                    continue

            series.append(series_obj)

        # determine timeout time, if there is one
        end_time = None
        if args.timeout is not None:
            end_time = start_time + float(args.timeout)

        self.wait(pav_cfg, series, tests, end_time, args.out_mode, args.update_period)
        return 0

    STATUS_UPDATE_PERIOD = 5  # seconds

    def wait(self, pav_cfg, series: List[TestSeries], tests: List[TestRun],
             end_time: float, out_mode: str, update_period: int) -> None:
        """Wait on each of the given tests to complete, printing a status
        message """

        base_tests = list(tests)
        base_series = list(series)

        tests = list(tests)

        def all_tests():
            """Return all tests we're waiting on, including tests from series."""

            tests = list(base_tests)
            for series in base_series:
                tests.extend(series.tests.values())

            return tests

        completed_tests = []
        newly_completed = []

        status_time = 0
        while (series or tests) and (end_time is None or time.time() < end_time):

            for test_state in tests:
                if test_state.complete:
                    completed_tests.append(test_state.id)
                    newly_completed.append(test_state)
                    tests.remove(test_state)

            for series_obj in series:
                for test_id, test_obj in series_obj.tests.items():
                    if test_id not in completed_tests and test_obj.complete:
                        completed_tests.append(test_id)
                        newly_completed.append(test_obj)

                if series_obj.complete:
                    series.remove(series_obj)

            # print status every 5 seconds
            if time.time() > status_time:
                status_time = time.time() + update_period

                if out_mode == self.OUT_FULL:
                    self._print_completed(pav_cfg, newly_completed)
                elif out_mode == self.OUT_SUMMARY:
                    self._print_test_state_summary(pav_cfg, all_tests())

                newly_completed = []

            time.sleep(1)

        if out_mode == self.OUT_FULL:
            self._print_completed(pav_cfg, newly_completed)
        if out_mode == self.OUT_SUMMARY:
            self._print_test_state_summary(pav_cfg, all_tests())
        fprint(self.outfile, '\n')

    last_summary_width = 1

    def _print_test_state_summary(self, pav_cfg, tests: List[TestRun]):
        """Print a summary of the status for the tests we're waiting on."""
        stats = status_utils.get_statuses(pav_cfg, tests)
        stats_out = []

        states = {}
        for test_state in stats:
            if test_state['state'] not in states.keys():
                states[test_state['state']] = 1
            else:
                states[test_state['state']] += 1
        status_counts = []
        for state, count in states.items():
            status_counts.append(state + ': ' + str(count))

        summary = ' | '.join(status_counts)
        fprint(self.outfile, ' '*self.last_summary_width, width=None, end='\r')
        fprint(self.outfile, summary, width=None, end='\r')
        self.last_summary_width = len(summary)

    def _print_completed(self, pav_cfg, tests: List[TestRun]):
        """Print a long form version of the tests status for each test we're waiting on."""
        stats = status_utils.get_statuses(pav_cfg, tests)

        fmt = '{:10s} {:10s} {:5s} {} {}'
        for test_state in stats:
            timestamp = datetime.datetime.fromtimestamp(test_state['time']).isoformat(" ")
            data = [str(test_state['test_id']),
                    test_state['state'],
                    test_state['result'],
                    timestamp,
                    test_state['name'],
                    ]
            fprint(self.outfile, fmt.format(*data), width=None)
