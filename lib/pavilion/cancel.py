"""Functions for cancelling groups of tests or jobs."""

import io
from collections import defaultdict
from typing import List, TextIO

from pavilion import schedulers
from pavilion.test_run import TestRun, load_tests


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
