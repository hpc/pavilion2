import subprocess
import yc_yaml as yaml
import time
import unittest
import logging
from pathlib import Path

import pavilion.schedulers
from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion import jobs
from pavilion import sys_vars
from pavilion.schedulers.plugins.slurm import Slurm
from pavilion.schedulers import SchedulerPluginAdvanced
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

        path = Path(__file__).parents[1]/'data'/'pav_config_dir'/'modes'/'local_slurm.yaml'
        with path.open() as slurm_mode:
            self.slurm_mode = yaml.load(path.open())

    def tearDown(self):

        plugins._reset_plugins()

    def _get_job(self, match, test):
        """Get a job id that from a job that contains match.
        :param str match: The string to look for in the job id.
        :return: A job id.
        """

        job_data = subprocess.check_output(['scontrol', 'show', 'jobs', '-o'])
        job_data = job_data.decode('utf-8').split('\n')

        id_field = 'JobId='

        for job_line in job_data:
            if match in job_line:
                id_pos = job_line.find(id_field)
                if id_pos >= 0:
                    id_pos += len(id_field)
                else:
                    self.fail(
                        "Could not find job id in matched job: {}"
                        .format(job_line)
                    )

                end_pos = job_line.find(' ', id_pos)

                job_id = job_line[id_pos:end_pos]
                job = jobs.Job.new(self.pav_cfg, [test])
                job.info = {
                    'id': job_id,
                    'sys_name': sys_vars.get_vars(True)['sys_name']
                }
                return job


    def test_node_list_parsing(self):
        """Make sure the node list regex matches what it's supposed to."""

        slurm = pavilion.schedulers.get_plugin('slurm')  # type: SchedulerPluginAdvanced

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

        snodes = Slurm.compress_node_list(nodes)

        self.assertEqual(
            snodes,
            'another000003,n0de[0020-0034,0047,0049,0099-1234],node00[1-2]'
        )

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_job_status(self):
        """Make sure we can get a slurm job status."""

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        cfg.update(self.slurm_mode)

        test = self._quick_test(cfg, name='slurm_job_status', finalize=False)

        slurm = pavilion.schedulers.get_plugin('slurm')

        # Steal a running job's ID, and then check our status.
        test.status.set(STATES.SCHEDULED, "not really though.")
        job = self._get_job('JobState=RUNNING', test)
        if job is not None:
            test.job = job
            status = slurm.job_status(self.pav_cfg, test)
            self.assertEqual(status.state, STATES.SCHED_RUNNING, 
                             msg="Got status {} instead".format(status))

        # Steal a canceled jobs id
        test = self._quick_test(cfg, name='slurm_job_status', finalize=False)
        test.status.set(STATES.SCHEDULED, "not really though.")
        test.job = self._get_job('JobState=CANCELLED', test)
        sched_status = slurm.job_status(self.pav_cfg, test)
        self.assertEqual(sched_status.state, STATES.SCHED_CANCELLED)
        status = test.status.current()
        self.assertEqual(status.state, STATES.SCHED_CANCELLED)

        # Check another random state. In this case, all pavilion will
        # just consider the test still scheduled.
        test = self._quick_test(cfg, name='slurm_job_status', finalize=False)
        test.status.set(STATES.SCHEDULED, "not really though.")
        test.job = self._get_job('JobState=COMPLETED', test)
        sched_status = slurm.job_status(self.pav_cfg, test)
        self.assertEqual(sched_status.state, STATES.SCHED_RUNNING)
        self.assertIn('COMPLETED', sched_status.note)

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_sched_vars(self):
        """Make sure the scheduler vars are reasonable when not on a node."""

        slurm = pavilion.schedulers.get_plugin('slurm')

        cfg = self._quick_test_cfg()
        cfg['scheduler'] = 'slurm'
        cfg.update(self.slurm_mode)
        test = self._quick_test(cfg, name='slurm_vars', finalize=False)

        sched_conf = test.config['schedule']

        # Check all the variables to make sure they work outside an allocation,
        # or at least return a DeferredVariable
        var_list = list()
        for k, v in slurm.get_initial_vars(sched_conf).items():
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
        cfg.update(self.slurm_mode)
        test = self._quick_test(cfg, name='slurm_vars2', finalize=False)
        slurm.schedule_tests(self.pav_cfg, [test])

        timeout = time.time() + self.TEST_TIMEOUT
        state = test.status.current()
        while time.time() < timeout:
            state = test.status.current()
            time.sleep(0.5)
            if state.state == STATES.COMPLETE:
                return 0
        else:
            self.fail("Test never completed. Has state: {}".format(state))

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_schedule(self):
        """Try to schedule a test. We don't actually need to get nodes."""

        slurm = pavilion.schedulers.get_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg.update(self.slurm_mode)
        cfg['schedule']['nodes'] = '5'
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test', finalize=False)

        slurm.schedule_tests(self.pav_cfg, [test])

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)

        self.assertIsNone(slurm.cancel(test.job.info))

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_cancel(self):
        """Try to schedule a test. We don't actually need to get nodes."""

        slurm = pavilion.schedulers.get_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg['run']['cmds'] = ['{{sched.test_cmd}} sleep 10']
        cfg.update(self.slurm_mode)
        cfg['schedule']['nodes'] = '5'
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test', finalize=False)

        slurm.schedule_tests(self.pav_cfg, [test])

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)
        # Pavilion will normally cancel the tests first, but we want to kill
        # the job hard. 
        self.assertIsNone(slurm.cancel(test.job.info))

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_slurm_params(self):
        """Launch a slurm job while setting all slurm options. (state options are left as defaults
        though)."""

        slurm = pavilion.schedulers.get_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg.update(self.slurm_mode)
        cfg['run']['cmds'] = ['{{sched.test_cmd}} hostname']
        cfg['schedule']['nodes'] = '5'
        cfg['schedule']['slurm'] = {
            'sbatch_extra': ['--comment "Hiya!"'],
            'srun_extra': ['--comment "Howdy!"'],
        }
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test', finalize=False)

        slurm.schedule_tests(self.pav_cfg, [test])

        status = slurm.job_status(self.pav_cfg, test)
        test.wait(10)

        self.assertEqual(test.results['result'], 'PASS')

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_mpirun(self):
        """Schedule a test but run it with mpirun.
        
        This test requires a working mpirun command. If you need to load one via a module, do so by 
        adding the module to the 'run.modules' list in `pav_config_dir/data/local_slurm.py`.
        """
 
        slurm = pavilion.schedulers.get_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg.update(self.slurm_mode)
        cfg['run']['cmds'] = ['{{sched.test_cmd}} hostname']
        cfg['schedule']['nodes'] = '5'
        cfg['schedule']['slurm'] = {
            'mpi_cmd': 'mpirun',
            'mpirun_bind_to': 'core',
            'mpirun_rank_by': 'core', 
            }
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test', finalize=False)

        slurm.schedule_tests(self.pav_cfg, [test])

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)
        test.wait(10)
        self.assertEqual(test.results['result'], 'PASS')

        slurm = pavilion.schedulers.get_plugin('slurm')
        cfg = self._quick_test_cfg()
        cfg.update(self.slurm_mode)
        cfg['run']['cmds'] = ['{{sched.test_cmd}} hostname']
        cfg['schedule']['nodes'] = '1'
        cfg['schedule']['slurm'] = {
            'mpi_cmd': 'mpirun',
            'mpirun_mca': ['btl self'], 
            }
        cfg['scheduler'] = 'slurm'
        test = self._quick_test(cfg=cfg, name='slurm_test', finalize=False)

        slurm.schedule_tests(self.pav_cfg, [test])

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)
        test.wait(10)
        self.assertEqual(test.results['result'], 'PASS')
