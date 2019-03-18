from pavilion import config_format
from pavilion.scheduler_plugins import SchedulerPlugin, SchedulerPluginError, SchedVarDict
from pavilion import scriptcomposer
from pavilion import status_file
import pavilion.dependencies.yaml_config as yc
import subprocess
import os


class Slurm(SchedulerPlugin):

    def __init__(self):
        super().__init__(name='slurm', priority=10)
        self.name = name
        self.priority = priority
        self.node_data = None

        # Set up the config specification for the test configuration.

    def activate(self):
        """Specify the configuration details for the test configs."""

        self.conf = yc.KeyedElem(self.name, elements=[
            yc.StrElem('num_nodes', default="1",
                       help_text="Number of nodes requested for this test. "
                                 "This can be a range (e.g. 12-24)."),
            yc.StrElem('tasks_per_node', default="1",
                       help_text="Number of tasks to run per node.")
            yc.StrElem('mem_per_node',
                       help_text="The minimum amount of memory required in GB. "
                                 "This can be a range (e.g. 64-128)."),
            yc.StrElem('partition', default="standard",
                       help_text="The partition that the test should be run "
                                 "on."),
            yc.StrElem('qos',
                       help_text="The QOS that this test should run under."),
            yc.StrElem('account',
                       help_text="The account that this test should run "
                                 "under."),
            yc.StrElem('reservation',
                       help_text="The reservation that this test should run "
                                 "under."),
            yc.StrElem('time_limit',
                       help_text="The time limit to specify for the slurm "
                                 "job.  This can be a range (e.g. "
                                 "00:02:00-01:00:00)."),
            yc.StrElem(name='req_type', choices=['immediate', 'wait'], default='wait',
                       help_text="If set to immediate, this test will fail to kick off if "
                                 "the expected resources aren't immediately available."),
            yc.ListElem(name='states', sub_elem=yc.StrElem(), default=['IDLE', 'MAINT'],
                        help_text="When looking for immediately available nodes, they "
                                  "must be in one of these states."),
            ],
            help_text="Configuration for the Slurm scheduler.")

        config_format.TestConfigLoader.add_subsection( self.conf )

        super().activate()


    FIELD_TYPES = {
        'CPUTot': int,
        'Partitions': lambda s: s.split(','),
    }

    def _collect_data(self):
        """Use the `scontrol show node` command to collect data on all
           available nodes.  A class-level dictionary is being populated."""
        sinfo = subprocess.check_output(
                                  ['scontrol', 'show', 'node']).decode('UTF-8')

        # Splits output by node record
        for node in sinfo.split('\n\n'):
            node_info = {}
            # Splits each node's output by line
            for line in node.split('\n'):
                line = line.strip()

                # Skip if the line is empty
                if not line:
                    continue

                # Skipping emtpy lines and lines that start with OS= and
                # Reason= because those two instances use spaces.  For all
                # others, dividing the record up into key-value pairs and
                # storing in the dictionary for this node.
                if not (line.startswith('OS=') or line.startswith('Reason=')):
                    for item in line.split():
                        key, value = item.split('=', 1)
                        if key in self.FIELD_TYPES:
                            value = self.FIELD_TYPES[key](value)
                        node_info[key] = value

                # For the OS= and Reason= lines, just don't split on spaces.
                else:
                    key, value = line.split('=', 1)
                    node_info[key] = value

            # Store the result in a dictionary by node name with all info
            # provided by sinfo in a dictionary.
            self.node_data[node_info['NodeName']] = node_info

    def _check_request(self, partition,
                             nodes,
                             tasks_per_node,
                             req_type,
                             states):
        """
        :param str partition: Name of the desired partition.
        :param str nodes: The number of nodes desired, can be a range 'n-m'.
        :param str tasks_per_node: The number of processors per node desired, can be a range 'n-m'.
        :param str req_type: Type of request.  Options include 'immediate'
                             and 'wait'.  Specifies whether the request
                             must be available immediately or if the job
                             can be queued for later.
        :param list states: State of the desired partition.
        :return tuple(int, int): Tuple containing the number of nodes that
                                 can be used and the number of processors
                                 per node that can be used.
        """

        # Refresh the information from Slurm
        # TODO: Is this really the right place?
        self._collect_data()

        # Accept a range for the number of nodes.
        if '-' in nodes:
            min_nodes, max_nodes = nodes.split('-', 1)
        elif nodes == 'all':
            min_nodes = 1
            # We'll compute this based on the machines total nodes in a bit.
            max_nodes = None
        else:
            min_nodes = max_nodes = nodes

        try:
            min_nodes = int(min_nodes)
        except ValueError:
            raise SchedulerPluginError("Invalid minimum nodes value: '{}'"
                                       .format(min_nodes))

        tasks_per_node = int(tasks_per_node)

        # Lists for internal uses
        nodes = []

        # Collect the list of nodes that are compute nodes.  Determined by
        # whether or not they have the keys 'Partitions' and 'State'.
        for node in self.node_data.keys():
            if ('Partitions' in self.node_data[node] and
                'State' in self.node_data[node]):
                nodes.append(node)

        if max_nodes is None:
            max_nodes = len(nodes)
        else:
            try:
                max_nodes = int(max_nodes)
            except ValueError:
                raise SchedulerPluginError("Invalid maximum nodes value': {}"
                                           .format(max_nodes))

        if min_nodes is not 'all' and int(min_nodes) > len(nodes):
            raise SchedulerPluginError('Insufficient compute nodes.')

        # Check for compute nodes that are part of the right partition.
        nodes = list(filter(lambda n: partition in n['Partitions'], nodes))

        if min_nodes > len(nodes):
            raise SchedulerPluginError('Insufficient nodes in partition '
                                       '{}.'.format(partition))

        if req_type == 'immediate':
            # Check for compute nodes in this partition in the right state.
            nodes = list(filter(lambda n: n['State'] in states, nodes))

            if min_nodes > len(nodes):
                raise SchedulerPluginError('Insufficient nodes in partition'
                                           ' {} and states {}.'
                                           .format(partition, states))


        nodes = list(filter(lambda n: tasks_per_node <= n['CPUTot'], nodes))

        if min_nodes > len(nodes):
            raise SchedulerPluginError('Insufficient nodes with more than {} '
                                       'procs per node available.'
                                       .format(tasks_per_node))

        if min_nodes > len(nodes):
            raise SchedulerPluginError('No compute nodes with less than {} '
                                       'procs per node.'.format(max_ppn))

        num_nodes = '{}-{}'.format(min_nodes, max_nodes)

        return num_nodes

    def submit_job(self, path):
        if os.isfile(path):
            job_id = subprocess.check_output(['sbatch', path]
                                          ).decode('UTF-8').strip().split()[-1]
        else:
            raise SchedulerPluginError('Submission script {}'.format(path)+\
                                       ' not found.')
        return job_id

    def check_job(self, id, key=None):
        job_dict = {}
        try:
            job_output = subprocess.check_output(['scontrol', 'show', 'job',
                         id]).decode('UTF-8').split()
            for item in job_output:
                key, value = item.split('=')
                job_dict[key] = value
        except subprocess.CalledProcessError:
            raise SchedulerPluginError('Job {} not found.'.format(id))

        if key is None:
            key = 'JobState'

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
                raise SchedulerPluginError('Job status {} '.format(value) +\
                                           'not recognized.')

        return ret_val

    def check_reservation(self, res_name):
        cmd = ['scontrol', 'show', 'reservation', res_name]
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def check_partition(self, partition):
        for node in self.node_data:
            if partition in node['Partitions']:
                return
        raise SchedulerPluginError('Partition {} not found.'
                                   .format(partition))

    def _write_kick_off_script(self, test_path, run_cmd,
                               account=None,
                               num_nodes=None,
                               partition=None,
                               tasks_per_node=None,
                               qos=None,
                               req_type=None,
                               reservation=None,
                               states=None,
                               time_limit=None,
                               **kwargs):

        nodes = self._check_request(partition, num_nodes, tasks_per_node, req_type, states)

        sbatch_script = scriptcomposer.ScriptComposer(
            details=scriptcomposer.ScriptDetails(
                path=os.path.join(test_path, 'kickoff.sbatch')
            )
        )
        sbatch_script.command('#SBATCH -p {}'.format(partition))
        if reservation is not None:
            sbatch_script.command('#SBATCH --reservation {}'
                                     .format(reservation))
        if qos is not None:
            sbatch_script.command('#SBATCH --qos {}'.format(qos))
        if account is not None:
            sbatch_script.command('#SBATCH --account {}'.format(account))
        sbatch_script.command('#SBATCH -N {}'.format(nodes))
        sbatch_script.command('#SBATCH --tasks-per-node={}'.format(tasks_per_node))
        sbatch_script.command('#SBATCH -t {}'.format(time_limit))

        sbatch_script.newline()

        sbatch_script.command(run_cmd)

        sbatch_script.write()

        return sbatch_script.details.path


    def resolve_nodes_request(self, name, request):
        if name not in self.values and name != 'scheduler_plugin':
            raise SchedulerPluginError("'{}' not a resolvable request."
                                       .format(name))

        request_min = 1
        request_max = 1
        # Parse the request format
        if '-' in request:
            request_split = request.split('-')
            request_min = request_split[0]
            request_max = request_split[1]

        # Use scheduler-specific method of determining available resources.
        # Number of nodes is based on the SLURM_JOB_NUM_NODES environment
        # variable, which is populated by Slurm when inside of an allocation.
        if name == 'num_nodes':
            request_avail = self._get_num_nodes()
        elif name == 'procs_per_node':
            request_avail = self._get_min_ppn()
        elif name == 'mem_per_node':
            request_avail = self._get_mem_per_node()

        # The value should only be none if the environment variable was not
        # defined.
        if request_avail is None:
            raise SchedulerPluginError(
                           "Resolving requests for '{}' requires an allocation"
                           .format(name))

        # Determine if the request can be met and return the appropriate value.
        if request_avail < request_min:
            raise SchedulerPluginError(
                 "Available {} '{}' is less than minimum requested nodes '{}'."
                 .format(name, request_avail, request_min))
        elif request_avail < request_max:
            return request_avail
        else:
            return request_max


