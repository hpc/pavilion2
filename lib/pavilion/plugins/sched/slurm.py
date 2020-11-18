# pylint: disable=too-many-lines
"""The Slurm Scheduler Plugin."""

import distutils.spawn
import math
import os
import re
import subprocess
from pathlib import Path
from typing import List

import yaml_config as yc
from pavilion import scriptcomposer
from pavilion import schedulers
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_var_method
from pavilion.status_file import STATES, StatusInfo
from pavilion.var_dict import var_method


class SbatchHeader(scriptcomposer.ScriptHeader):
    """Provides header information specific to sbatch files for the
slurm kickoff script.
"""

    def __init__(self, sched_config, nodes, test_id, slurm_vars):
        """Build a header for an sbatch file.

        :param dict sched_config: The slurm section of the test config.
        :param str nodes: The node list
        :param int test_id: The test's id.
        :param dict slurm_vars: The test variables.
        """

        super().__init__()

        self._conf = sched_config
        self._test_id = test_id
        self._nodes = nodes
        self._vars = slurm_vars

    def get_lines(self):
        """Get the sbatch header lines."""

        lines = super().get_lines()

        if self._conf.get('job_name') is not None:
            lines.append(
                '#SBATCH --job-name {s._conf[job_name]}'
                .format(s=self))
        else:
            lines.append(
                '#SBATCH --job-name "pav test #{s._test_id}"'
                .format(s=self))

        lines.append('#SBATCH -p {s._conf[partition]}'.format(s=self))
        if self._conf.get('reservation') is not None:
            lines.append('#SBATCH --reservation {s._conf[reservation]}'
                         .format(s=self))
        if self._conf.get('qos') is not None:
            lines.append('#SBATCH --qos {s._conf[qos]}'.format(s=self))
        if self._conf.get('account') is not None:
            lines.append('#SBATCH --account {s._conf[account]}'.format(s=self))

        lines.append('#SBATCH -N {s._nodes}'.format(s=self))
        tasks = self._conf['tasks_per_node']
        if tasks == 'all':
            tasks = self._vars['min_ppn']
        lines.append('#SBATCH --tasks-per-node={}'.format(tasks))
        if self._conf.get('time_limit') is not None:
            lines.append('#SBATCH -t {s._conf[time_limit]}'.format(s=self))
        if self._conf.get('include_nodes') is not None:
            lines.append('#SBATCH -w {s._conf[include_nodes]}'.format(s=self))
        if self._conf.get('exclude_nodes') is not None:
            lines.append('#SBATCH -x {s._conf[exclude_nodes]}'.format(s=self))

        return lines


