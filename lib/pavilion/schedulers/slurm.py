# pylint: disable=too-many-lines
"""The Slurm Scheduler Plugin."""

import distutils.spawn
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Union, Any, Tuple

import yaml_config as yc
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.var_dict import dfr_var_method
from . import base_vars
from .base_scheduler import (SchedulerPluginError, NodeList,
                             SchedulerPlugin, KickoffScriptHeader, NodeInfo)


class SbatchHeader(KickoffScriptHeader):
    """Provides header information specific to sbatch files for the
slurm kickoff script.
"""

    def get_lines(self):
        """Get the sbatch header lines."""

        lines = super().get_lines()

        lines.append(
            '#SBATCH --job-name {}'.format(self._job_name))

        lines.append('#SBATCH -p {s._conf[partition]}'.format(s=self))
        if self._config.get('reservation') is not None:
            lines.append('#SBATCH --reservation {s._conf[reservation]}'
                         .format(s=self))
        if self._config.get('qos') is not None:
            lines.append('#SBATCH --qos {s._conf[qos]}'.format(s=self))
        if self._config.get('account') is not None:
            lines.append('#SBATCH --account {s._conf[account]}'.format(s=self))

        time_limit = '{}:0:0'.format(self._config['time_limit'])
        lines.append('#SBATCH -t {}'.format(time_limit))
        nodes = compress_node_list(self._nodes)

        lines.append('#SBATCH -w {}'.format(nodes))
        lines.append('#SBATCH -N {}'.format(len(self._nodes)))

        return lines


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


class SlurmVars(base_vars.SchedulerVariables):
    """Scheduler variables for the Slurm scheduler."""
    # pylint: disable=no-self-use

    EXAMPLE = {
        "alloc_cpu_total": "36",
        "alloc_max_mem": "128842",
        "alloc_max_ppn": "36",
        "alloc_min_mem": "128842",
        "alloc_min_ppn": "36",
        "alloc_node_list": "node004 node005",
        "alloc_nodes": "2",
        "max_mem": "128842",
        "max_ppn": "36",
        "min_mem": "128842",
        "min_ppn": "36",
        "node_avail_list": ["node003", "node004", "node005"],
        "node_list": ["node001", "node002", "node003", "node004", "node005"],
        "node_up_list": ["node002", "node003", "node004", "node005"],
        "nodes": "371",
        "nodes_avail": "3",
        "nodes_up": "350",
        "test_cmd": "srun -N 2 -n 2",
        "test_node_list": "node004 node005",
        "test_node_list_short": "node00[4-5]",
        "test_nodes": "2",
        "test_procs": "2",
        "job_name": "pav",
    }

    @dfr_var_method
    def test_cmd(self):
        """Construct a cmd to run a process under this scheduler, with the
        criteria specified by this test.
        """

        # TODO - Add MPIRUN support.

        nodes = len(self._nodes)
        tasks = self.tasks_per_node() * nodes

        cmd = ['srun',
               '-N', str(nodes),
               '-w', compress_node_list(self._nodes.keys()),
               '-n', str(tasks)]

        cmd.extend(self._sched_config['slurm']['slurm_extra'])

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


