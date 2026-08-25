"""Unit tests for the PBS scheduler plugin.

These deliberately exercise only logic that runs without a live PBS cluster, so
they are safe in CI: scheduler variables, node list parsing, raw node data
transformation, qsub header generation, and config validators.
"""

import copy

import pavilion.schedulers
from pavilion.errors import SchedConfigError
from pavilion.schedulers.plugins.pbs import (PBS, PBSVars, QsubHeader, pbs_float,
                                             pbs_int, pbs_str, pbs_states,
                                             validate_pbs_states)
from pavilion.types import Nodes
from pavilion.unittest import PavTestCase


class PBSSchedTests(PavTestCase):
    """Tests for the PBS scheduler plugin that need no PBS installation."""

    # NOTE: PBS.get_initial_vars() shells out to 'pbsnodes' to build a node
    # inventory, so it cannot be used in CI. Instead build a normal (raw) test to
    # get a fully validated 'schedule' config, adjust its 'pbs' subsection, and
    # instantiate the variable class directly -- the same approach
    # sched_tests.SchedTests._check_examples uses to cover every scheduler.

    def _pbs_config(self, **pbs_opts):
        """Return a validated schedule config with 'schedule.pbs' options applied."""

        test = self._quick_test()
        config = copy.deepcopy(test.config['schedule'])
        config['pbs'].update(pbs_opts)

        return config

    def _pbs_vars(self, **pbs_opts):
        """Build PBS scheduler variables without needing a PBS installation."""

        # deferred=False so dfr_var_method values resolve to real values rather
        # than DeferredVariable placeholders.
        return PBSVars(self._pbs_config(**pbs_opts), nodes=Nodes({}), chunks=[],
                       node_list_id=0, deferred=False)

    def test_plugin_is_registered(self):
        """The PBS plugin should be available as a builtin scheduler."""

        self.assertIn('pbs', pavilion.schedulers.list_plugins())

        pbs_sched = pavilion.schedulers.get_plugin('pbs')
        self.assertIsInstance(pbs_sched, PBS)

    def test_queue_var_empty_when_unset(self):
        """queue() must return '' rather than None when no queue is configured.

        Pavilion's dfr_var_method rejects a None return value, which crashes job
        kickoff, so the empty string is the correct 'no queue' sentinel.
        """

        sched_vars = self._pbs_vars()

        self.assertEqual(sched_vars['queue'], '')
        self.assertIsNotNone(sched_vars['queue'])

    def test_queue_var_set(self):
        """queue() should return the configured queue."""

        self.assertEqual(self._pbs_vars(queue='workq')['queue'], 'workq')

    def test_mpiprocs_var(self):
        """mpiprocs() returns '' when unset and the value when set.

        mpiprocs is optional -- some clusters require it in the select statement
        and others reject it -- so the unset case must not produce None.
        """

        self.assertEqual(self._pbs_vars()['mpiprocs'], '')
        self.assertEqual(self._pbs_vars(mpiprocs='2')['mpiprocs'], '2')

    def test_srun_args_is_inert(self):
        """srun_args is a Slurm concept and must be empty under PBS.

        It is inherited from SchedulerVariables, so without an override a PBS test
        referencing {{sched.srun_args}} would silently receive Slurm flags.
        """

        self.assertEqual(self._pbs_vars(queue='workq')['srun_args'], '')

    def test_walltime_var(self):
        """walltime() should return the configured walltime."""

        self.assertEqual(self._pbs_vars(walltime='00:05:00')['walltime'], '00:05:00')

    def test_parse_node_list(self):
        """PBS_NODEFILE lists one entry per task slot; nodes must be deduplicated.

        Order must be preserved, and hostnames containing digits or hyphens must
        survive (an earlier implementation used isalpha() and dropped them).
        """

        self.assertEqual(PBS.parse_node_list([]), [])
        self.assertEqual(PBS.parse_node_list(None), [])

        # One entry per CPU slot collapses to unique nodes, order preserved.
        self.assertEqual(
            PBS.parse_node_list(['node02', 'node02', 'node01', 'node01']),
            ['node02', 'node01'])

        # Hostnames with digits and hyphens are valid and must be kept.
        self.assertEqual(
            PBS.parse_node_list(['x1002c6s2b0n1', 'x1002c6s2b0n1', 'nid-00123']),
            ['x1002c6s2b0n1', 'nid-00123'])

        # Empty entries are dropped.
        self.assertEqual(PBS.parse_node_list(['node01', '', 'node02']),
                         ['node01', 'node02'])

    def test_pbs_value_converters(self):
        """PBS reports unavailable values as the literal string 'N/A'."""

        self.assertIsNone(pbs_int('N/A'))
        self.assertIsNone(pbs_str('N/A'))
        self.assertIsNone(pbs_float('N/A'))

        self.assertEqual(pbs_int('4'), 4)
        self.assertEqual(pbs_str('free'), 'free')
        self.assertEqual(pbs_float('1.5'), 1.5)

    def test_pbs_states_parsing(self):
        """Compound PBS states are '+' separated and may carry a trailing marker."""

        self.assertEqual(pbs_states('free'), ['free'])
        self.assertEqual(pbs_states('job-busy+free'), ['job-busy', 'free'])

        # Trailing '*' and '$' markers are stripped.
        self.assertEqual(pbs_states('free*'), ['free'])
        self.assertEqual(pbs_states('busy$'), ['busy'])

    def test_validate_pbs_states(self):
        """State config values must be lowercase alphabetic, optionally hyphenated."""

        states = ['free', 'job-busy', 'resv-exclusive']
        self.assertEqual(validate_pbs_states(states), states)

        with self.assertRaises(SchedConfigError):
            validate_pbs_states(['Free'])

        with self.assertRaises(SchedConfigError):
            validate_pbs_states(['free!'])

    def test_config_defaults(self):
        """The pbs config section should supply sane defaults."""

        pbs_sched = pavilion.schedulers.get_plugin('pbs')
        _elems, _validators, defaults = pbs_sched._get_config_elems()

        self.assertEqual(defaults['nodes'], 1)
        self.assertEqual(defaults['tasks'], 1)
        self.assertEqual(defaults['walltime'], '00:01:00')
        self.assertEqual(defaults['avail_states'], ['free'])

        # Optional keys must default to unset, so they are omitted entirely from
        # the qsub command on clusters that do not use them.
        for key in ('queue', 'target', 'model', 'exclusive', 'mpiprocs',
                    'all_queue_nodes'):
            self.assertIsNone(defaults[key],
                              msg="'{}' must default to None (unset)".format(key))

    def test_mpiprocs_affects_job_sharing(self):
        """Tests differing in mpiprocs must not share an allocation.

        Anything that changes the qsub command has to be part of the job share
        key, or Pavilion merges those tests into one job and one of them silently
        receives the other's resources.
        """

        self.assertIn('pbs.mpiprocs', PBS.JOB_SHARE_KEY_ATTRS)
        self.assertIn('pbs.exclusive', PBS.JOB_SHARE_KEY_ATTRS)
        self.assertIn('pbs.qsub_extra', PBS.JOB_SHARE_KEY_ATTRS)

    def test_transform_raw_node_data(self):
        """pbsnodes output should map onto Pavilion's NodeInfo fields."""

        pbs_sched = pavilion.schedulers.get_plugin('pbs')
        sched_config = {'pbs': {'avail_states': ['free'],
                                'up_states': ['free', 'job-busy'],
                                'reserved_states': ['resv-exclusive']}}

        node_data = {
            'node01': {
                'vnode': 'node01',
                'arch': 'linux',
                'state': 'free',
                'ncpus': '4',
                'mem': '4194304kb',
                'queue': 'workq',
            }
        }

        node_info = pbs_sched._transform_raw_node_data(sched_config, node_data, {})

        self.assertIsInstance(node_info, dict)
        self.assertEqual(node_info['name'], 'node01')
        self.assertEqual(node_info['cpus'], 4)
        self.assertEqual(node_info['mem'], 4194304 * 1024)
        self.assertEqual(node_info['states'], ['free'])
        self.assertTrue(node_info['up'])
        self.assertTrue(node_info['available'])

    def test_transform_raw_node_data_down_node(self):
        """A node in a state outside up_states must not be reported as up."""

        pbs_sched = pavilion.schedulers.get_plugin('pbs')
        sched_config = {'pbs': {'avail_states': ['free'],
                                'up_states': ['free', 'job-busy'],
                                'reserved_states': ['resv-exclusive']}}

        node_data = {'node02': {'vnode': 'node02', 'state': 'down', 'ncpus': '4'}}

        node_info = pbs_sched._transform_raw_node_data(sched_config, node_data, {})

        self.assertFalse(node_info['up'])
        self.assertFalse(node_info['available'])

    def test_transform_raw_node_data_busy_node(self):
        """A job-busy node is 'up' but not 'available'."""

        pbs_sched = pavilion.schedulers.get_plugin('pbs')
        sched_config = {'pbs': {'avail_states': ['free'],
                                'up_states': ['free', 'job-busy'],
                                'reserved_states': ['resv-exclusive']}}

        node_data = {'node03': {'vnode': 'node03', 'state': 'job-busy',
                                'ncpus': '4'}}

        node_info = pbs_sched._transform_raw_node_data(sched_config, node_data, {})

        self.assertTrue(node_info['up'])
        self.assertFalse(node_info['available'])

    def _qsub_lines(self, job_name='pav_test', **pbs_opts):
        """Render the qsub header lines for the given pbs config."""

        config = self._pbs_config(**pbs_opts)
        sched_vars = PBSVars(config, nodes=Nodes({}), chunks=[], node_list_id=0,
                             deferred=False)

        header = QsubHeader(job_name, config, sched_vars,
                            nodes=None, node_range=(1, 1))

        return header._kickoff_lines()

    def test_qsub_header_job_name_sanitized(self):
        """PBS job names must start with a letter and be alphanumeric/_/- only."""

        lines = self._qsub_lines(job_name='suite.test-1')
        self.assertIn('#PBS -N suite_test-1', lines)

        # A name starting with a non-letter gets a 'pav_' prefix.
        lines = self._qsub_lines(job_name='1bad')
        self.assertIn('#PBS -N pav_1bad', lines)

    def test_qsub_header_queue_and_extra(self):
        """Queue and qsub_extra should be emitted as header lines."""

        lines = self._qsub_lines(queue='workq',
                                 qsub_extra=['-l foo=bar'])

        self.assertIn('#PBS -q workq', lines)
        self.assertIn('#PBS -l foo=bar', lines)

    def test_qsub_header_exclusive(self):
        """'exclusive' should request exclusive host placement."""

        self.assertIn('#PBS -l place=exclhost:scatter',
                      self._qsub_lines(exclusive='true'))

        self.assertNotIn('#PBS -l place=exclhost:scatter',
                         self._qsub_lines())
