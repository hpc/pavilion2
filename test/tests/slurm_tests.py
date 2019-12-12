import subprocess
import time
import unittest

from pavilion import config
from pavilion import plugins
from pavilion import result_parsers
from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion.test_config.file_format import TestConfigLoader
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase

_HAS_SLURM = None


def has_slurm():
    global _HAS_SLURM
    if _HAS_SLURM is None:
        try:
            _HAS_SLURM = subprocess.call(['sinfo', '--version'],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL) == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            _HAS_SLURM = False

    return _HAS_SLURM


class SlurmTests(PavTestCase):

    # How long to wait for tests to complete
    TEST_TIMEOUT = 30

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Do a default pav config, which will load from
        # the pavilion lib path.
        self.pav_config = config.PavilionConfigLoader().load_empty()

    def setUp(self):

        plugins.initialize_plugins(self.pav_config)

    def tearDown(self):

        plugins._reset_plugins()

    def _get_job(self, match):
        """Get a job id that from a job that contains match.
        :param str match: The string to look for in the job id.
        :return: A job id.
        """

        jobs = subprocess.check_output(['scontrol', 'show', 'jobs', '-o'])
        jobs = jobs.decode('utf-8').split('\n')

        id_field = 'JobId='

        for job in jobs:
            if match in job:
                id_pos = job.find(id_field)
                if id_pos >= 0:
                    id_pos += len(id_field)
                else:
                    self.fail(
                        "Could not find job id in matched job: {}"
                        .format(job)
                    )

                end_pos = job.find(' ', id_pos)
                return job[id_pos:end_pos]

        else:
            self.fail(
                "Could not find a job matching {} to impersonate."
                .format(match))

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_job_status(self):
        """Make sure we can get a slurm job status."""

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg, name='slurm_job_status', finalize=False)

        slurm = schedulers.get_scheduler_plugin('slurm')

        # Steal a running job's ID, and then check our status.
        test.status.set(STATES.SCHEDULED, "not really though.")
        test.job_id = self._get_job('JobState=RUNNING')
        status = slurm.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHEDULED)
        self.assertIn('RUNNING', status.note)

        # Steal a canceled jobs id
        test.status.set(STATES.SCHEDULED, "not really though.")
        test.job_id = self._get_job('JobState=CANCELLED')
        sched_status = slurm.job_status(self.pav_cfg, test)
        self.assertEqual(sched_status.state, STATES.SCHED_CANCELLED)
        status = test.status.current()
        self.assertEqual(status.state, STATES.SCHED_CANCELLED)

        # Check another random state. In this case, all pavilion will
        # just consider the test still scheduled.
        test.status.set(STATES.SCHEDULED, "not really though.")
        test.job_id = self._get_job('JobState=COMPLETED')
        sched_status = slurm.job_status(self.pav_cfg, test)
        self.assertEqual(sched_status.state, STATES.SCHEDULED)
        self.assertIn('COMPLETED', sched_status.note)

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_sched_vars(self):
        """Make sure the scheduler vars are reasonable when not on a node."""

        slurm = schedulers.get_scheduler_plugin('slurm')

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg, name='slurm_vars', finalize=False)

        sched_conf = test.config['slurm']

        # Check all the variables to make sure they work outside an allocation,
        # or at least return a DeferredVariable
        var_list = list()
        for k, v in slurm.get_vars(sched_conf).items():
            # Make sure everything has a value of some sort.
            self.assertNotIn(v, ['None', ''])
            var_list.append(k)

        # Now check all the vars for real, when a test is running.
        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        # Ask for each var in our test comands.
        cfg['run']['cmds'] = [
            'echo "{var}={{{{sched.{var}}}}}"'.format(var=var)
            for var in var_list
        ]
        sched_vars = slurm.get_vars(sched_conf)
        test = self._quick_test(cfg, name='slurm_vars2', finalize=False,
                                sched_vars=sched_vars)

        slurm.schedule_test(self.pav_cfg, test)

        timeout = time.time() + self.TEST_TIMEOUT
        state = test.status.current()
        while time.time() < timeout:
            state = test.status.current()
            if state.state == STATES.COMPLETE:
                return 0
        else:
            self.fail("Test never completed. Has state: {}".format(state))

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_schedule_test(self):
        """Try to schedule a test."""

        slurm = schedulers.get_scheduler_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test')

        slurm.schedule_test(self.pav_cfg, test)

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)

        status = slurm.cancel_job(test)

        self.assertEqual(status.state, STATES.SCHED_CANCELLED)

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_node_range(self):
        """Make sure node ranges work properly."""

        slurm = schedulers.get_scheduler_plugin('slurm')

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'

        for num_nodes in '1-10000000', '1-all':
            # We're testing that everything works when we ask for a max number
            # of nodes and don't get them all.
            cfg['slurm']['num_nodes'] = num_nodes

            test = self._quick_test(cfg=cfg, name='slurm_test')
            test.build()

            slurm.schedule_test(self.pav_cfg, test)
            timeout = time.time() + self.TEST_TIMEOUT

            while time.time() < timeout:
                status = slurm.job_status(self.pav_cfg, test)
                if status.state == STATES.COMPLETE:
                    break
                time.sleep(.5)
            else:
                # We timed out.
                slurm.cancel_job(test)
                self.fail(
                    "Test {} at {} did not complete within {} secs with "
                    "num_nodes of {}."
                    .format(test.id, test.path, self.TEST_TIMEOUT, num_nodes))

        results = test.load_results()
        self.assertEqual(results['result'], result_parsers.PASS)