class Slurm(SchedulerPlugin):
    """Schedule tests with Slurm!"""

    KICKOFF_SCRIPT_EXT = '.sbatch'

    VAR_CLASS = SlurmVars

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

    def _get_config_elems(self):
        return [
            yc.ListElem(name='avail_states',
                        sub_elem=yc.StrElem(),
                        defaults=['IDLE', 'MAINT'],
                        help_text="When looking for immediately available "
                                  "nodes, they must be in one of these "
                                  "states."),
            yc.ListElem(name='up_states',
                        sub_elem=yc.StrElem(),
                        defaults=['ALLOCATED',
                                  'COMPLETING',
                                  'IDLE',
                                  'MAINT'],
                        help_text="When looking for nodes that could be  "
                                  "allocated, they must be in one of these "
                                  "states."),
        ]

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

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Use the `scontrol show node` command to collect data on nodes.
        Types are converted according to self.FIELD_TYPES."""

        cmd = ['scontrol', 'show', 'node']
        sinfo = subprocess.check_output(cmd)
        sinfo = sinfo.decode('UTF-8')

        raw_node_data = sinfo.split('\n\n')

        extra = {'reservations': {}}
        # We also need to gather reservation information.

        cmd = ['scontrol', 'show', 'reservations']
        rinfo = subprocess.check_output(cmd)
        rinfo = rinfo.decode('UTF-8')

        for raw_res in rinfo.split('\n\n'):
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
        node_info['states'] = [state.strip().rstrip('*')
                               for state in node_info['states'].split('+')]

        # Split and strip multi-valued items.
        for key in 'partitions', 'features':
            node_info[key] = [data.strip() for data in node_info[key].split(',')]

        # Add reservations
        node_info['reservations'] = []
        for reservation, res_nodes in extra['reservations'].items():
            if node_info['name'] in res_nodes:
                node_info['reservations'].append(reservation)

        # Convert to an integer in GBytes
        node_info['mem'] = int(node_info['mem'])/1024**2

        # Convert to an integer
        node_info['cpus'] = int('cpus')

        up_states = sched_config['slurm']['up_states']
        avail_states = sched_config['slurm']['avail_states']
        node_info['up'] = all(state in up_states for state in node_info['states'])
        node_info['avail'] = all(state in avail_states for state in node_info['states'])

        return node_info

    def _available(self) -> bool:
        """Looks for several slurm commands, and tests slurm can talk to the
        slurm db."""

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

    def _kickoff(self, pav_cfg, script_path: Path, sched_config: dict,
                 test_chunk: NodeList):
        """Submit the kick off script using sbatch."""

        if not script_path.is_file():
            raise SchedulerPluginError(
                'Submission script {} not found'.format(kickoff_path))

        slurm_out = test.path / 'slurm.log'

        proc = subprocess.Popen(['sbatch',
                                 '--output={}'.format(slurm_out),
                                 script_path.as_posix()],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Sbatch failed for kickoff script '{}': {}"
                .format(kickoff_path, stderr.decode('utf8'))
            )

        return stdout.decode('UTF-8').strip().split()[-1]

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
            self.logger.warning("Error getting scontrol output with cmd "
                                "'%s'. Process timed out.", cmd)
            return []

        stdout = stdout.decode('utf8')
        stderr = stderr.decode('utf8')

        if proc.poll() != 0:
            raise ValueError(stderr)

        results = []
        for section in stdout.split('\n\n'):
            try:
                results.append(self._scontrol_parse(section))
            except (KeyError, ValueError) as err:
                self.logger.warning("Error parsing scontrol output with cmd"
                                    "'%s': %s", cmd, err)

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

    def _job_status(self, pav_cfg, job_id: str):
        """Get the current status of the slurm job for the given test."""

        try:
            job_info = self._scontrol_show('job', job_id)
        except ValueError as err:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note=str(err),
                when=time.time()
            )

        if not job_info:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_id),
                when=time.time()
            )

        # scontrol show returns a list. There should only be one item in that
        # list though.
        job_info = job_info.pop(0)

        job_state = job_info.get('JobState', 'UNKNOWN')
        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Job {} has state '{}', reason '{}'"
                      .format(job_id, job_state, job_info.get('Reason'))),
                when=time.time()
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_WINDUP,
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
                 "idea what is going on.".format(job_id, job_state),
            when=time.time()
        )

    def _cancel_job(self, test):
        """Scancel the job attached to the given test.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: A statusInfo object with the latest scheduler state.
        :rtype: TestStatusInfo
        """

        cmd = ['scancel', test.job_id]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            # SCancel successful, pass the stdout message
            test.set_run_complete()
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Slurm jobid {} canceled via slurm.".format(test.job_id),
            )
        else:
            # SCancel failed, pass the stderr message
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Tried (but failed) to cancel job: {}".format(stderr))
