# pylint: disable=too-many-lines
"""The Pbs Scheduler Plugin."""

import os
import re
import shutil
import subprocess
import time
import json
from typing import List, Union, Any, Tuple, Dict

import hostlist
import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.types import NodeInfo, NodeList
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list
from ..scheduler import KickoffScriptHeader
from ..vars import SchedulerVariables
from ...errors import SchedulerPluginError, SchedConfigError


class QsubHeader(KickoffScriptHeader):
    """Provides header information specific to qsub files for the PBS kickoff script."""

    def _kickoff_lines(self) -> List[str]:
        """Get the qsub header lines."""

        lines = []

        # PBS job names: first char must be alphabetic, only alphanumeric/_/- allowed.
        job_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', self._job_name)
        if not job_name or not job_name[0].isalpha():
            job_name = 'pav_' + job_name
        lines.append('#PBS -N {}'.format(job_name))

        queue = self._config['pbs']['queue']
        if queue is not None:
            lines.append('#PBS -q {}'.format(queue))

        # Mandatory account name
        if self._sched_vars.account():
            lines.append('#PBS -A {}'.format(self._sched_vars.account()))

        # Exclusive node allocation
        if self._config['pbs'].get('exclusive'):
            lines.append('#PBS -l place=exclhost:scatter')

        # Extra qsub arguments
        for line in self._config['pbs']['qsub_extra']:
            lines.append('#PBS {}'.format(line))

        return lines


def validate_pbs_states(states):
    """Should be a list of strings (with no punctuation) or None."""
    for state in states:
        if not re.match(r'^[a-z-]*$', state):
            raise SchedConfigError(
                "Invalid PBS state '{}'. PBS states should be alpha numeric.".format(state))
    return states


class PBSVars(SchedulerVariables):
    """Scheduler variables for the PBS scheduler."""

    # 'pav show sched --vars pbs' renders this for deferred vars. Inherit upstream's
    # examples, then correct the ones that are wrong or missing for PBS:
    #  - srun_args is overridden below to '' for PBS, but the inherited example still
    #    advertised Slurm flags, which is exactly the confusion the override exists
    #    to remove.
    #  - our own deferred vars had no example at all and rendered as '<no example>'.
    EXAMPLE = dict(
        SchedulerVariables.EXAMPLE,
        srun_args='',
        queue='workq',
        walltime='00:01:00',
        mpiprocs='2',
        test_cmd='mpirun --host node01,node02',
    )

    def _test_cmd(self):
        """Construct a cmd to run a process under this scheduler."""
        pbs_conf = self._sched_config['pbs']
        nodes = len(self._nodes)
        tasks = self._sched_config['tasks']

        if tasks is None:
            tasks = int(self.tasks_per_node()) * nodes

        cmd = []
        if pbs_conf['mpi_cmd']:
            cmd = ['mpirun']
            cmd.extend(self.mpirun_opts())
            cmd.extend(['--host', ','.join(self._nodes.keys())])

        return ' '.join(cmd)

    @dfr_var_method
    def test_cmd(self):
        """Calls the actual test command and wraps the return with the configured wrapper."""
        # Filter None values to avoid TypeError when joining
        parts = filter(None, [self._test_cmd(), self._sched_config.get('wrapper')])
        return ' '.join(parts)

    @dfr_var_method
    def walltime(self):
        """Return the configured walltime."""
        return self._sched_config['pbs']['walltime']

    @dfr_var_method
    def queue(self):
        """Return the configured queue, or empty string if not set."""
        return self._sched_config['pbs']['queue'] or ''

    # NOTE: a variable's docstring IS its help text in 'pav show sched --vars', and
    # that column is narrow. Keep these docstrings to ONE short line; rationale
    # belongs here in comments, which the listing never renders.
    #
    # Upstream's SchedulerVariables.srun_args (lib/pavilion/schedulers/vars.py)
    # composes Slurm flags: --account, --partition, --qos, --reservation, --nodes,
    # and its own docstring says it is meant for the 'raw' scheduler. Every plugin
    # inherits it, so it appears under PBS whether it makes sense or not -- a PBS
    # test referencing {{sched.srun_args}} would silently be handed Slurm flags
    # instead of erroring. Overridden to '' so it is inert. It cannot be removed
    # from the listing without touching pavilion source.
    #
    # For extra qsub arguments use the 'qsub_extra' CONFIG KEY (emits '#PBS' header
    # lines). There is no {{sched.qsub_extra}} variable.
    #
    # Returns '' not None: dfr_var_method rejects None and crashes kickoff.
    @dfr_var_method
    def srun_args(self):
        """Not applicable to PBS - always empty. Use the 'qsub_extra' config key."""

        return ''

    # Lets a test reference the rank count it asked for instead of hardcoding it
    # twice, e.g. 'mpirun -np {{sched.mpiprocs}} ./app'. Returns '' not None when
    # unset: mpiprocs is optional and dfr_var_method rejects a None return with
    # "Invalid variable value returned by ...", crashing kickoff -- same reason
    # queue() returns ''. Docstring stays one line: it is the --vars help text.
    @dfr_var_method
    def mpiprocs(self):
        """The configured MPI ranks per chunk, or '' if not set."""
        mpiprocs = self._sched_config['pbs'].get('mpiprocs')

        return str(mpiprocs) if mpiprocs else ''


