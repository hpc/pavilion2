"""Cancels tests as prescribed by the user."""
import collections
import errno
import os
import signal
import time

from pavilion import output
from pavilion import schedulers
from pavilion import series
from pavilion.test_run import TestRun, load_tests
from .base_classes import Command
from ..exceptions import TestRunError


class CancelCommand(Command):
    """Cancel a set of commands using the appropriate scheduler."""

    def __init__(self):
        super().__init__(
            'cancel',
            'Cancel a test, tests, or test series.',
            short_help="Cancel a test, tests, or test series."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-s', '--status', action='store_true', default=False,
            help='Prints status of cancelled jobs.'
        )
        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Prints status of cancelled jobs in json format.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to cancel. These may be any mix of '
                 'test IDs and series IDs. If no value is provided, the most '
                 'recent series submitted by the user is cancelled. '
        )

    def run(self, pav_cfg, args):
        """Cancel the given tests."""

        if not args.tests:
            # Get the last series ran by this user.
            series_id = series.load_user_series_id(pav_cfg)
            if series_id is not None:
                args.tests.append(series_id)

        tests = []
        for test_id in args.tests:
            if test_id.startswith('s'):
                try:
                    test_series = series.TestSeries.load(pav_cfg, test_id)
                    series_pgid = test_series.pgid
                    tests.extend(test_series.tests.values())
                except series.errors.TestSeriesError as err:
                    output.fprint(
                        "Series {} could not be found.\n{}"
                        .format(test_id, err.args[0]),
                        file=self.errfile, color=output.RED)
                    return errno.EINVAL
                except ValueError as err:
                    output.fprint(
                        "Series {} is not a valid series.\n{}"
                        .format(test_id, err.args[0]),
                        color=output.RED, file=self.errfile)
                    return errno.EINVAL

                try:
                    # if there's a series PGID, kill the series PGID
                    if series_pgid:
                        os.killpg(series_pgid, signal.SIGTERM)
                        output.fprint('Killed process {}, which is series {}.'
                                      .format(series_pgid, test_id),
                                      file=self.outfile)

                except ProcessLookupError:
                    output.fprint("Unable to kill {}. No such process: {}"
                                  .format(test_id, series_pgid),
                                  color=output.RED, file=self.errfile)
            else:
                try:
                    tests.append(TestRun.load_from_raw_id(pav_cfg, test_id))
                except TestRunError as err:
                    output.fprint(
                        "Test {} is not a valid test.\n{}".format(test_id, err),
                        file=self.errfile, color=output.RED
                    )
                    return errno.EINVAL

        output.fprint("Found {} tests to try to cancel.".format(len(tests)),
                      file=self.outfile)

        tests_by_sched = collections.defaultdict(list)
        # Cancel each test. Note that this does not cancel test jobs or builds.
        cancelled_tests = []
        for test in tests:
            # Don't try to cancel complete tests
            if not test.complete:
                test.cancel("Cancelled via cmdline.")
                cancelled_tests.append(test)
                tests_by_sched[test.scheduler].append(test)

        if cancelled_tests:
            output.draw_table(
                outfile=self.outfile,
                fields=['name', 'id'],
                rows=[{'name': test.name, 'id': test.full_id}
                      for test in cancelled_tests])
        else:
            output.fprint("No tests needed to be cancelled.",
                          file=self.outfile)
            return 0

        output.fprint("Giving tests a moment to quit.",
                      file=self.outfile)
        time.sleep(TestRun.RUN_WAIT_MAX)

        # Figure out which jobs to cancel, and cancel them.
        jobs_cancelled = []
        for sched_name, sched_tests in tests_by_sched.items():
            jobs = []
            try:
                scheduler = schedulers.get_plugin(sched_name)
            except schedulers.SchedulerPluginError:
                output.fprint("Skipping job cancellation for unknown scheduler '{}'"
                              .format(sched_name), file=self.outfile)
                continue

            # Gather the unique jobs
            for test in sched_tests:
                if test.job not in jobs and test.job is not None:
                    jobs.append(test.job)

            # Find the tests for each unique job, and make sure they're all cancelled.
            for job in jobs:
                job_tests = load_tests(pav_cfg, job.get_test_id_pairs(),
                                       self.errfile)

                if all([test.cancelled or test.complete for test in job_tests]):
                    msg = scheduler.cancel(job.info)
                    success = True if msg is None else False
                    if msg is None:
                        msg = 'Cancel Succeeded'
                    jobs_cancelled.append({
                        'scheduler': sched_name,
                        'job': str(job),
                        'success': str(success),
                        'msg': msg,
                    })
                else:
                    jobs_cancelled.append({
                        'scheduler': sched_name,
                        'job': str(job),
                        'success': False,
                        'msg': "Uncancelled tests still running."})

        if jobs_cancelled:
            output.draw_table(
                outfile=self.outfile,
                fields=['scheduler', 'job', 'success', 'msg'],
                rows=jobs_cancelled,
                title="Cancelled {} jobs.".format(len(jobs_cancelled)),
            )
        else:
            output.fprint("No jobs needed to be cancelled.", file=self.outfile)

        return 0
