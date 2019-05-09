from pavilion import scriptcomposer
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_var_method
from pavilion.var_dict import var_method
import os
import yaml_config as yc
import re
import subprocess


class SbatchHeader(scriptcomposer.ScriptHeader):
    def __init__(self, sched_config, nodes, id):
        super().__init__()

        self._conf = sched_config
        self._id = id
        self._nodes = nodes

    def get_lines(self):

        lines = super().get_lines()

        lines.append('#SBATCH --job_name "pav test #{s.id}"'.format(s=self))
        lines.append('#SBATCH -p {s._conf[partition]}'.format(s=self))
        if self._conf.get('reservation') is not None:
            lines.append('#SBATCH --reservation {s._conf[reservation]}'
                         .format(s=self))
        if self._conf.get('qos') is not None:
            lines.append('#SBATCH --qos {s._conf[qos]}'.format(s=self))
        if self._conf.get('account') is not None:
            lines.append('#SBATCH --account {s._conf[account]}'.format(s=self))

        lines.append('#SBATCH -N {s.nodes}'.format(s=self))
        lines.append('#SBATCH --tasks-per-node={s._conf['
                     'tasks_per_node]}'.format(s=self))
        lines.append('#SBATCH -t {s._conf[time_limit]}'.format(s=self))

        return lines


class SlurmVars(SchedulerVariables):
    @var_method
    def min_ppn(self):
        """The minimum processors per node across all nodes."""
        return self.sched_data['min_ppn']

    @var_method
    def max_ppn(self):
        """The maximum processors per node across all nodes."""
        return self.sched_data['max_ppn']

    @var_method
    def min_mem(self):
        """The minimum memory per node across all nodes (in MiB)."""
        return self.sched_data['min_ppn']

    @var_method
    def max_mem(self):
        """The maximum memory per node across all nodes (in MiB)."""


    @dfr_var_method
    def alloc_nodes(self):
        """The number of nodes in this allocation."""
        return os.getenv('SLURM_NNODES')

    @dfr_var_method
    def alloc_node_list(self):
        """A space separated list of nodes in this allocation."""
        final_list = []
        nodelist = os.getenv('SLURM_NODELIST')

        if '[' in nodelist:
            prefix = nodelist.split('[')[0]
            nodes = nodelist.split('[')[1].split(']')[0]

            range_list = nodes.split(',')

            for item in range_list:
                if '-' in item:
                    node_range = range(int(item.split('-')[0]),
                                       int(item.split('-')[1])+1)
                    zfill = len(item.split('-')[0])
                    for i in range(0, len(node_range)):
                        final_list.append(str(node_range[i]).zfill(zfill))
                else:
                    final_list.append(item)

            for i in range(0, len(final_list)):
                final_list[i] = prefix + final_list[i]
        else:
            final_list.append(nodelist)

        # Deferred variables can't be lists, so we have to make this into
        # a space separated string.
        return ' '.join(final_list)

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
    def test_nodes(self):
        """The number of nodes allocated for this test (may be less than the
        total in this allocation)."""

        num_nodes = self.test.config['slurm'].get('num_nodes')

        _, nmax = num_nodes.split('-') if '-' in num_nodes else None, num_nodes

        if nmax == 'all':
            return self.alloc_nodes()
        else:
            return nmax

    @dfr_var_method
    def test_procs(self):
        """The number of processors to request for this test."""

        alloc_nodes = self.sched_data['alloc_nodes'].values()
        alloc_nodes.sort(lambda v: v['CPUTot'], reverse=True)

        biggest_nodes = alloc_nodes[:int(self.test_nodes)]
        return sum([n['CPUTot'] for n in biggest_nodes])

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
    if val == 'N/A':
        return None
    else:
        return float(val)