class SlurmVars(SchedulerVariables):
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

    @var_method
    def min_ppn(self):
        """The minimum processors per node across all nodes."""
        return self.sched_data['summary']['min_ppn']

    @var_method
    def max_ppn(self):
        """The maximum processors per node across all nodes."""
        return self.sched_data['summary']['max_ppn']

    @var_method
    def min_mem(self):
        """The minimum memory per node across all nodes (in MiB)."""

        return self.sched_data['summary']['min_mem']

    @var_method
    def max_mem(self):
        """The maximum memory per node across all nodes (in MiB)."""

        return self.sched_data['summary']['max_mem']

    @var_method
    def nodes(self):
        """Number of nodes on the system."""

        return len(self.sched_data['nodes'])

    @var_method
    def node_list(self):
        """List of nodes on the system."""

        return list(self.sched_data['nodes'].keys())

    @var_method
    def node_up_list(self):
        """List of nodes who are in an a state that is considered available."""

        up_states = self.sched_config['up_states']

        nodes = []
        for node, node_info in self.sched_data['nodes'].items():
            if 'Partitions' not in node_info:
                # Skip nodes that aren't in any partition.
                continue

            for state in node_info['State']:
                if state not in up_states:
                    break
            else:
                nodes.append(node)

        return nodes

    @var_method
    def nodes_up(self):
        """Number of nodes in an 'avail' state."""

        return len(self.node_up_list())

    @var_method
    def node_avail_list(self):
        """List of nodes who are in an a state that is considered available.
Warning: Tests that use this will fail to start if no nodes are available."""

        avail_states = self.sched_config['avail_states']

        nodes = []
        for node, node_info in self.sched_data['nodes'].items():
            if 'Partitions' not in node_info:
                # Skip nodes that aren't in any partition.
                continue

            for state in node_info['State']:
                if state not in avail_states:
                    break
            else:
                nodes.append(node)

        return nodes

    @var_method
    def nodes_avail(self):
        """Number of nodes in an 'avail' state."""

        return len(self.node_avail_list())

    @dfr_var_method
    def alloc_nodes(self):
        """The number of nodes in this allocation."""
        return os.getenv('SLURM_NNODES')

    @dfr_var_method
    def alloc_node_list(self):
        """A space separated list of nodes in this allocation."""

        return ' '.join(Slurm.parse_node_list(os.getenv('SLURM_NODELIST')))

    @dfr_var_method
    def alloc_min_ppn(self):
        """Min ppn for this allocation."""
        return self.sched_data['alloc_summary']['min_ppn']

    @dfr_var_method
    def alloc_max_ppn(self):
        """Max ppn for this allocation."""
        return self.sched_data['alloc_summary']['max_ppn']

    @dfr_var_method
    def alloc_min_mem(self):
        """Min mem per node for this allocation. (in MiB)"""
        return self.sched_data['alloc_summary']['min_mem']

    @dfr_var_method
    def alloc_max_mem(self):
        """Max mem per node for this allocation. (in MiB)"""
        return self.sched_data['alloc_summary']['max_mem']

    @dfr_var_method
    def alloc_cpu_total(self):
        """Total CPUs across all nodes in this allocation."""
        return self.sched_data['alloc_summary']['total_cpu']

    @dfr_var_method
    def test_node_list(self):
        """A list of nodes dedicated to this test run."""
        return self.alloc_node_list()

    @dfr_var_method
    def test_node_list_short(self):
        """Node list, compressed in a slurm compatible way."""

        return Slurm.short_node_list(
            self.test_node_list().split(),
            self.sched.logger)

    @dfr_var_method
    def test_nodes(self):
        """The number of nodes allocated for this test (may be less than the
        total in this allocation)."""

        num_nodes = self.sched_config.get('num_nodes')

        if '-' in num_nodes:
            _, nmax = num_nodes.split('-', 1)
        else:
            nmax = num_nodes

        if nmax == 'all':
            return self.alloc_nodes()
        else:
            # This assumes we'll never have an allocation less than the min
            # number of requested nodes.
            return min(nmax, self.alloc_nodes())

    @dfr_var_method
    def test_procs(self):
        """The number of processors to request for this test."""

        alloc_nodes = list(self.sched_data['alloc_nodes'].values())
        alloc_nodes.sort(key=lambda v: v['CPUTot'], reverse=True)

        biggest_nodes = alloc_nodes[:int(self.test_nodes())]
        total_procs = sum([n['CPUTot'] for n in biggest_nodes])

        # The requested processors is the number per node times
        # the actual number of nodes.

        req_procs = self.sched_config.get('tasks_per_node')
        if req_procs == 'all':
            req_procs = int(self['min_ppn'])
        else:
            req_procs = int(req_procs)
        req_procs = req_procs * int(self.test_nodes())

        # We can't request more processors than there are, nor
        # should we return more than requested.
        return min(total_procs, req_procs)

    @dfr_var_method
    def test_cmd(self):
        """Construct a cmd to run a process under this scheduler, with the
        criteria specified by this test.
        """

        # Note that this is expected to become significantly more complicated
        # as we add additional constraints.

        cmd = ['srun',
               '-N', self.test_nodes(),
               '-n', self.test_procs()]

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