# Functions to run inside of an allocation to get job-specific values
    def _get_num_nodes(self):
        return os.getenv('SLURM_NNODES')


    def _get_node_list(self):
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

        return final_list


    def _get_min_ppn(self, node_list=None):
        if node_list is None:
            node_list = self._get_node_list()
        num_procs = None

        for node in node_list:
            node_procs = subprocess.check_output( ['ssh', node, 'nproc'] )
            if num_procs is not None:
                num_procs = min(num_procs, node_procs)
            else:
                num_procs = node_procs

        return num_procs


    def _get_tot_procs(self, node_list=None):
        if node_list is None:
            node_list = self._get_node_list()
        num_procs = 0

        for node in node_list:
            node_procs = subprocess.check_output( ['ssh', node, 'nproc'] )
            num_procs += node_procs

        return num_procs


    def _get_mem_per_node(self, node_list=None):
        if node_list is None:
            node_list = self._get_node_list()

        mem = None

        for node in node_list:
            cmd_list = ['ssh', 'node', 'free', '-g']
            node_mem = subprocess.check_output( cmd_list ).decode('UTF-8')
            for line in node_mem.split('\n'):
                if line[:4] == 'Mem:':
                    mem_free = line.split()[3]
                    break
            if mem is not None:
                mem = min(mem, int(mem_free))
            else:
                mem = int(mem_free)

        return mem