def pbs_float(val):
    """PBS 'float' values might also be 'N/A'."""
    return None if val == 'N/A' else float(val)


def pbs_int(val):
    """PBS 'int' values might also be 'N/A'."""
    return None if val == 'N/A' else int(val)


def pbs_str(val):
    """PBS 'str' values might also be 'N/A'."""
    return None if val == 'N/A' else str(val)





def pbs_states(state):
    """Parse a PBS state down to something reasonable."""
    states = state.split('+')

    if not states:
        return ['UNKNOWN']

    # STYLE FIX: use enumerate instead of range(len(...))
    for i, s in enumerate(states):
        if s.endswith('$') or s.endswith('*'):
            states[i] = s[:-1]

    return states



class PBS(SchedulerPluginAdvanced):
    """Schedule tests with PBS!"""

    VAR_CLASS = PBSVars
    KICKOFF_SCRIPT_HEADER_CLASS = QsubHeader

    # Pbs status mappings
    SCHED_WAITING = ['Q', 'W']
    SCHED_RUN = ['R', 'B']
    SCHED_CANCELLED = ['E', 'X']
    SCHED_ERROR = ['F']
    SCHED_OTHER = ['H', 'U', 'S', 'T']

    def __init__(self):
        super().__init__('pbs', "Schedules tests via the PBS scheduler.")

    # Tests may only share a PBS allocation when every setting that shapes the qsub
    # command matches. Anything listed here that differs forces separate jobs.
    # If an option that changes the select statement or qsub args is NOT listed,
    # Pavilion will merge those tests into one allocation and one of them silently
    # gets the other's resources -- which is exactly what happened with mpiprocs
    # before it was added here.
    JOB_SHARE_KEY_ATTRS = SchedulerPluginAdvanced.JOB_SHARE_KEY_ATTRS + [
        'pbs.qsub_extra',
        'pbs.exclusive',
        'pbs.mpiprocs',
    ]

    MPI_CMD_MPIRUN = 'mpirun'
    MPIRUN_BIND_OPTS = (
        'slot', 'hwthread', 'core', 'L1cache', 'L2cache', 'L3cache',
        'socket', 'numa', 'board', 'node'
    )

    def _get_config_elems(self):
        elems = [
            yc.ListElem(name='avail_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for immediately available nodes, "
                                  "they must be in one of these states."),
            yc.ListElem(name='up_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for nodes that could be allocated, "
                                  "they must be in one of these states."),
            yc.StrElem(name='all_queue_nodes',
                       help_text="If set, use all nodes in the queue instead of a fixed count."),
            yc.ListElem(name='reserved_states',
                        sub_elem=yc.StrElem(),
                        help_text="Ignore nodes in these states, unless a reservation "
                                  "was specified."),
            yc.ListElem(name='qsub_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to add as qsub header lines. "
                                  "Example: ['--deadline now+20hours']"),
            yc.StrElem(name='walltime',
                       help_text="Walltime to add to job in PBS format. "
                                 "Example: 00:01:00"),
            yc.StrElem(name='target',
                       help_text="Target a specific host. "
                                 "Example: node001 "),
            yc.StrElem(name='queue',
                       help_text="Queue to run job in. Example: normal"),
            yc.StrElem(name='tasks'),
            yc.StrElem(name='nodes'),
            yc.StrElem(name='mpiprocs',
                       help_text="MPI ranks per chunk, added to the select statement as "
                                 "'-l select=...:mpiprocs=N'. OPTIONAL and unset by default -- "
                                 "some clusters require it, others don't, and when it is unset "
                                 "the select statement is byte-for-byte what it was before. "
                                 "Note this is distinct from 'tasks', which sets ncpus (cores "
                                 "per chunk); mpiprocs is what determines the PBS_NODEFILE line "
                                 "count and the rank count mpirun sees. Example: 2"),
            yc.StrElem(name='mpi_cmd',
                       help_text="Command to use to start MPI jobs. If empty, "
                                 "MPI will not be used. Options: {}.".format(self.MPI_CMD_MPIRUN)),
            yc.StrElem(name='model',
                       help_text="Node model to target. Example: broadwell"),
            yc.StrElem(name='exclusive',
                       help_text="Request exclusive node allocation (-l place=exclhost:scatter). "
                                 "Set to 'true' to enable."),
        ]

        defaults = {
            'up_states': ['job-exclusive', 'job-busy', 'free', 'busy', 'resv-exclusive'],
            'avail_states': ['free'],
            'reserved_states': ['resv-exclusive'],
            'tasks': 1,
            'nodes': 1,
            'walltime': '00:01:00',
            'queue': None,
            'qsub_extra': [],
            'mpi_cmd': [],
            'target': None,
            'all_queue_nodes': None,
            'mpiprocs': None,
            'model': None,
            'exclusive': None,
        }

        validators = {
            'up_states': validate_pbs_states,
            'avail_states': validate_pbs_states,
            'reserved_states': validate_pbs_states,
            'tasks': pbs_int,
            'nodes': pbs_int,
            'qsub_extra': validate_list,
            'walltime': pbs_str,
            'queue': pbs_str,
            'mpi_cmd': pbs_str,
            'target': pbs_str,
            'all_queue_nodes': pbs_int,
            'mpiprocs': pbs_int,
            'model': pbs_str,
            'exclusive': lambda v: v if v is None else str(v).lower() in ('true', '1', 'yes'),
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list) -> NodeList:
        if not node_list:
            return NodeList([])

        # BUG FIX: isalpha() rejects hostnames with digits/hyphens; use a truthy check instead
        # Deduplicate while preserving order: PBS_NODEFILE lists one entry per CPU slot,
        # so a node with 2 CPUs appears twice. dict.fromkeys preserves insertion order.
        nodes = list(dict.fromkeys(n for n in node_list if n))
        return NodeList(nodes)


    def _get_alloc_nodes(self, job) -> NodeList:
        """Get the list of allocated nodes."""
        try:
            nodefile = os.environ['PBS_NODEFILE']
        except KeyError:
            raise SchedulerPluginError("PBS_NODEFILE environment variable is not set.")

        node_list = []

        try:
            with open(nodefile, 'r') as nf:
                n_tmp = nf.read().split('\n')
        except OSError as err:
            raise SchedulerPluginError(
                "Could not read PBS nodefile '{}'.".format(nodefile), prior_error=err)

        for n in n_tmp:
            if '.' in n:
                node_list.append(n.split('.')[0])
            else:
                node_list.append(n)

        return self.parse_node_list(node_list)

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Use `pbsnodes` to collect data on nodes."""
        try:
            output = subprocess.check_output(['pbsnodes', '-avFjson'], stderr=subprocess.PIPE)
            nodes_json = json.loads(output).get('nodes', {})
        except (subprocess.CalledProcessError, json.JSONDecodeError) as err:
            raise SchedulerPluginError("Failed to get pbsnodes data", err)

        raw_node_data = []
        for node_name, data in nodes_json.items():
            res = data.get('resources_available', {})
            queue = data.get('queue')
            res['queue'] = [queue] if queue else []
            res['state'] = data.get('state', 'unknown')
            raw_node_data.append({node_name: res})

        return raw_node_data, {'reservations': {}}

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Translate gathered data into a NodeInfo dict."""
        parsed_data = self._pbsnodes_parse(node_data)
        node_info = NodeInfo({})

        key_map = (
            ('vnode', 'name'),
            ('arch', 'arch'),
            ('ncpus', 'cpus'),
            ('mem', 'mem'),
            ('state', 'states'),
            ('queue', 'partitions'),
            ('model', 'model'),
        )

        for node in parsed_data:
            for orig_key, dest_key in key_map:
                node_info[dest_key] = parsed_data[node].get(orig_key)

        # Split and clean up states
        if node_info['states'] is not None:
            node_info['states'] = [
                state.strip().rstrip(',') for state in node_info['states'].split(',')
            ]

        # Convert mem to bytes; PBS reports values like '4194304kb'
        if node_info.get('mem'):
            mem_str = node_info['mem']
            suffix = mem_str[-2:].lower()
            value = int(mem_str[:-2])
            multipliers = {'kb': 1024, 'mb': 1024 ** 2, 'gb': 1024 ** 3}
            node_info['mem'] = value * multipliers.get(suffix, 1)

        # Convert cpus to integer
        if node_info.get('cpus'):
            node_info['cpus'] = int(node_info['cpus'])

        pbs_config = sched_config['pbs']
        up_states = list(pbs_config['up_states'])
        avail_states = list(pbs_config['avail_states'])
        reserved_states = pbs_config['reserved_states']

        if sched_config.get('reservation'):
            up_states += reserved_states
            avail_states += reserved_states

        states = node_info.get('states') or []
        node_info['up'] = all(state in up_states for state in states)
        node_info['available'] = all(state in avail_states for state in states)

        return node_info

    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> Union[str, None]:
        """Filter nodes by features. Returns reason to filter, or None to keep."""
        if 'free' not in (node.get('states') or []):
            return "node unavailable"
        queue = sched_config['pbs'].get('queue')
        if queue:
            if queue not in (node.get('partitions') or []):
                return "node not in queue"
        return None

    def _available(self) -> bool:
        """Check that PBS commands exist and PBS can talk to the scheduler DB."""
        for command in ('pbsnodes', 'qsub', 'qstat'):
            if shutil.which(command) is None:
                return False

        ret = subprocess.call(
            ['qstat'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ret == 0

    def _get_queue_nodect(self, queue, model=None):
        nodes = self._nodes
        nodect = 0
        for node in nodes:
            if 'free' not in (nodes[node].get('states') or []):
                continue
            if nodes[node]['partitions']:
                if queue in nodes[node]['partitions']:
                    if model is None or nodes[node].get('model') == model:
                        nodect += 1
        return nodect

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict, job_name: str,
                 nodes: Union[NodeList, None] = None,
                 node_range: Union[Tuple[int, int], None] = None) -> JobInfo:
        """Submit the kickoff script using qsub."""

        pbs_cfg = sched_config['pbs']
        cmd = ['qsub']

        if pbs_cfg.get('all_queue_nodes') and pbs_cfg.get('target'):
            raise SchedulerPluginError(
                "PBS config error: 'all_queue_nodes' and 'target' are mutually exclusive. "
                "Remove one before submitting.")

        if pbs_cfg.get('walltime'):
            cmd.append('-l walltime={}'.format(pbs_cfg['walltime']))

        if pbs_cfg.get('nodes') or pbs_cfg.get('tasks'):
            n = pbs_cfg.get('nodes', 1)
            if pbs_cfg.get('all_queue_nodes'):
               n = self._get_queue_nodect(pbs_cfg.get('queue'), model=pbs_cfg.get('model'))
            t = pbs_cfg.get('tasks', 1)
            if pbs_cfg.get('target') and not pbs_cfg.get('all_queue_nodes'):
                select = '-l select={}:ncpus={}:host={}'.format(n, t, pbs_cfg['target'])
            else:
                select = '-l select={}:ncpus={}'.format(n, t)
            # Optional: only appended when explicitly set, so clusters that don't
            # use mpiprocs get exactly the select statement they got before.
            if pbs_cfg.get('mpiprocs'):
                select += ':mpiprocs={}'.format(pbs_cfg['mpiprocs'])
            if pbs_cfg.get('model'):
                select += ':model={}'.format(pbs_cfg['model'])
            cmd.append(select)

        cmd += ['-o', job.sched_log.as_posix(), job.kickoff_path.as_posix()]

        with job.kickoff_log.open('a') as log:
            log.write(' '.join(cmd) + '\n')

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Qsub failed for kickoff script '{}': {}"
                .format(job.kickoff_path, stderr.decode('utf8'))
            )

        sys_name = sys_vars.get_vars(True)['sys_name']
        return JobInfo({
            'id': stdout.decode('utf-8').strip().split('.')[0],
            'sys_name': sys_name,
        })

    def _pbsnodes_parse(self, section: dict) -> Dict[str, str]:
        """Parse pbsnodes JSON output into a dict."""
        # SIMPLIFICATION: dict.update({k: v}) in a loop is just dict.copy()
        return dict(section)

    def _qstat(self, *args, timeout=30) -> List[Dict]:
        """Run qstat and return the parsed output.

        :param args: Additional args to qstat.
        :param timeout: How long to wait for results (seconds).
        """
        cmd = ['qstat', '-fFjson'] + list(args)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as err:
            raise SchedulerPluginError("Timed out waiting for qstat.", prior_error=err)

        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        if proc.poll() != 0:
            raise SchedulerPluginError("qstat failed: {}".format(stderr))

        try:
            job_dict = json.loads(stdout)['Jobs']
        except json.JSONDecodeError as err:
            raise SchedulerPluginError(
                "Could not parse qstat output as JSON.", prior_error=err)
        except KeyError:
            raise SchedulerPluginError(
                "qstat JSON output missing 'Jobs' key.")

        return [job_dict]

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the PBS job."""
        sys_name = sys_vars.get_vars(True)['sys_name']
        if job_info['sys_name'] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name)
            )

        try:
            job_data = self._qstat(job_info['id'])
        except SchedulerPluginError as err:
            if isinstance(err.prior_error, subprocess.TimeoutExpired):
                return TestStatusInfo(
                    state=STATES.SCHED_WARNING,
                    note="Timed out waiting for qstat (job {})".format(job_info['id']),
                    when=time.time()
                )
            return TestStatusInfo(state=STATES.SCHED_ERROR, note=str(err), when=time.time())

        if not job_data:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_info['id']),
                when=time.time()
            )

        # BUG FIX: original code checked len > 0 twice, with dead code in the else branch
        job_data = job_data.pop(0)

        job_id = list(job_data.keys())[0]
        job_state = job_data[job_id].get('job_state', 'UNKNOWN')

        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note="Job {} has state '{}', reason '{}'".format(
                    job_info['id'], job_state, job_info.get('Reason')),
                when=time.time()
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note="Job is running or about to run. Has job state {}".format(job_state),
                when=time.time()
            )
        elif job_state in self.SCHED_ERROR:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "The scheduler killed the job, it has job state '{}'".format(job_state)
            )
        elif job_state in self.SCHED_CANCELLED:
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state)
            )

        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. "
                 "We have no idea what is going on.".format(job_info['id'], job_state),
            when=time.time()
        )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Cancel the PBS job via qdel."""
        if job_info['sys_name'] != sys_vars.get_vars(True)['sys_name']:
            return "Could not cancel - job started on a different cluster ({}).".format(
                job_info['sys_name'])

        proc = subprocess.Popen(
            ['qdel', job_info['id']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        return "Tried (but failed) to cancel job {}: {}".format(job_info['id'], stderr)
