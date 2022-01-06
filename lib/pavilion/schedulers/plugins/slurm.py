# pylint: disable=too-many-lines
"""The Slurm Scheduler Plugin."""

import distutils.spawn
import math
import re
import subprocess
import time
from typing import List, Union, Any, Tuple

import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..scheduler import SchedulerPluginError, KickoffScriptHeader
from ..types import NodeInfo, NodeList
from ..vars import SchedulerVariables
from ..config import validate_list


class SbatchHeader(KickoffScriptHeader):
    """Provides header information specific to sbatch files for the
slurm kickoff script.
"""

    def _kickoff_lines(self) -> List[str]:
        """Get the sbatch header lines."""

        lines = list()

        # White space is discouraged in job names.
        job_name = '__'.join(self._job_name.split())

        lines.append(
            '#SBATCH --job-name "{}"'.format(job_name))

        partition = self._config['partition']
        if partition:
            lines.append('#SBATCH -p {}'.format(partition))
        reservation = self._config['reservation']
        if reservation:
            lines.append('#SBATCH --reservation {}'.format(reservation))
        if self._config.get('qos') is not None:
            lines.append('#SBATCH --qos {s._conf[qos]}'.format(s=self))
        if self._config.get('account') is not None:
            lines.append('#SBATCH --account {s._conf[account]}'.format(s=self))

        time_limit = '{}:0:0'.format(self._config['time_limit'])
        lines.append('#SBATCH -t {}'.format(time_limit))
        nodes = Slurm.compress_node_list(self._nodes)

        lines.append('#SBATCH -w {}'.format(nodes))
        lines.append('#SBATCH -N {}'.format(len(self._nodes)))

        for line in self._config['slurm']['sbatch_extra']:
            lines.append('#SBATCH {}'.format(line))

        return lines


def validate_slurm_states(states):
    """Should be a list of strings (with no punctuation) or None."""

    # We can assume that if this isn't None it's a list.
    for state in states:
        if not state.isalnum():
            raise ValueError(
                "Invalid slurm state '{}'. Slurm states should be alpha "
                "numeric (typically in all caps). Symbols are stripped "
                "from the states as listed by slurm, so if the node states "
                "like 'UP*' are equivalent to 'UP'.")
    return states


class SlurmVars(SchedulerVariables):
    """Scheduler variables for the Slurm scheduler."""
    # pylint: disable=no-self-use

    EXAMPLE = SchedulerVariables.EXAMPLE.copy()
    EXAMPLE.update({
        'test_cmd': 'srun -N 5 -w node[05-10],node23 -n 20',
    })

    @dfr_var_method
    def test_cmd(self):
        """Construct a cmd to run a process under this scheduler, with the
        criteria specified by this test.
        """

        slurm_conf = self._sched_config['slurm']

        nodes = len(self._nodes)
        tasks = int(self.tasks_per_node()) * nodes

        if self._sched_config['slurm']['mpi_cmd'] == Slurm.MPI_CMD_SRUN:

            cmd = ['srun',
                   '-N', str(nodes),
                   '-w', Slurm.compress_node_list(self._nodes.keys()),
                   '-n', str(tasks)]

            cmd.extend(slurm_conf['srun_extra'])
        else:
            cmd = ['mpirun', '--map-by ppr:{}:node'.format(tasks)]

            rank_by = slurm_conf['mpirun_rank_by']
            bind_to = slurm_conf['mpirun_bind_to']
            mca = slurm_conf['mpirun_mca']
            if rank_by:
                cmd.extend(['--rank-by', rank_by])
            if bind_to:
                cmd.extend(['--bind-to', bind_to])
            if mca:
                for mca_opt in mca:
                    cmd.extend(['--mca', mca_opt])

            hostlist = ','.join(self._nodes.keys())
            cmd.extend(['--host', hostlist])

            cmd.extend(self._sched_config['slurm']['mpirun_extra'])

        return ' '.join(cmd)


def slurm_float(val):
    """Slurm 'float' values might also be 'N/A'."""
    if val == 'N/A':
        return None
    else:
        return float(val)


def slurm_states(state):
    """Parse a slurm state down to something reasonable."""
    states = state.split('+')

    if not states:
        return ['UNKNOWN']

    for i in range(len(states)):
        state = states[i]
        if state.endswith('$') or state.endswith('*'):
            states[i] = state[:-1]

    return states


