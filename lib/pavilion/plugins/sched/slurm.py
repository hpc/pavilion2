import pavilion.scheduler_plugins as scheduler_plugins

class Slurm( scheduler_plugins.SchedulerPlugin ):

    def __init__( self ):
        super().__init__( name='slurm', priority=10 )
        self.node_data = None

    def _get( self, var ):
        """Base method for getting variable values from the slurm scheduler."""
        if var in [ 'down_nodes', 'unused_nodes', 'busy_nodes', 'maint_nodes',
                    'other_nodes' ] and \
           self.values[ var ] is None:
            # Retrieve the full list of nodes and their states.
            sinfo = subprocess.check_output(['sinfo', '--noheader'
                                             '-o "%20E %12U %19H %.6D %6t %N"']
                                            ).decode('UTF-8').split('\n')

            # Lists to be populated with node names.
            down_list = []
            unused_list = []
            busy_list = []
            maint_list = []
            other_list = []
            prefix = ''
            # Iterating through the lines of the sinfo output.
            for line in sinfo:
                line = line[1:-1]
                items = line.split()
                nodes = items[5]
                node_list = []

                # If prefix hasn't been set, set it.
                if prefix == '':
                   for letter in nodes:
                       if letter.isalpha():
                           prefix.append(letter)
                       else:
                           break

                # Strip the prefix from the node list
                nodes = nodes[len(prefix):]

                # Strip any extra zeros as well as any brackets from node list.
                nzero = 0
                if nodes[0] == '[' and nodes[-1] == ']':
                    nodes = nodes[1:-1]
                elif nodes[0] != '[' and nodes[-1] == ']':
                    for char in nodes:
                        if char == '[':
                            break
                        nzero += 1
                    nodes = nodes[nzero+1:-1]

                # Split node list by individuals or ranges.
                nodes = nodes.split(',')

                # Expand ranges to an explicit list of every node.
                for node in nodes:
                    if '-' in node:
                        node_len = len( node.split('-')[0] )
                        for i in range(node.split('-')[0], node.split('-')[1]):
                            node_list.append( prefix +
                                              str(i).zfill(node_len + nzero) )
                    else:
                        node_list.append( prefix + nzero + node )

                # Determine to which list this set of nodes belongs.
                state = items[4]
                if state[:3] == 'down' or state[:4] == 'drain' or
                   state[:3] == 'drng':
                    down_list.extend( node_list )
                elif state[:4] == 'alloc' or state[:3] == 'resv':
                    busy_list.extend( node_list )
                elif state[:4] == 'maint':
                    maint_list.extend( node_list )
                elif state[:3] == 'idle':
                    unused_list.extend( node_list )
                else:
                    other_list.extend( node_list )

            # Assign to related class-level variables.
            self.values[ 'down_nodes' ] = down_list
            self.values[ 'unused_nodes' ] = unused_list
            self.values[ 'busy_nodes' ] = busy_list
            self.values[ 'maint_nodes' ] = maint_list
            self.values[ 'other_nodes' ] = other_list

        return self.values[ var ]

    def check_reservation( self, res_name ):
        """Check the status of a requested reservation."""
        if not subprocess.check_call( [ 'scontrol', 'show', 'reservation',
                                                                  res_name ] ):
            return False

        return True

    def _collect_data( self ):
        """Use the `scontrol show node` command to collect data on all
           available nodes.  A class-level dictionary is being populated."""
        sinfo = subprocess.check_output(
                               ['scontrol', 'show', 'node'] ).decode( 'UTF-8' )

        for node in sinfo.split( '\n\n' ):
            node_info = {}
            for line in node.split( '\n' ):
                if line.strip() != '' and item.strip()[:3] != 'OS=' and
                   item.strip()[:7] != 'Reason=':
                    for item in line.strip().split():
                        node_info[ item.split( '=' ).strip() ] =
                                                      item.split( '=' ).strip()
                elif item.strip()[:3] == 'OS=' or
                     item.strip()[:7] == 'Reason=':
                    node_info[ item.strip().split( '=' )[0] ] =
                                                   item.strip().split( '=' )[1]
            self.node_data[ node_info[ 'NodeName' ] ] = node_info


    def check_request( self, partition=None, state=None, min_nodes=None,
                       max_nodes=None, min_ppn=None, max_ppn=None,
                       req_type=None ):
        if self.node_data is None:
            self._collect_data()

        # Set defaults
        if partition is None:
            partition = 'standard'

        if state is None:
            state = 'IDLE'

        if min_nodes is None:
            min_nodes = 1

        if min_ppn is None:
            min_ppn = 1

        # Lists for internal uses
        comp_nodes = []
        partition_nodes = []
        state_nodes = []
        ppn_nodes = []
        max_procs = 0
        min_procs = None
        max_avail = False
        if max_nodes == 'all':
            max_avail = True

        # Collect the list of nodes that are compute nodes.  Determined by
        # whether or not they have the keys 'Partitions' and 'State'.
        for node in list(self.node_data.keys()):
            if 'Partitions' in list(self.node_data[ node ].keys()) and
               'State' in list(self.node_data[ node ].keys()):
                comp_nodes.append( node )
                max_procs = max( [ max_procs, self.node_data[ 'CPUTot' ] ] )

        if min_nodes > len( comp_nodes ):
            raise SchedulerPluginError( 'Insufficient compute nodes.' )

        # Set default maxes based on collected node lists.
        if max_nodes is None or max_avail:
            max_nodes = len( comp_nodes )

        if max_ppn is None:
            max_ppn = max_procs

        # Check for compute nodes that are part of the right partition.
        for node in list(self.node_data.keys()):
            if partition in self.node_data[ node ][ 'Partitions' ]:
                partition_nodes.append( node )

        if min_nodes > len( partition_nodes ):
            raise SchedulerPluginError( 'Insufficient nodes in partition ' + \
                                        '{}.'.format( partition ) )

        if req_type == 'immediate':
            # Check for compute nodes in this partition in the right state.
            for node in partition_nodes:
                if state in self.node_data[ node ]['State']
                    state_nodes.append( node )
    
            if min_nodes > len( state_nodes ):
                raise SchedulerPluginError( 'Insufficient nodes in partition'+\
                                            ' {} and state {}.'.format(
                                                            patition, state ) )

            # Check that compute nodes in the right partition and state have
            # enough processors to match the requirements.
            for node in state_nodes:
                if self.node_data[ node ][ 'CPUTot' ] >= min_ppn and
                   self.node_data[ node ][ 'CPUTot' ] <= max_ppn:
                    ppn_nodes.append( node )
        elif req_type == 'wait':
            for node in partition_nodes:
                if self.node_data[ node ][ 'CPUTot' ] >= min_ppn and
                   self.node_data[ node ][ 'CPUTot' ] <= max_ppn:
                    ppn_nodes.append( node )
        else:
            raise SchedulerPluginError( "Request type {} ".format( req_type )+\
                                        "not recognized." )
    
        if min_nodes > len( ppn_nodes ):
            raise SchedulerPluginError

        if len( ppn_nodes ) >= max_nodes:
            num_nodes = max_nodes
        else:
            num_nodes = ppn_nodes

        max_procs = 0
        for node in ppn_nodes:
            if min_procs is None:
                min_procs = self.node_data[ node ][ 'CPUTot' ]
            else:
                min_procs = min( min_procs, self.node_data[ node ][ 'CPUTot' ]
            max_procs = max( max_procs, self.node_data[ node ][ 'CPUTot' ] )

        if ppn_min > max_procs:
            raise SchedulerPluginError( 'Too many processors requested.' )
        elif ppn_max < min_procs:
            num_procs = ppn_max
        elif max_procs < ppn_max:
            num_procs = max_procs

        return ( num_nodes, num_procs )

    def get_script_headers( self, partition=None, reservation=None, qos=None,
                            account=None, num_nodes=None, ppn=None,
                            time_limit=None ):
        """Function to accept a series of job submission resource requests and
           return a list of lines to go in a submission script.
        """
        line_list = []
        if partition is None:
            partition = 'standard'

        if not subprocess.check_call( [ 'scontrol', 'show', 'partition',
                                                                 partition ] ):
            raise SchedulerPluginError( 'Partition {} not found.'.format(
                                                                  partition ) )

        line_list.append( '#SBATCH -p {}'.format( partition ) )

        if reservation is not None:
            if not check_reservation( reservation ):
                raise SchedulerPluginError( 'Reservation {} not found.'.format(
                                                                reservation ) )
            else:
                line_list.append( '#SBATCH --reservation={}'.format(
                                                                reservation ) )

        if qos is not None:
            line_list.append( '#SBATCH -q {}'.format( qos ) )

        if account is not None:
            line_list.append( '#SBATCH --account={}'.format( account ) )

        if num_nodes is None:
            raise SchedulerPluginError( 'A number of nodes must be provided.' )

        line_list.append( '#SBATCH -N {}'.format( num_nodes ) )

        if ppn is not None:
            line_list.append( '#SBATCH --ntasks-per-node={}'.format( ppn ) )

        if time_limit is not None:
            line_list.append( '#SBATCH -t {}'.format( time_limit ) )

        return line_list

    def get_submission_call( self ):
        """Return the submission invocation."""
        return 'sbatch'
