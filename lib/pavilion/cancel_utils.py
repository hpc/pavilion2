"""Functions for cancelling groups of tests or jobs."""

import io
from collections import defaultdict
from operator import attrgetter
from itertools import filterfalse
from typing import List, TextIO, Iterable, Union, Iterator
import time

from pavilion import schedulers
from pavilion import utils
from pavilion.test_run import TestRun, load_tests
from pavilion import output
from pavilion.config import PavConfig
from pavilion.micro import do


def not_completed(tests: Iterator[Union[TestRun, "TestSeries"]]) -> List[TestRun]:
    """Return a list of only those tests in the input sequence
    that have not completed running."""

    return list(filterfalse(attrgetter("complete"), tests))

def cancel_jobs(
        pav_cfg: PavConfig,
        tests: Iterable[TestRun],
        errfile: TextIO = None) -> List[dict]:
    """Collect all jobs from the given tests, and cancel them if all the tests
    attached to those jobs have been cancelled.

    :returns: A list of cancel information dictionaries. These will contain keys:
        'scheduler' (the scheduler name),
        'job' (the job info string),
        'success': True if cancelled
        'msg': Cancellation message.
    """

    if errfile is None:
        errfile = io.StringIO()

    jobs_by_sched = defaultdict(list)
    for test in tests:
        if test.job is not None and test.job not in jobs_by_sched[test.scheduler]:
            jobs_by_sched[test.scheduler].append(test.job)

    jobs_cancelled = []
    for sched_name, jobs in jobs_by_sched.items():
        sched = schedulers.get_plugin(sched_name)

        for job in jobs:
            job_tests = load_tests(pav_cfg, job.get_test_id_pairs(), errfile)

            if all([test.cancelled or test.complete for test in job_tests]):
                if job.info is None:
                    msg = "Cancel Failed - No such job"
                else:
                    msg = sched.cancel(job.info)
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

    return jobs_cancelled


SLEEP_PERIOD = 0.3
SERIES_WARN_EXPIRE = 60*60*24  # 24 hours


def cancel_tests(pav_cfg: PavConfig, tests: Iterable[TestRun], outfile: TextIO,
                 max_wait: float = 3.0, no_series_warning: bool = False) -> int:
    """Cancel all of the given tests, printing useful user messages and error information."""

    user = utils.get_login()

    tests = not_completed(tests)

    # Cancel each test. Note that this does not cancel test jobs or builds.
    cancelled_test_info = []

    for test in tests:
        # Don't try to cancel complete tests
        test.cancel("Cancelled via cmdline by user '{}'".format(user))
        cancelled_test_info.append(test)

    if len(cancelled_test_info) > 0:
        test_count = len(tests)
        output.draw_table(
            title="Cancelling {} test{}".format(test_count, 's' if test_count > 1 else ''),
            outfile=outfile,
            fields=['name', 'id', 'state', 'series'],
            rows=[{'name': test.name, 'id': test.full_id,
                   'state': test.status.current().state, 'series': test.series}
                  for test in cancelled_test_info])
    else:
        output.fprint(outfile, "No tests needed to be cancelled.")

        return 0

    timeout = time.time() + max_wait
    wait_tests = list(tests)
    wait_msg = True

    while len(wait_tests) > 0 and time.time() > timeout:
        wait_tests = not_completed(wait_tests)

        if len(wait_tests) > 0:
            if wait_msg:
                output.fprint(outfile, "Giving tests a moment to quit.", end='')
                wait_msg = False
            else:
                output.fprint(outfile, '.', end='')

            time.sleep(SLEEP_PERIOD)

    if not wait_msg:
        output.fprint(outfile, 'Done')

    output.fprint(outfile, '\n')

    job_cancel_info = cancel_jobs(pav_cfg, tests, outfile)

    if len(job_cancel_info) > 0:
        jobs = len(job_cancel_info)
        output.draw_table(
            outfile=outfile,
            fields=['scheduler', 'job', 'success', 'msg'],
            rows=job_cancel_info,
            title="Cancelling {} job{}.".format(jobs, 's' if jobs > 1 else ''),
        )
    else:
        output.fprint(outfile, "No jobs needed to be cancelled.")

    for test in tests:
        series_path = test.path/'series'
        if not series_path.exists():
            continue

        if not (series_path/'ALL_TESTS_STARTED').exists()  \
                and (series_path.stat().st_mtime + SERIES_WARN_EXPIRE > time.time()
                and not no_series_warning):
            output.fprint(outfile, "\nTests cancelled, but associated series "
                                   "may still be running.\n"
                                   "Use `pav series cancel` to cancel the series itself.")
            break

    return 0


def cancel_series(sers: Iterable["TestSeries"], errfile: TextIO = None) -> int:
    """Cancel all the series in the sequence."""

    running_series = not_completed(sers)

    do(lambda x: x.cancel(), running_series)

    return 0