class Slurm(SchedulerPlugin):

    KICKOFF_SCRIPT_EXT = '.sbatch'

    VAR_CLASS = SlurmVars

    def __init__(self):
        super().__init__(name='slurm', priority=10)

        self.node_data = None

    def _get_conf(self):
        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the Slurm scheduler.",
            elements=[
                yc.StrElem(
                    'num_nodes',
                    default="1",
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
                yc.StrElem('qos',
                           help_text="The QOS that this test should use."),
                yc.StrElem('account',
                           help_text="The account that this test should run "
                                     "under."),
                yc.StrElem('reservation',
                           help_text="The reservation that this test should "
                                     "run under."),
                yc.StrElem('time_limit',
                           help_text="The time limit to specify for the slurm "
                                     "job.  This can be a range (e.g. "
                                     "00:02:00-01:00:00)."),
                yc.StrElem(name='immediate',
                           choices=['true', 'false'],
                           default='false',
                           help_text="If set to immediate, this test will fail "
                                     "to kick off if the expected resources "
                                     "aren't immediately available."),
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
                ])

    def _get_data(self):

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

            data['alloc_nodes'] = self._collect_node_data(alloc_nodes)
            data['alloc_summary'] = self._make_summary(alloc_nodes.values())

        return data

    NODE_FIELD_TYPES = {
        'CPUTot': int,
        'CPUAlloc': int,
        'CPULoad': slurm_float,
        # In MB
        'RealMemory': int,
        'AllocMemory': int,
        'FreeMemory': int,
        'Partitions': lambda s: s.split(','),
        'AvailableFeatures': lambda s: s.split(','),
        'ActiveFeatures': lambda s: s.split(','),
    }

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

            node_info = self.parse_scontrol(node_section)
            for k,v in node_info.items():
                if k in self.NODE_FIELD_TYPES:
                    node_info[k] = self.NODE_FIELD_TYPES[v]

            node_data[node_info['NodeName']] = node_info

        return node_data

    def _make_summary(self, nodes):
        """Get aggregate data about the given nodes. This includes:
            - min_ppn - min procs per node
            - max_ppn - max procs per node
            - min_mem - min mem per node (in MiB)
            - max_mem - min mem per node (in MiB)
            - total_cpu - Total cpu's on these nodes.
        :param typing.Iterable nodes: Node dictionaries as returned by
        _collect_node_data.
        :rtype: dict"""

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

    def _filter_nodes(self, min, config, nodes):
        """Filter the system nodes down to just those we can use. For each step,
        we check to make sure we still have the minimum nodes needed in order
        to give more relevant errors.

        :param int min: The minimum number of nodes desired. This will
        :param dict config: The scheduler config for a test.
        :param [dict] nodes: Nodes (as defined by collect node data)
        :returns: A list of node names that are compatible with the given
        config.
        :rtype: list
        """

        # Remove any nodes that aren't compute nodes.
        nodes = list(filter(lambda n: 'Partitions' in n and 'State' in n,
                            nodes))

        # Remove nodes that aren't up.
        up_states = config['up_states']
        nodes = list(filter(lambda n: n['State'] in up_states, nodes))
        if min > len(nodes):
            raise SchedulerPluginError("Insufficient nodes in up states: {}"
                                       .format(up_states))

        # Check for compute nodes that are part of the right partition.
        partition = config['partition']
        nodes = list(filter(lambda n: partition in n['Partitions'], nodes))

        if min > len(nodes):
            raise SchedulerPluginError('Insufficient nodes in partition '
                                       '{}.'.format(partition))

        if config['immediate'] == 'true':
            states = config['avail_states']
            # Check for compute nodes in this partition in the right state.
            nodes = list(filter(lambda n: n['State'] in states, nodes))

            if min > len(nodes):
                raise SchedulerPluginError('Insufficient nodes in partition'
                                           ' {} and states {}.'
                                           .format(partition, states))

        tasks_per_node = config.get('tasks_per_node')
        # When we want all the CPUs, it doesn't matter how many are on a node.
        tasks_per_node = 0 if tasks_per_node == 'all' else int(tasks_per_node)
        nodes = list(filter(lambda n: tasks_per_node <= n['CPUTot'], nodes))

        if min > len(nodes):
            raise SchedulerPluginError('Insufficient nodes with more than {} '
                                       'procs per node available.'
                                       .format(tasks_per_node))

        return nodes

    def _in_alloc(self):
        """Check if we're in an allocation."""

        return 'SLURM_JOBID' in os.environ

    def _schedule(self, script_path, output_path):
        """Submit the kick off script using sbatch."""

        if os.path.isfile(script_path):
            job_id = subprocess.check_output(['sbatch', script_path])
            job_id = job_id.decode('UTF-8').strip().split()[-1]
        else:
            raise SchedulerPluginError('Submission script {}'.format(script_path) +\
                                       ' not found.')
        return job_id

    SCONTROL_KEY_RE = re.compile(r'(?:^|\s+)([A-Z][a-zA-Z0-9:/]*)=')
    SCONTROL_WS_RE = re.compile(r'\s+')

    def parse_scontrol(self, section):

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

    def check_job(self, id):
        job_dict = {}
        try:
            job_output = subprocess.check_output(
                ['scontrol', 'show', 'job', id])
            job_output = job_output.decode('UTF-8').split()
            for item in job_output:
                item = item.strip()
                if not item:
                    continue
                key, value = item.split('=', 1)
                job_dict[key] = value
        except subprocess.CalledProcessError:
            raise SchedulerPluginError('Job {} not found.'.format(id))

        try:
            value = job_dict[key]
        except KeyError:
            raise SchedulerPluginError('Key {} not found in '.format(key) +\
                                       'scontrol output.')

        ret_val = None
        run_list = ['RUNNING', 'COMPLETING', 'CONFIGURING']
        pend_list = ['PENDING']
        finish_list = ['COMPLETED']
        fail_list = ['BOOT_FAIL', 'FAILED', 'DEADLINE', 'NODE_FAIL',
                     'PREEMPTED', 'OUT_OF_MEMORY', 'TIMEOUT']

        if key == 'JobState':
            if value in run_list:
                ret_val = 'running'
            elif value in pend_list:
                ret_val = 'pending'
            elif value in finish_list:
                ret_val = 'finished'
            elif value in fail_list:
                ret_val = 'failed'
            else:
                raise SchedulerPluginError('Job status {} not recognized.'
                                           .format(key))

        return ret_val

    def check_reservation(self, res_name):
        cmd = ['scontrol', 'show', 'reservation', res_name]
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_kickoff_script_header(self, test):
        """Get the kickoff header. Most of the work here """

        sched_config = test.config.get(self.name)

        nodes = self.get_data()['nodes']

        return SbatchHeader(sched_config,
                            self._get_node_range(sched_config, nodes),
                            test.id)

    def _get_node_range(self, sched_config, nodes):
        """Translate user requests for a number of nodes into a numerical
        range based on the number of nodes on the actual system.
        :param dict sched_config: The scheduler config for a particular test.
        :returns: A range suitable for the num_nodes argument of slurm."""

        # Figure out the requested number of nodes
        num_nodes = sched_config.get('num_nodes')
        min_all = False
        if '-' in num_nodes:
            min_nodes, max_nodes = num_nodes.split()

            if min_nodes == 'all':
                # We'll translate this to something else in a bit.
                min_nodes = '1'
                min_all = True
        else:
            min_nodes = max_nodes = num_nodes

        try:
            min_nodes = int(min_nodes)
        except ValueError:
            raise SchedulerPluginError(
                "Invalid num_nodes minimum value: {}"
                .format(min_nodes))

        nodes = self._filter_nodes(min_nodes, sched_config, nodes)

        if min_all:
            min_nodes = len(nodes)

        if max_nodes == 'all':
            max_nodes = len(nodes)
        else:
            try:
                max_nodes = int(max_nodes)
            except ValueError:
                raise SchedulerPluginError(
                    "Invalid num_nodes maximum value: {}".format(max_nodes))

        return '{}-{}'.format(min_nodes, max_nodes)