class Slurm(schedulers.SchedulerPlugin):
    """Schedule tests with Slurm!"""

    KICKOFF_SCRIPT_EXT = '.sbatch'

    VAR_CLASS = SlurmVars

    NUM_NODES_REGEX = re.compile(r'^(\d+|all)(-(\d+|all))?$')

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
        r'([a-zA-Z][a-zA-Z_-]*\d*)\[(.*)\]'
    )

    def __init__(self):
        super().__init__(
            'slurm',
            "Schedules tests via the Slurm scheduler.",
            priority=10)

        self.node_data = None

    @staticmethod
    def _get_config_elems():
        return [
            yc.StrElem(
                'num_nodes', default="1",
                help_text="Number of nodes requested for this test. "
                          "This can be a range (e.g. 12-24)."),
            yc.StrElem('tasks_per_node', default="1",
                       help_text="Number of tasks to run per node."),
            yc.StrElem(
                'mem_per_node',
                help_text="The minimum amount of memory required in GB. "
                          "This can be a range (e.g. 64-128)."),
            yc.StrElem(
                'partition', default="standard",
                help_text="The partition that the test should be run "
                          "on."),
            yc.StrElem(
                'immediate', choices=['true', 'false', 'True', 'False'],
                default='false',
                help_text="Only consider nodes not currently running jobs"
                          "when determining job size. Will set the minimum"
                          "number of nodes "
            ),
            yc.StrElem('qos',
                       help_text="The QOS that this test should use."),
            yc.StrElem('account',
                       help_text="The account that this test should run "
                                 "under."),
            yc.StrElem('reservation',
                       help_text="The reservation that this test should "
                                 "run under."),
            yc.RegexElem(
                'time_limit', regex=r'^(\d+-)?(\d+:)?\d+(:\d+)?$',
                help_text="The time limit to specify for the slurm job in"
                          "the formats accepted by slurm "
                          "(<hours>:<minutes> is typical)"),
            yc.RegexElem(
                'include_nodes', regex=Slurm.NODE_LIST_RE,
                help_text="The nodes to include, in the same format "
                          "that Slurm expects with the -w or -x option. "
                          "This will automatically increase num_nodes to "
                          "at least this node count."
            ),
            yc.RegexElem(
                'exclude_nodes', regex=Slurm.NODE_LIST_RE,
                help_text="A list of nodes to exclude, in the same format "
                          "that Slurm expects with the -w or -x option."
            ),
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
            yc.StrElem(
                'job_name', default="pav",
                help_text="The job name for this test."),

        ]

    def get_conf(self):
        """Set up the Slurm configuration attributes."""

        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the Slurm scheduler.",
            elements=self._get_config_elems()
        )

    def _get_data(self):
        """Get the slurm node state information.

        :returns: A dict with individual node and summary information.
        :rtype: dict
        """

        data = dict()
        data['nodes'] = self._collect_node_data()

        # Filter out 'nodes' that aren't a part of any partition.
        # These are typically front-end/login nodes.
        real_nodes = [n for n in data['nodes'].values() if
                      'Partitions' in n]
        data['summary'] = self._make_summary(real_nodes)

        # Get additional information specific to just our allocation.
        if self.in_alloc:
            alloc_nodes = os.environ.get('SLURM_NODELIST')
            alloc_nodes = self._collect_node_data(alloc_nodes)

            data['alloc_nodes'] = alloc_nodes
            data['alloc_summary'] = self._make_summary(alloc_nodes.values())

        return data

    # Callback functions to convert various node info fields into native types.
    NODE_FIELD_TYPES = {
        'CPUTot': int,
        'CPUAlloc': int,
        'CPULoad': slurm_float,
        # In MB
        'RealMemory': int,
        'State': slurm_states,
        'AllocMemory': int,
        'FreeMemory': int,
        'Partitions': lambda s: s.split(','),
        'AvailableFeatures': lambda s: s.split(','),
        'ActiveFeatures': lambda s: s.split(','),
    }

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

    @classmethod
    def short_node_list(cls, nodes: List[str], logger):
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
                logger.warning(
                    "Node '{}' did not match node_re when trying to dissect "
                    "node name in slurm.short_node_list."
                    .format(node))
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
                        .format(
                            start=start, last=last, num_digits=num_digits))

            num_list = ','.join(num_list)
            if ',' in num_list or '-' in num_list:
                seq_format = '{base}{z}[{num_list}]'
            else:
                seq_format = '{base}{z}{num_list}'

            node_seqs.append(
                seq_format
                .format(base=base, z='0' * pre_digits, num_list=num_list))

        return ','.join(node_seqs)

    def _collect_node_data(self, nodes=None):
        """Use the `scontrol show node` command to collect data on nodes.
        Types are converted according to self.FIELD_TYPES.

        :param str nodes: The nodes to collect data on. If None, collect
            data on all nodes. The format is slurm standard node list,
            which can include compressed series eg 'n00[20-99],n0101'
        :rtype: dict
        :returns: A dict of node dictionaries."""

        cmd = ['scontrol', 'show', 'node']

        if nodes is not None:
            cmd.append(nodes)

        sinfo = subprocess.check_output(cmd)
        sinfo = sinfo.decode('UTF-8')

        node_data = {}

        # Splits output by node record
        for node_section in sinfo.split('\n\n'):

            node_info = self._scontrol_parse(node_section)
            for key, val in node_info.items():
                if key in self.NODE_FIELD_TYPES:
                    node_info[key] = self.NODE_FIELD_TYPES[key](val)
                else:
                    node_info[key] = val

            if 'NodeName' in node_info:
                node_data[node_info['NodeName']] = node_info

        return node_data

    @staticmethod
    def _make_summary(nodes):
        """Get aggregate data about the given nodes. This includes:

- min_ppn - min procs per node
- max_ppn - max procs per node
- min_mem - min mem per node (in MiB)
- max_mem - min mem per node (in MiB)
- total_cpu - Total cpu's on these nodes.

:param typing.Iterable nodes: Node dictionaries as returned by
    _collect_node_data.
:rtype: dict
"""

        min_ppn = 0
        max_ppn = 0
        min_mem = 0
        max_mem = 0
        tot_cpu = 0

        data = dict()

        for node in nodes:
            # It's totally weird to start a max calculation from 0, but that
            # should be the default in this case anyway.
            if min_ppn == 0 or node['CPUTot'] < min_ppn:
                min_ppn = node['CPUTot']

            max_ppn = node['CPUTot'] if node['CPUTot'] > max_ppn else max_ppn

            tot_cpu += node['CPUTot']

            if min_mem == 0 or node['RealMemory'] < min_mem:
                min_mem = node['RealMemory']

            if node['RealMemory'] > max_mem:
                max_mem = node['RealMemory']

        data['min_ppn'] = min_ppn
        data['max_ppn'] = max_ppn
        data['min_mem'] = min_mem
        data['max_mem'] = max_mem
        data['total_cpu'] = tot_cpu

        return data

    # pylint: disable=arguments-differ
    def _filter_nodes(self, min_nodes, config, nodes):
        """Filter the system nodes down to just those we can use. For each step,
        we check to make sure we still have the minimum nodes needed in order
        to give more relevant errors.

        :param int min_nodes: The minimum number of nodes desired. This will
        :param dict config: The scheduler config for a test.
        :param [list] nodes: Nodes (as defined by collect node data)
        :returns: A list of node names that are compatible with the given
            config.
        :rtype: list
        """

        # Remove any nodes that aren't compute nodes.
        nodes = list(filter(lambda n: 'Partitions' in n and 'State' in n,
                            nodes))

        up_states = config['up_states']

        include_nodes = self.parse_node_list(config['include_nodes'])
        exclude_nodes = self.parse_node_list(config['exclude_nodes'])

        def in_up_states(state):
            """state in up states"""
            return state in config['up_states']

        # Nodes can be in multiple simultaneous states. Only include nodes
        # for which all of their states are in the 'up_states'.
        nodes = [node for node in nodes if
                 all(map(in_up_states, node['State']))]
        if min_nodes > len(nodes):
            raise SchedulerPluginError(
                "Insufficient nodes in up states: {}. Needed {}, found {}."
                .format(up_states, min_nodes,
                        [node['NodeName'] for node in nodes]))

        # Check for compute nodes that are part of the right partition.
        partition = config['partition']
        nodes = list(filter(lambda n: partition in n['Partitions'], nodes))

        if min_nodes > len(nodes):
            raise SchedulerPluginError('Insufficient nodes in partition '
                                       '{}.'.format(partition))

        if config['immediate'].lower() == 'true':

            def in_avail(state):
                """state in avail_states."""
                return state in config['avail_states']

            # Check for compute nodes in this partition in the avail states.
            nodes = [node for node in nodes
                     if all(map(in_avail, node['State']))]

            if min_nodes > len(nodes):
                raise SchedulerPluginError(
                    'Insufficient nodes in partition {} and states {}.'
                    .format(partition, config['avail_states']))

        tasks_per_node = config.get('tasks_per_node')
        # When we want all the CPUs, it doesn't matter how many are on a node.
        tasks_per_node = 0 if tasks_per_node == 'all' else int(tasks_per_node)
        nodes = list(filter(lambda n: tasks_per_node <= n['CPUTot'], nodes))

        # Remove any specifically excluded nodes.
        nodes = [node for node in nodes
                 if node['NodeName'] not in exclude_nodes]
        node_names = [node['NodeName'] for node in nodes]
        for name in include_nodes:
            if name not in node_names:
                raise SchedulerPluginError(
                    "Specifically requested node '{}', but it was determined "
                    "to be unavailable.".format(name))

        if min_nodes > len(nodes):
            raise SchedulerPluginError(
                'Insufficient nodes with more than {} procs per node available.'
                .format(tasks_per_node))

        return nodes

    def _in_alloc(self):
        """Check if we're in an allocation."""

        return 'SLURM_JOBID' in os.environ

    def available(self):
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

    def _schedule(self, test, kickoff_path):
        """Submit the kick off script using sbatch.

        :param TestRun test: The TestRun we're kicking off.
        :param Path kickoff_path: The kickoff script path.
        """

        if not kickoff_path.is_file():
            raise SchedulerPluginError(
                'Submission script {} not found'.format(kickoff_path))

        slurm_out = test.path/'slurm.log'

        proc = subprocess.Popen(['sbatch',
                                 '--output={}'.format(slurm_out),
                                 kickoff_path.as_posix()],
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

    def job_status(self, pav_cfg, test):
        """Get the current status of the slurm job for the given test."""

        try:
            job_info = self._scontrol_show('job', test.job_id)
        except ValueError as err:
            return StatusInfo(
                state=STATES.SCHED_ERROR,
                note=str(err),
                when=self._now()
            )

        if not job_info:
            return StatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(test.job_id),
                when=self._now()
            )

        # scontrol show returns a list. There should only be one item in that
        # list though.
        job_info = job_info.pop(0)
        if job_info:
            self.logger.info("Extra items in show job output: %s", job_info)

        job_state = job_info.get('JobState', 'UNKNOWN')
        if job_state in self.SCHED_WAITING:
            return StatusInfo(
                state=STATES.SCHEDULED,
                note=("Job {} has state '{}', reason '{}'"
                      .format(test.job_id, job_state, job_info.get('Reason'))),
                when=self._now()
            )
        elif job_state in self.SCHED_RUN:
            # The job should be running. Check it's status again.
            status = test.status.current()
            if status.state != STATES.SCHEDULED:
                return status
            else:
                return StatusInfo(
                    state=STATES.SCHEDULED,
                    note=("Job is running or about to run. Has job state {}"
                          .format(job_state)),
                    when=self._now()
                )
        elif job_state in self.SCHED_ERROR:
            # The job should have run enough to change it's state, but
            # might not have.
            status = test.status.current()
            if status.state != STATES.SCHEDULED:
                return status
            else:
                return test.status.set(
                    STATES.SCHED_ERROR,
                    "The scheduler killed the job, it has job state '{}'"
                    .format(job_state))

        elif job_state in self.SCHED_CANCELLED:
            # The job appears to have been cancelled without running.

            test.set_run_complete()
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state)
            )

        self.logger.warning("Encountered unhandled job state '%s' for"
                            "job '%s'.", job_state, test.job_id)
        # The best we can say is that the test is still SCHEDULED. After all,
        # it might be! Who knows.
        return StatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. We have no"
                 "idea what is going on.".format(test.job_id, job_state),
            when=self._now()
        )

    def _get_kickoff_script_header(self, test):
        """Get the kickoff header. Most of the work here """

        sched_config = test.config[self.name]

        nodes = self.get_data()['nodes']

        return SbatchHeader(sched_config,
                            self._get_node_range(sched_config, nodes.values()),
                            test.id,
                            self.get_vars(test))

    def _get_node_range(self, sched_config, nodes):
        """Translate user requests for a number of nodes into a numerical
        range based on the number of nodes on the actual system.

        :param dict sched_config: The scheduler config for a particular test.
        :param list nodes: A list of nodes.
        :rtype: str
        :returns: A range suitable for the num_nodes argument of slurm.
        """

        # Figure out the requested number of nodes
        num_nodes = sched_config.get('num_nodes')

        if self.NUM_NODES_REGEX.match(num_nodes) is None:
            raise SchedulerPluginError(
                "Invalid value for 'num_nodes'. Got '{}', expected something "
                "like '3', 'all', or '1-all'.".format(num_nodes))

        min_all = False
        if '-' in num_nodes:
            min_nodes, max_nodes = num_nodes.split('-')
        else:
            min_nodes = max_nodes = num_nodes

        if min_nodes == 'all':
            # We'll translate this to something else in a bit.
            min_nodes = '1'
            min_all = True

        nodes = self._filter_nodes(int(min_nodes), sched_config, nodes)

        include_nodes = self.parse_node_list(sched_config['include_nodes'])
        if min_all:
            min_nodes = len(nodes)
        else:
            min_nodes = int(min_nodes)
            if include_nodes:
                min_nodes = max(len(include_nodes), min_nodes)

        if max_nodes == 'all':
            max_nodes = len(nodes)
        else:
            max_nodes = int(max_nodes)

        return '{}-{}'.format(min_nodes, max_nodes)

    def _cancel_job(self, test):
        """Scancel the job attached to the given test.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: A statusInfo object with the latest scheduler state.
        :rtype: StatusInfo
        """

        cmd = ['scancel', test.job_id]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            # Scancel successful, pass the stdout message
            test.set_run_complete()
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Slurm jobid {} canceled via slurm.".format(test.job_id),
            )
        else:
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Tried (but failed) to cancel job: {}".format(stderr))
            # Scancel failed, pass the stderr message
