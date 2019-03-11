from pavilion import status_file
from pavilion import scheduler_plugins
from pavilion import scriptcomposer

class Slurm(scheduler_plugins.SchedulerPlugin):

    def __init__(self):
        super().__init__(name='slurm', priority=10)
        self.node_data = None

#    def _get(self, var):
#        """Base method for getting variable values from the slurm scheduler."""
#        if var in ['down_nodes', 'unused_nodes', 'busy_nodes', 'maint_nodes',
#                   'other_nodes'] and \
#           self.values[var] is None:
#            # Retrieve the full list of nodes and their states.
#            sinfo = subprocess.check_output(['sinfo', '--noheader'
#                                             '-o "%20E %12U %19H %.6D %6t %N"']
#                                            ).decode('UTF-8').split('\n')
#
#            # Lists to be populated with node names.
#            down_list = []
#            unused_list = []
#            busy_list = []
#            maint_list = []
#            other_list = []
#            prefix = ''
#            # Iterating through the lines of the sinfo output.
#            for line in sinfo:
#                line = line[1:-1]
#                items = line.split()
#                nodes = items[5]
#                node_list = []
#
#                # If prefix hasn't been set, set it.
#                if prefix == '':
#                   for letter in nodes:
#                       if letter.isalpha():
#                           prefix.append(letter)
#                       else:
#                           break
#
#                # Strip the prefix from the node list
#                nodes = nodes[len(prefix):]
#
#                # Strip any extra zeros as well as any brackets from node list.
#                nzero = 0
#                if nodes[0] == '[' and nodes[-1] == ']':
#                    nodes = nodes[1:-1]
#                elif nodes[0] != '[' and nodes[-1] == ']':
#                    for char in nodes:
#                        if char == '[':
#                            break
#                        nzero += 1
#                    nodes = nodes[nzero+1:-1]
#
#                # Split node list by individuals or ranges.
#                nodes = nodes.split(',')
#
#                # Expand ranges to an explicit list of every node.
#                for node in nodes:
#                    if '-' in node:
#                        node_len = len(node.split('-')[0])
#                        for i in range(node.split('-')[0], node.split('-')[1]):
#                            node_list.append(prefix +
#                                                str(i).zfill(node_len + nzero))
#                    else:
#                        node_list.append(prefix + nzero + node)
#
#                # Determine to which list this set of nodes belongs.
#                state = items[4]
#                if state[:3] == 'down' or state[:4] == 'drain' or
#                   state[:3] == 'drng':
#                    down_list.extend(node_list)
#                elif state[:4] == 'alloc' or state[:3] == 'resv':
#                    busy_list.extend(node_list)
#                elif state[:4] == 'maint':
#                    maint_list.extend(node_list)
#                elif state[:3] == 'idle':
#                    unused_list.extend(node_list)
#                else:
#                    other_list.extend(node_list)
#
#            # Assign to related class-level variables.
#            self.values['down_nodes'] = down_list
#            self.values['unused_nodes'] = unused_list
#            self.values['busy_nodes'] = busy_list
#            self.values['maint_nodes'] = maint_list
#            self.values['other_nodes'] = other_list
#
#        return self.values[var]

    def _collect_data(self):
        """Use the `scontrol show node` command to collect data on all
           available nodes.  A class-level dictionary is being populated."""
        sinfo = subprocess.check_output(
                                  ['scontrol', 'show', 'node']).decode('UTF-8')

        for node in sinfo.split('\n\n'):
            node_info = {}
            for line in node.split('\n'):
                if line.strip() != '' and item.strip()[:3] != 'OS=' and
                   item.strip()[:7] != 'Reason=':
                    for item in line.strip().split():
                        node_info[item.split('=').strip()] =
                                                      item.split('=').strip()
                elif item.strip()[:3] == 'OS=' or
                     item.strip()[:7] == 'Reason=':
                    node_info[item.strip().split('=')[0]] =
                                                   item.strip().split('=')[1]
            self.node_data[node_info['NodeName']] = node_info

    def check_request(self, partition='standard', state='IDLE', nodes=1,
                      ppn=1, req_type=None):

        self._collect_data()

        min_nodes = 1
        max_nodes = 1
        if '-' in nodes:
            node_split = nodes.split('-')
            min_nodes = node_split[0]
            max_nodes = node_split[1]
        else:
            min_nodes = nodes
            max_nodes = nodes

        min_ppn = 1
        max_ppn = 1
        if '-' in ppn:
            ppn_split = ppn.split('-')
            min_ppn = ppn_split[0]
            max_ppn = ppn_split[1]
        else:
            min_ppn = ppn
            max_ppn = ppn

        max_avail_nodes = True if max_nodes == 'all' else False
        min_nodes = max_nodes if min_nodes == 'all'
        max_avail_ppn = True if max_ppn == 'all' else False
        min_ppn = max_ppn if min_ppn == 'all'

        # Lists for internal uses
        comp_nodes = []
        partition_nodes = []
        state_nodes = []
        ppn_nodes = []
        max_found_ppn = 1

        # Collect the list of nodes that are compute nodes.  Determined by
        # whether or not they have the keys 'Partitions' and 'State'.
        for node in list(self.node_data.keys()):
            if 'Partitions' in list(self.node_data[node].keys()) and
               'State' in list(self.node_data[node].keys()):
                comp_nodes.append(node)
                max_found_ppn = max([max_found_ppn,
                                     self.node_data[node]['CPUTot']])

        if min_nodes > len(comp_nodes):
            raise SchedulerPluginError('Insufficient compute nodes.')

        # Set default maxes based on collected node lists.
        if max_avail_nodes:
            max_nodes = len(comp_nodes)

        if max_found_ppn < min_ppn:
            raise SchedulerPluginError('Insufficient nodes with ' + \
                                       '{} procs per node.'.format(min_ppn))
        elif max_avail_ppn:
            max_ppn = max_found_ppn

        # Check for compute nodes that are part of the right partition.
        max_found_ppn = 1
        for node in list(self.node_data.keys()):
            if partition in self.node_data[node]['Partitions']:
                partition_nodes.append(node)
                max_found_ppn = max([max_found_ppn,
                                     self.node_data[node]['CPUTot']])

        if min_nodes > len(partition_nodes):
            raise SchedulerPluginError('Insufficient nodes in partition ' + \
                                       '{}.'.format(partition))

        if max_found_ppn < min_ppn:
            raise SchedulerPluginError('Insufficient nodes with ' + \
                                       '{} procs per node.'.format(min_ppn))

        if req_type == 'immediate':
            # Check for compute nodes in this partition in the right state.
            for node in partition_nodes:
                if state in self.node_data[node]['State']
                    state_nodes.append(node)

            if min_nodes > len(state_nodes):
                raise SchedulerPluginError('Insufficient nodes in partition'+\
                                           ' {} and state {}.'.format(
                                                              patition, state))

            # Check that compute nodes in the right partition and state have
            # enough processors to match the requirements.
            for node in state_nodes:
                if self.node_data[node]['CPUTot'] >= min_ppn and
                   self.node_data[node]['CPUTot'] <= max_ppn:
                    ppn_nodes.append(node)
        elif req_type == 'wait':
            for node in partition_nodes:
                if self.node_data[node]['CPUTot'] >= min_ppn and
                   self.node_data[node]['CPUTot'] <= max_ppn:
                    ppn_nodes.append(node)
        else:
            raise SchedulerPluginError("Request type {} ".format(req_type)+\
                                       "not recognized.")

        if min_nodes > len(ppn_nodes):
            raise SchedulerPluginError('Insufficient nodes in partition ' + \
                                       '{}.'.format(partition))

        if len(ppn_nodes) >= max_nodes:
            num_nodes = max_nodes
        else:
            num_nodes = ppn_nodes

        max_procs = 1
        min_procs = None
        for node in ppn_nodes:
            if min_procs is None:
                min_procs = self.node_data[node]['CPUTot']
            else:
                min_procs = min(min_procs, self.node_data[node]['CPUTot'])
            max_procs = max(max_procs, self.node_data[node]['CPUTot'])

        if ppn_min > max_procs:
            raise SchedulerPluginError('Too many processors requested.')
        elif ppn_max < min_procs:
            num_procs = ppn_max
        elif max_procs < ppn_max:
            num_procs = max_procs

        return (num_nodes, num_procs)

    def get_script_headers(self, partition=None, reservation=None, qos=None,
                           account=None, num_nodes=None, ppn=None,
                           time_limit=None):
        """Function to accept a series of job submission resource requests and
           return a list of lines to go in a submission script.
        """
        line_list = []
        if partition is None:
            partition = 'standard'

        check_partition(partition)

        if not subprocess.check_call(['scontrol', 'show', 'partition',
                                                                   partition]):
            raise SchedulerPluginError('Partition {} not found.'.format(
                                                                    partition))

        line_list.append('#SBATCH -p {}'.format(partition))

        if reservation is not None:
            if not check_reservation(reservation):
                raise SchedulerPluginError('Reservation {} not found.'.format(
                                                                  reservation))
            else:
                line_list.append('#SBATCH --reservation={}'.format(
                                                                  reservation))

        if qos is not None:
            line_list.append('#SBATCH -q {}'.format(qos))

        if account is not None:
            line_list.append('#SBATCH --account={}'.format(account))

        if num_nodes is None:
            raise SchedulerPluginError('A number of nodes must be provided.')

        line_list.append('#SBATCH -N {}'.format(num_nodes))

        if ppn is not None:
            line_list.append('#SBATCH --ntasks-per-node={}'.format(ppn))

        if time_limit is not None:
            line_list.append('#SBATCH -t {}'.format(time_limit))

        return line_list

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
        try:
            subprocess.check_call(['scontrol', 'show', 'reservation',
                                                                    res_name]):
            return True
        except subprocess.CalledProcessError:
            return False

    def check_partition(self, partition):
        try:
            subprocess.check_call(['scontrol', 'show', 'partition', partition])
        except subprocess.CalledProcessError:
            raise SchedulerPluginError('Partition {} not found.'.format(
                                                                    partition))

    def kick_off(self, test_obj=None):
        slurm = test_obj.config['slurm']
        job_id = self._kick_off(slurm['partition'], slurm['reservation'],
                                slurm['qos'], slurm['account'],
                                slurm['num_nodes'], slurm['ppn'],
                                slurm['time_limit'], test_obj.id,
                                test_obj.path)

        test_obj.job_id = job_id
        test_obj.status.set(self.status.STATES.SCHEDULED,
                            "Test has slurm job ID {}.".format(job_id))

    def _kick_off(self, partition='standard', reservation=None, qos=None,
                  account=None, num_nodes=1, ppn=1, time_limit='01:00:00',
                  test_id=None, test_path=None):
        sbatch_script = scriptcomposer.ScriptComposer()
        sbatch_script.addCommand('#SBATCH -p {}'.format(partition))
        if reservation is not None:
            sbatch_script.addCommand('#SBATCH --reservation {}'
                                     .format(reservation))
        if qos is not None:
            sbatch_script.addCommand('#SBATCH --qos {}'.format(qos))
        if account is not None:
            sbatch_script.addCommand('#SBATCH --account {}'.format(account))
        sbatch_script.addCommand('#SBATCH -N {}'.format(num_nodes))
        sbatch_script.addCommand('#SBATCH --tasks-per-node={}'.format(ppn))
        sbatch_script.addCommand('#SBATCH -t {}'.format(time_limit))

        sbatch_script.addNewline()

        sbatch_script.addCommand('pav run {}'.format(test_id))

        sbatch_script.writeScript(dirname=test_path)

        job_id = self.submit_job(os.path.join(test_path,
                                              sbatch_script.details.name))

        return job_id

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
            request_avail = os.getenv('SLURM_JOB_NUM_NODES')
        elif name == 'procs_per_node':
            request_avail = os.getenv('SLURM_JOB_CPUS_PER_NODE')
        elif name == 'mem_per_node':
            check = subprocess.check_output(['scontrol', '-o', 'show',
                                             'node', '$(hostname)']).split()
            for item in check:
                if item[:8] == 'FreeMem=':
                    request_avail = item.split('=')[1]
                    break

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
        elif num_nodes_avail < request_max:
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
