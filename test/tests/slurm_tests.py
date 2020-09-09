import subprocess
import time
import unittest
import logging

from pavilion import config
from pavilion import plugins
from pavilion.result import parsers
from pavilion import schedulers
from pavilion.plugins.sched.slurm import Slurm
from pavilion.status_file import STATES
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

    def test_node_list_parsing(self):
        """Make sure the node list regex matches what it's supposed to."""

        slurm = schedulers.get_plugin('slurm')  # type: Slurm

        examples = (
            (None, []),
            ('', []),
            ('ab03', ['ab03']),
            ('ab-bc[3-004]', ['ab-bc3', 'ab-bc4']),
            ('ab_bc[03-10]',
             ['ab_bc{:02d}'.format(d) for d in range(3, 11)]),
            ('n[003-143]', ['n{:03d}'.format(d) for d in range(3, 144)]),
            # Duplicates are accepted
            ('nid03,nid[03-04]', ['nid03', 'nid03', 'nid04']),
            ('nid03,nid[04-06],nid[12-33]',
             ['nid03', 'nid04', 'nid05', 'nid06'] +
             ['nid{:02d}'.format(d) for d in range(12, 34)]),
        )

        for ex, answer in examples:
            nodes = slurm.parse_node_list(ex)
            self.assertEqual(nodes, answer)

        bad_examples = (
            ('n03d',  "Trailing characters"),
            ('nid03!@#', "Trailing junk (whole string match)."),
            ('n03.n04', "Not comma separated"),
            ('n[03', "No closing bracket"),
            ('n03]', "No open bracket"),
            ('nid[12-03]', "Out of order range"),
        )

        for ex, problem in bad_examples:
            with self.assertRaises(
                    ValueError,
                    msg="Did not throw error for {}".format(problem)):
                slurm.parse_node_list(ex)

    def test_node_list_shortening(self):
        """Check that node lists are shortened properly."""

        nodes = (
            ['node001', 'node002', 'n0de047', 'n0de49'] +
            ['n0de{:04d}'.format(i) for i in range(20, 35)] +
            ['n0de{:04d}'.format(i) for i in range(99, 1235)] +
            ['baaaad'] +
            ['another000003'])

        snodes = Slurm.short_node_list(nodes, logging.getLogger("discard"))

        self.assertEqual(
            snodes,
            'another000003,n0de[0020-0034,0047,0049,0099-1234],node00[1-2]'
        )

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_job_status(self):
        """Make sure we can get a slurm job status."""

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg, name='slurm_job_status', finalize=False)

        slurm = schedulers.get_plugin('slurm')

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

        slurm = schedulers.get_plugin('slurm')

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg, name='slurm_vars', finalize=False)

        sched_conf = test.config['slurm']

        # Check all the variables to make sure they work outside an allocation,
        # or at least return a DeferredVariable
        var_list = list()
        for k, v in slurm.get_vars(sched_conf).items():
            # Make sure everything has a value of some sort.
            self.assertNotIn(v, ['None', '', []])
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
    def test_schedule(self):
        """Try to schedule a test. We don't actually need to get nodes."""

        slurm = schedulers.get_plugin('slurm')
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

        slurm = schedulers.get_plugin('slurm')

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'

        for num_nodes in '1-10000000', '1-all':
            # We're testing that everything works when we ask for a max number
            # of nodes and don't get them all.
            cfg['slurm']['num_nodes'] = num_nodes

            test = self._quick_test(cfg=cfg, name='slurm_test')

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
        self.assertEqual(results['result'], test.PASS)

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_include_exclude(self):
        """Test that we can schedule tests that require or exclude nodes."""

        slurm = schedulers.get_plugin('slurm')

        dummy_test = self._quick_test(build=False, finalize=False)
        svars = slurm.get_vars(dummy_test.config['slurm'])
        up_nodes = svars['node_up_list']

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        cfg['slurm']['num_nodes'] = '2'
        cfg['slurm']['include_nodes'] = up_nodes[1]
        cfg['slurm']['exclude_nodes'] = up_nodes[2]

        test = self._quick_test(cfg, finalize=False)

        # We mainly care if this step completes successfully.
        slurm.schedule_test(self.pav_cfg, test)
        try:
            test.wait(timeout=5)
        except TimeoutError:
            slurm.cancel_job(test)
