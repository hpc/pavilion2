import yaml_config as yc
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_var_method
import pavilion.plugins.sched.slurm as slurm


class SlurmMPIVars(slurm.SlurmVars):
    """Variables for SlurmMPI scheduler."""

    def procs_per_node(self):
        """Returns tasks per node"""
        return self.sched_config.get('tasks_per_node')

    def mca_translation(self):
        """Formats --mca argument(s)."""
        return ['--mca ' + kv_pair for kv_pair in self.sched_config.get('mca')]

    @dfr_var_method
    def test_cmd(self):
        """Overrides test_cmd in SlurmVars to use mpirun instead of srun."""
        cmd = ['mpirun', '--map-by ppr:{}:node'.format(self.procs_per_node())]

        if self.sched_config.get('rank_by'):
            cmd.extend(['--rank-by', self.sched_config.get('rank_by')])
        if self.sched_config.get('bind_to'):
            cmd.extend(['--bind-to', self.sched_config.get('bind_to')])
        if self.sched_config.get('mca'):
            cmd.extend(self.mca_translation())

        # create list of hosts if need be
        if int(self.sched_config.get('num_nodes')) < int(self.alloc_nodes()):
            hostlist = self.alloc_node_list().split()
            hostlist = hostlist[:int(self.sched_config.get('num_nodes'))]
            hostlist = ','.join(hostlist)
            cmd.extend(['--host', hostlist])

        return ' '.join(cmd)


class SlurmMPI(slurm.Slurm):
    """Schedules tests using Slurm, but uses mpirun instead of srun."""

    VAR_CLASS = SlurmMPIVars

    def __init__(self): # pylint: disable=W0231
        SchedulerPlugin.__init__( # pylint: disable=W0233
            self,
            'slurm_mpi',
            'Schedules tests via Slurm but runs them using mpirun',
            priority=10
        )

    def get_conf(self):
        """Add necessary MPI attributes to those of Slurm."""
        elems = slurm.get_slurm_elems()
        elems.extend([
            yc.StrElem(
                'rank_by',
                help_text="Value for `--rank-by`. Default is slot."
            ),
            yc.StrElem(
                'bind_to',
                help_text="Value for `--bind-to`. Default is core."
            ),
            yc.ListElem(
                'mca',
                help_text="Key-Value for pair(s) for --mca.",
                sub_elem=yc.RegexElem(
                    'kv_pair',
                    regex=r'^[a-z1-9]+\s[a-z1-9,]+$'
                )
            )
        ])

        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the Slurm scheduler using mpirun.",
            elements=elems
        )
