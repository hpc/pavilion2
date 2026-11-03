"""Unit tests for the PBS scheduler plugin.

These deliberately exercise only logic that runs without a live PBS cluster, so
they are safe in CI: scheduler variables, node list parsing, raw node data
transformation, qsub header generation, and config validators.
"""

import copy
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pavilion.schedulers
from pavilion.errors import SchedConfigError, SchedulerPluginError
from pavilion.schedulers.plugins import pbs as pbs_mod
from pavilion.schedulers.plugins.pbs import (PBS, PBSVars, QsubHeader, pbs_float,
                                             pbs_int, pbs_str, pbs_states,
                                             validate_pbs_states, validate_mem,
                                             validate_exclusive, pbs_resv_queue,
                                             pbs_submit_queue, pbs_node_reservations,
                                             EXCLUSIVE_DEFAULT_PLACE,
                                             DEFAULT_QUEUE_FALLBACK)
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

        # Run the options through the plugin's own validators, as Pavilion does for
        # a real test config, so tests see the values the plugin really receives.
        _elems, validators, _defaults = \
            pavilion.schedulers.get_plugin('pbs')._get_config_elems()
        for key, value in pbs_opts.items():
            validator = validators.get(key)
            if validator is not None and value is not None and not isinstance(value, list):
                value = validator(value)
            config['pbs'][key] = value

        return config

    def setUp(self):
        # The server's default queue is looked up once and cached. Start every test
        # with an empty cache so no test depends on another (or on a real PBS server).
        super().setUp()
        pbs_mod._default_queue_cache.clear()

    def tearDown(self):
        pbs_mod._default_queue_cache.clear()
        super().tearDown()

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

    def test_queue_var_default_queue_when_unset(self):
        """With no queue configured, queue() is the server's default queue.

        Jobs with no queue go to the PBS server's default_queue, so that is what
        {{sched.queue}} reports. It is never None: Pavilion's dfr_var_method
        rejects a None return value, which crashes job kickoff.
        """

        sched_vars = self._pbs_vars()
        server = json.dumps({'Server': {'pbs-server': {'default_queue': 'workq'}}})
        with mock.patch.object(pbs_mod.subprocess, 'check_output',
                               return_value=server.encode()):
            self.assertEqual(sched_vars['queue'], 'workq')

    def test_queue_var_fallback_without_pbs(self):
        """If the server can't be asked, queue() falls back to 'normal', never None."""

        sched_vars = self._pbs_vars()
        with mock.patch.object(pbs_mod.subprocess, 'check_output',
                               side_effect=OSError('no qstat')):
            queue = sched_vars['queue']

        self.assertEqual(queue, DEFAULT_QUEUE_FALLBACK)
        self.assertIsNotNone(queue)

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
        for key in ('queue', 'target', 'model', 'exclusive', 'mpiprocs', 'mem',
                    'ngpus', 'all_queue_nodes'):
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
        self.assertIn('pbs.mem', PBS.JOB_SHARE_KEY_ATTRS)
        self.assertIn('pbs.ngpus', PBS.JOB_SHARE_KEY_ATTRS)

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

    def test_mem_and_ngpus_vars(self):
        """mem() and ngpus() return '' when unset and the value when set."""

        sched_vars = self._pbs_vars()
        self.assertEqual(sched_vars['mem'], '')
        self.assertEqual(sched_vars['ngpus'], '')

        sched_vars = self._pbs_vars(mem='4gb', ngpus=2)
        self.assertEqual(sched_vars['mem'], '4gb')
        self.assertEqual(sched_vars['ngpus'], '2')

    def test_validate_mem(self):
        """mem takes a PBS size: a whole number with an optional unit."""

        for good in ('4gb', '512mb', '1024kb', '2GB', '100', '8w', '1tb'):
            self.assertEqual(validate_mem(good), good)

        for unset in (None, '', '  '):
            self.assertIsNone(validate_mem(unset))

        for bad in ('4 gb', '4.5gb', 'lots', '-1gb', '4gib'):
            with self.assertRaises(SchedConfigError, msg=bad):
                validate_mem(bad)

    def test_validate_exclusive(self):
        """exclusive takes a boolean or a literal PBS place spec."""

        for true in ('true', 'yes', 'on', '1', 'True'):
            self.assertEqual(validate_exclusive(true), EXCLUSIVE_DEFAULT_PLACE)

        for false in (None, 'false', 'no', 'off', '0', 'none', ''):
            self.assertIsNone(validate_exclusive(false))

        for spec in ('exclhost:scatter', 'excl:vscatter', 'pack:excl', 'group=switch'):
            self.assertEqual(validate_exclusive(spec), spec)

        for bad in ('excl vscatter', 'excl;rm', '"excl"'):
            with self.assertRaises(SchedConfigError, msg=bad):
                validate_exclusive(bad)

    def test_qsub_header_exclusive_place_spec(self):
        """A place spec is passed through as-is; 'false' emits no place line."""

        self.assertIn('#PBS -l place=excl:vscatter',
                      self._qsub_lines(exclusive='excl:vscatter'))

        self.assertFalse([line for line in self._qsub_lines(exclusive='false')
                          if line.startswith('#PBS -l place=')])

    def test_reservation_queue(self):
        """A reservation is a queue; it wins over the configured queue."""

        self.assertEqual(pbs_resv_queue('R123.pbs-server'), 'R123')
        self.assertEqual(pbs_resv_queue('S45'), 'S45')

        config = self._pbs_config(queue='workq')
        self.assertEqual(pbs_submit_queue(config), 'workq')

        config['reservation'] = 'R123.pbs-server'
        self.assertEqual(pbs_submit_queue(config), 'R123')

    def test_qsub_header_in_reservation(self):
        """In a reservation the job goes to its queue and sets no place spec.

        qsub rejects a job whose place spec conflicts with the reservation's own.
        """

        config = self._pbs_config(queue='workq', exclusive='true')
        config['reservation'] = 'R123.pbs-server'
        sched_vars = PBSVars(config, nodes=Nodes({}), chunks=[], node_list_id=0,
                             deferred=False)
        lines = QsubHeader('pav_test', config, sched_vars, nodes=None,
                           node_range=(1, 1))._kickoff_lines()

        self.assertIn('#PBS -q R123', lines)
        self.assertFalse([line for line in lines if line.startswith('#PBS -l place=')])

    def test_node_reservations(self):
        """A node's 'resv' attribute yields each reservation in full and short form."""

        resvs = pbs_node_reservations('R123.pbs-server, S45.pbs-server')
        for name in ('R123.pbs-server', 'R123', 'S45.pbs-server', 'S45'):
            self.assertIn(name, resvs)

        self.assertEqual(pbs_node_reservations(None), [])

    def _kickoff_cmd(self, config=None, **pbs_opts):
        """Run PBS._kickoff with qsub mocked out and return the qsub command."""

        if config is None:
            config = self._pbs_config(**pbs_opts)
        work_dir = Path(self.pav_cfg.working_dir)
        job = SimpleNamespace(sched_log=work_dir / 'pbs_sched.log',
                              kickoff_path=work_dir / 'pbs_kickoff',
                              kickoff_log=work_dir / 'pbs_kickoff.log')

        proc = mock.MagicMock()
        proc.communicate.return_value = (b'1234.pbs-server\n', b'')
        proc.poll.return_value = 0

        plugin = pavilion.schedulers.get_plugin('pbs')
        with mock.patch.object(pbs_mod.subprocess, 'Popen', return_value=proc) as popen, \
                mock.patch.object(pbs_mod.sys_vars, 'get_vars',
                                  return_value={'sys_name': 'test'}):
            job_info = plugin._kickoff(self.pav_cfg, job, config, 'pav_test')

        self.assertEqual(job_info['id'], '1234')
        return popen.call_args[0][0]

    def test_kickoff_select(self):
        """Optional select keys appear only when set, in a fixed order."""

        cmd = self._kickoff_cmd(nodes=2, tasks=4)
        self.assertIn('-l select=2:ncpus=4', cmd)
        self.assertEqual(cmd[-5:-2], ['-j', 'oe', '-o'])

        cmd = self._kickoff_cmd(nodes=2, tasks=4, mpiprocs=4, mem='8gb', ngpus=2,
                                model='abc')
        self.assertIn('-l select=2:ncpus=4:mpiprocs=4:mem=8gb:ngpus=2:model=abc', cmd)

        cmd = self._kickoff_cmd(nodes=1, tasks=2, target='node01')
        self.assertIn('-l select=1:ncpus=2:host=node01', cmd)

    def test_kickoff_refuses_empty_select(self):
        """all_queue_nodes with no usable nodes must not submit 'select=0'."""

        # nodes/tasks set as the real config defaults would set them; the select
        # line is only built when they are.
        config = self._pbs_config(all_queue_nodes=1, queue='workq', nodes=1, tasks=1)
        plugin = pavilion.schedulers.get_plugin('pbs')
        with mock.patch.object(plugin, '_get_queue_nodect', return_value=0):
            with self.assertRaises(SchedulerPluginError):
                self._kickoff_cmd(config=config)

    def test_kickoff_missing_reservation(self):
        """An unknown reservation stops the kickoff with a clear error."""

        config = self._pbs_config()
        config['reservation'] = 'R999'
        rstat = subprocess.CompletedProcess(args=[], returncode=0, stdout=b'')
        with mock.patch.object(pbs_mod.subprocess, 'run', return_value=rstat):
            with self.assertRaises(SchedulerPluginError):
                pavilion.schedulers.get_plugin('pbs')._kickoff(
                    self.pav_cfg, SimpleNamespace(), config, 'pav_test')