class Slurm(SchedulerPluginAdvanced):
    """Schedule tests with Slurm!"""

    VAR_CLASS = SlurmVars
    KICKOFF_SCRIPT_HEADER_CLASS = SbatchHeader

    NODE_SEQ_REGEX_STR = (
        # The characters in a valid hostname.
        r'[a-zA-Z][a-zA-Z_-]*\d*'
        # A numeric range of nodes in square brackets.
        r'(?:\[(?:\d+|\d+-\d+)(?:,\d+|,\d+-\d+)*\])?'
    )
    NODE_LIST_RE = re.compile(
        # Match a comma separated list of these things.
        r'{0}(?:,{0})*$'.format(NODE_SEQ_REGEX_STR)
    )

    NODE_BRACKET_FORMAT_RE = re.compile(
        # Match hostname followed by square brackets,
        # group whats in the brackets.
        r'([a-zA-Z][a-zA-Z_-]*\d*)\[(.*)]'
    )

    def __init__(self):
        super().__init__(
            'slurm',
            "Schedules tests via the Slurm scheduler.")

    # Add sbatch extra to the values to consider when deciding what tests can be
    # allocated together.
    ALLOC_ACQUIRE_OPTIONS = list(SchedulerPluginAdvanced.ALLOC_ACQUIRE_OPTIONS)
    ALLOC_ACQUIRE_OPTIONS.append('slurm.sbatch_extra')

    MPI_CMD_SRUN = 'srun'
    MPI_CMD_MPIRUN = 'mpirun'
    MPI_CMD_OPTIONS = (MPI_CMD_SRUN, MPI_CMD_MPIRUN)

    MPIRUN_BIND_OPTS = ('slot', 'hwthread', 'core', 'L1cache', 'L2cache', 'L3cache',
        'socket', 'numa', 'board', 'node')

    def _get_config_elems(self):

        elems = [
            yc.ListElem(name='avail_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for immediately available "
                                  "nodes, they must be in one of these "
                                  "states."),
            yc.ListElem(name='up_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for nodes that could be  "
                                  "allocated, they must be in one of these "
                                  "states."),
            yc.ListElem(name='srun_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to pass to srun as part of the "
                                  "'sched.test_cmd' variable."),
            yc.ListElem(name='sbatch_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to add as sbatch header lines."
                                  "Example: ['--deadline now+20hours']"),
            yc.StrElem(name='mpi_cmd',
                       help_text="What command to use to start mpi jobs. Options"
                                 "are {}.".format(self.MPI_CMD_OPTIONS)),
            yc.StrElem(name='mpirun_bind_to',
                       help_text="MPIrun --bind-to option. See `man mpirun`"),
            yc.StrElem(name='mpirun_rank_by',
                       help_text="MPIrun --rank-by option. See `man mpirun`"),
            yc.ListElem(name='mpirun_mca', sub_elem=yc.StrElem(),
                       help_text="MPIrun mca module options (--mca). See `man mpirun`"),
            yc.ListElem(name='mpirun_extra', sub_elem=yc.StrElem(),
                        help_text="Extra arguments to add to mpirun commands."),
        ]

        defaults = {
            'up_states': ['ALLOCATED',
                          'COMPLETING',
                          'MAINTENANCE',
                          'IDLE',
                          'RESERVED',
                          'MAINT'],
            'avail_states': ['IDLE', 'MAINT', 'MAINTENANCE', 'RESERVED'],
            'sbatch_extra': [],
            'srun_extra': [],
            'mpi_cmd': self.MPI_CMD_SRUN,
            'mpirun_extra': [],
            'mpirun_mca': [],
        }

        validators = {
            'up_states': validate_slurm_states,
            'avail_states': validate_slurm_states,
            'srun_extra': validate_list,
            'sbatch_extra': validate_list,
            'mpi_cmd': self.MPI_CMD_OPTIONS,
            'mpirun_bind_to': self.MPIRUN_BIND_OPTS,
            'mpirun_rank_by': self.MPIRUN_BIND_OPTS,
            'mpirun_mca': validate_list,
            'mpirun_extra': validate_list,
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list):
        """Convert a slurm format node list into a list of nodes, and throw
        errors that help the user identify their exact mistake."""
        if node_list is None or node_list == '':
            return []

        match = cls.NODE_LIST_RE.match(node_list)
        if match is None:
            node_part_re = re.compile(cls.NODE_SEQ_REGEX_STR + r'$')
            # The following is required to handle foo[3,6-9].
            prev = ""
            for part in node_list.split(','):
                # Logic used to recombined 'foo[3', '6-9]' after split.
                if prev:
                    part = prev + "," + part
                    prev = ""
                if '[' in part and ']' not in part:
                    prev = part
                    continue
                if not node_part_re.match(part):
                    raise ValueError(
                        "Invalid Node List: '{}'. Syntax error in item '{}'. "
                        "Node lists components be a hostname or hostname "
                        "prefix followed by a range of node numbers. "
                        "Ex: foo003,foo0[10-20],foo[103-104], foo[10,12-14]"
                        .format(node_list, part)
                    )

            # If all the parts matched, then it's an overall format issue.
            raise ValueError("Invalid Node List: '{}' "
                             "Good Example: foo003,foo0[10-20],"
                             "foo[103-104], foo[10,12-14]")

        nodes = []
        prev = ""
        for part in node_list.split(','):
            if prev:
                part = prev + "," + part
                prev = ""
            if '[' in part and ']' not in part:
                prev = part
                continue
            match = cls.NODE_BRACKET_FORMAT_RE.match(part)
            if match:
                host, nodelist = match.groups()
                for node in nodelist.split(","):
                    if '-' in node:
                        start, end = node.split('-')
                        digits = min(len(start), len(end))
                        if int(end) < int(start):
                            raise ValueError(
                                "In node list '{}' part '{}', node range ends "
                                "before it starts."
                                .format(node_list, part)
                            )
                        for i in range(int(start), int(end)+1):
                            node = ('{base}{num:0{digits}d}'
                                    .format(base=host, num=i, digits=digits))
                            nodes.append(node)
                    else:
                        node = ('{base}{num}'
                                .format(base=host, num=node))
                        nodes.append(node)
            else:
                nodes.append(part)

        return nodes

    @staticmethod
    def compress_node_list(nodes: List[str]):
        """Convert a list of nodes into an abbreviated node list that
        slurm should understand."""

        # Pull apart the node name into a prefix and number. The prefix
        # is matched minimally to avoid consuming any parts of the
        # node number.
        node_re = re.compile(r'^([a-zA-Z0-9_-]+?)(\d+)$')

        seqs = {}
        nodes = sorted(nodes)
        for node in nodes:
            node_match = node_re.match(node)
            if node_match is None:
                continue

            base, raw_number = node_match.groups()
            number = int(raw_number)
            if base not in seqs:
                seqs[base] = (len(raw_number), [])

            _, node_nums = seqs[base]
            node_nums.append(number)

        node_seqs = []
        for base, (digits, nums) in sorted(seqs.items()):
            nums.sort(reverse=True)
            num_digits = math.ceil(math.log(nums[0], 10))
            pre_digits = digits - num_digits

            num_list = []

            num_series = []
            start = last = nums.pop()
            while nums:
                next_num = nums.pop()
                if next_num != last + 1:
                    num_series.append((start, last))
                    start = next_num
                last = next_num

            num_series.append((start, last))

            for start, last in num_series:
                if start == last:
                    num_list.append(
                        '{num:0{digits}d}'
                            .format(base=base, num=start, digits=num_digits))
                else:
                    num_list.append(
                        '{start:0{num_digits}d}-{last:0{num_digits}d}'
                            .format(start=start, last=last, num_digits=num_digits))

            num_list = ','.join(num_list)
            if ',' in num_list or '-' in num_list:
                seq_format = '{base}{z}[{num_list}]'
            else:
                seq_format = '{base}{z}{num_list}'

            node_seqs.append(
                seq_format
                .format(base=base, z='0' * pre_digits, num_list=num_list))

        return ','.join(node_seqs)

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Use the `scontrol show node` command to collect data on nodes.
        Types are converted according to self.FIELD_TYPES."""

        cmd = ['scontrol', 'show', 'node']
        sinfo = subprocess.check_output(cmd)
        sinfo = sinfo.decode('UTF-8')

        raw_node_data = [node_data for node_data in sinfo.split('\n\n') if node_data.strip()]

        extra = {'reservations': {}}
        # We also need to gather reservation information.

        cmd = ['scontrol', 'show', 'reservations']
        rinfo = subprocess.check_output(cmd)
        rinfo = rinfo.decode('UTF-8')

        for raw_res in rinfo.split('\n\n'):
            if not raw_res.strip():
                continue
            res_info = self._scontrol_parse(raw_res)
            name = res_info.get('ReservationName')
            nodes = res_info.get('Nodes')
            nodes = self.parse_node_list(nodes)
            extra['reservations'][name] = nodes

        return raw_node_data, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Translate the gathered data into a NodeInfo dict."""

        parsed_data = self._scontrol_parse(node_data)
        node_info = NodeInfo({})

        for orig_key, dest_key in (
                ('NodeName', 'name'),
                ('Arch', 'arch'),
                ('CPUTot', 'cpus'),
                ('ActiveFeatures', 'features'),
                ('RealMemory', 'mem'),
                ('State', 'states'),
                ('Partitions', 'partitions')):
            node_info[dest_key] = parsed_data.get(orig_key)

        # Split and clean up the states
        if node_info['states'] is not None:
            node_info['states'] = [state.strip().rstrip('*')
                                   for state in node_info['states'].split('+')]
        else:
            node_info['states'] = None

        # Split and strip multi-valued items.
        for key in 'partitions', 'features':
            partitions = node_info.get(key)
            if partitions is None:
                node_info[key] = []
            else:
                node_info[key] = [data.strip() for data in node_info[key].split(',')]

        # Add reservations
        node_info['reservations'] = []
        for reservation, res_nodes in extra['reservations'].items():
            if node_info['name'] in res_nodes:
                node_info['reservations'].append(reservation)

        # Convert to an integer in GBytes
        node_info['mem'] = int(node_info['mem'])/1024**2

        # Convert to an integer
        node_info['cpus'] = int(node_info['cpus'])

        up_states = sched_config['slurm']['up_states']
        avail_states = sched_config['slurm']['avail_states']
        node_info['up'] = all(state in up_states for state in node_info['states'])
        node_info['avail'] = all(state in avail_states for state in node_info['states'])

        return node_info

    def _available(self) -> bool:
        """Looks for several slurm commands, and tests slurm can talk to the
        slurm db."""

        _ = self

        for command in 'scontrol', 'sbatch', 'sinfo':
            if distutils.spawn.find_executable(command) is None:
                return False

        # Try to get basic system info from sinfo. Should return not-zero
        # on failure.
        ret = subprocess.call(
            ['sinfo'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return ret == 0

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict,
                 chunk: NodeList) -> JobInfo:
        """Submit the kick off script using sbatch."""

        nodes = self.compress_node_list(chunk)

        proc = subprocess.Popen(['sbatch',
                                 '-w', nodes,
                                 '--output={}'.format(job.sched_log.as_posix()),
                                 job.kickoff_path.as_posix()],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Sbatch failed for kickoff script '{}': {}"
                .format(job.kickoff_path, stderr.decode('utf8'))
            )

        sys_name = sys_vars.get_vars(True)['sys_name']

        return JobInfo({
            'id': stdout.decode('UTF-8').strip().split()[-1],
            'sys_name': sys_name,
        })

    SCONTROL_KEY_RE = re.compile(r'(?:^|\s+)([A-Z][a-zA-Z0-9:/]*)=')
    SCONTROL_WS_RE = re.compile(r'\s+')

    def _scontrol_parse(self, section):

        # NOTE: Because slurm administrators can essentially add whatever
        # they want to scontrol variables, they may break the parsing of
        # 'scontrol show' output, perhaps even making it un-parseable with a
        # general algorithm.

        offset = 0
        val = None
        key = None

        results = {}

        match = self.SCONTROL_KEY_RE.search(section)
        # Keep searching till we find all the key=value pairs.
        while match is not None:

            # We break values at whitespace by default, but their
            # might be more. We add everything before the key match
            # to the last value.
            if key is not None:
                extra = section[offset: match.start(1)].rstrip()
                val = val + extra

                results[key] = val

            key = match.groups()[0]

            ws_match = self.SCONTROL_WS_RE.search(section, match.end())
            if ws_match is None:
                # We've reached the end of the string
                offset = len(section)
            else:
                offset = ws_match.start()

            # The value is everything up to the whitespace (we may append more)
            val = section[match.end():offset]

            # Search for the next key starting from the offset
            match = self.SCONTROL_KEY_RE.search(section, offset)

        if key is not None:
            # Add the last key and anything extra
            results[key] = val + section[offset:].rstrip()

        return results

    def _scontrol_show(self, *args, timeout=10):
        """Run scontrol show and return the parsed output.

        :param list(str) args: Additional args to scontrol.
        :param int timeout: How long to wait for results.
        """

        cmd = ['scontrol', 'show'] + list(args)

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            return []

        stdout = stdout.decode('utf8')
        stderr = stderr.decode('utf8')

        if proc.poll() != 0:
            raise ValueError(stderr)

        results = []
        for section in stdout.split('\n\n'):
            try:
                results.append(self._scontrol_parse(section))
            except (KeyError, ValueError):
                pass

        return results

    # Slurm status mappings
    # SCHED_WAITING - The job is still queued and waiting to start.
    SCHED_WAITING = [
        'CONFIGURING',
        'PENDING',
    ]
    # SCHED_OK - From pavilion's perspective, these all mean Pavilion should
    # look to the test's status file for more information.
    SCHED_RUN = [
        'COMPLETED',
        'COMPLETING',
        'RUNNING',
        'STAGE_OUT',
    ]
    # SCHED_CANCELLED - The job was cancelled. We can't expect to see more
    # from the test status, as the test probably never started.
    SCHED_CANCELLED = [
        'CANCELLED',
        'DEADLINE',
        'PREEMPTED',
        'BOOT_FAIL',
    ]
    # SCHED_ERROR - Something went wrong, but the job was running at some
    # point.
    SCHED_ERROR = [
        'DEADLINE',
        'FAILED',
        'NODE_FAIL',
        'OUT_OF_MEMORY',
        'PREEMPTED',
        'REVOKED',
        'SPECIAL_EXIT',
        'TIMEOUT',
    ]
    # SCHED_OTHER - Pavilion shouldn't see these, and will log them when it
    # does.
    SCHED_OTHER = [
        'RESV_DEL_HOLD',
        'REQUEUE_FED',
        'REQUEUE_HOLD',
        'REQUEUED',
        'RESIZING',
        'SIGNALING',
        'SUSPENDED',
    ]

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the slurm job for the given test."""

        sys_name = sys_vars.get_vars(True)['sys_name']
        if job_info['sys_name'] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name))

        try:
            job_data = self._scontrol_show('job', job_info['id'])
        except ValueError as err:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note=str(err),
                when=time.time()
            )

        if not job_data:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_info['id']),
                when=time.time()
            )

        # scontrol show returns a list. There should only be one item in that
        # list though.
        if job_data:
            job_data = job_data.pop(0)
        else:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Could not find info on slurm job '{}' in slurm."
                      .format(job_info['id'])),
                when=time.time())

        job_state = job_data.get('JobState', 'UNKNOWN')
        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Job {} has state '{}', reason '{}'"
                      .format(job_info['id'], job_state, job_info.get('Reason'))),
                when=time.time()
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note=("Job is running or about to run. Has job state {}"
                      .format(job_state)),
                when=time.time()
            )
        elif job_state in self.SCHED_ERROR:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "The scheduler killed the job, it has job state '{}'"
                .format(job_state))

        elif job_state in self.SCHED_CANCELLED:
            # The job appears to have been cancelled without running.
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state))

        # The best we can say is that the test is still SCHEDULED. After all,
        # it might be! Who knows.
        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. We have no"
                 "idea what is going on.".format(job_info['id'], job_state),
            when=time.time()
        )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Scancel the job attached to the given test."""

        _ = self

        if job_info['sys_name'] != sys_vars.get_vars(True)['sys_name']:
            return "Could not cancel - job started on a different cluster ({})."\
                .format(job_info['sys_name'])

        cmd = ['scancel', job_info['id']]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        else:
            return "Tried (but failed) to cancel job {}: {}".format(job_info['id'],
                                                                    stderr)
