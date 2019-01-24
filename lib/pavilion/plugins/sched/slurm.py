import pavilion.scheduler_plugins as scheduler_plugins

class Slurm( scheduler_plugins.SchedulerPlugin ):

    def __init__( self ):
        super().__init__( name='slurm', priority=10 )

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
