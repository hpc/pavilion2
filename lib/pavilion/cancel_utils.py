"""Functions for cancelling groups of tests or jobs."""

import io
from collections import defaultdict
from typing import List, TextIO
import time

from pavilion import schedulers
from pavilion import utils
from pavilion.test_run import TestRun, load_tests
from pavilion import output


def cancel_jobs(pav_cfg, tests: List[TestRun], errfile: TextIO = None) -> List[dict]:
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


def cancel_tests(pav_cfg, tests: List, outfile: TextIO):
    """Cancel all of the given tests, printing useful user messages and error information."""

    user = utils.get_login()

    # Cancel each test. Note that this does not cancel test jobs or builds.
    cancelled_test_info = []
    for test in tests:
        # Don't try to cancel complete tests
        if not test.complete:
            test.cancel("Cancelled via cmdline by user '{}'".format(user))
            cancelled_test_info.append(test)

    if cancelled_test_info:
        output.draw_table(
            outfile=outfile,
            fields=['name', 'id'],
            rows=[{'name': test.name, 'id': test.full_id}
                  for test in cancelled_test_info])
    else:
        output.fprint("No tests needed to be cancelled.",
                      file=outfile)
        return 0

    output.fprint("Giving tests a moment to quit.",
                  file=outfile)
    time.sleep(TestRun.RUN_WAIT_MAX)

    job_cancel_info = cancel_jobs(pav_cfg, tests, outfile)

    if job_cancel_info:
        output.draw_table(
            outfile=outfile,
            fields=['scheduler', 'job', 'success', 'msg'],
            rows=job_cancel_info,
            title="Cancelled {} jobs.".format(len(job_cancel_info)),
        )
    else:
        output.fprint("No jobs needed to be cancelled.", file=outfile)

    return 0
