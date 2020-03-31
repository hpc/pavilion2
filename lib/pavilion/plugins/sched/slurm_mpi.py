import yaml_config as yc
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_var_method
import pavilion.plugins.sched.slurm as slurm


class SlurmMPIVars(slurm.SlurmVars):

    @dfr_var_method
    def procs_per_node(self):
        return self.sched_config.get('tasks_per_node')

    @dfr_var_method
    def test_cmd(self):
        """Overrides test_cmd in SlurmVars to use mpirun instead of srun."""
        cmd = ['mpirun', '--map-by ppr:{}:node'.format(self.procs_per_node())]

        if self.sched_config.get('rank_by'):
            cmd.extend(['--rank-by', self.sched_config.get('rank_by')])
        if self.sched_config.get('bind_to'):
            cmd.extend(['--bind-to', self.sched_config.get('bind_to')])

        return ' '.join(cmd)


class SlurmMPI(slurm.Slurm):

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
        elems = slurm.Slurm.get_slurm_elems(self)
        elems.extend([
            yc.StrElem(
                'rank_by',
                help_text="Value for `--rank-by`. Default is slot."
            ),
            yc.StrElem(
                'bind_to',
                help_text="Value for `--bind-to`. Default is core."
            )
        ])

        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the Slurm scheduler using mpirun.",
            elements=elems
        )
