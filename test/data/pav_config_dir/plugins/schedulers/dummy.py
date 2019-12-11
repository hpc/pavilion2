from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion.test_config import VariableSetManager
from pavilion.system_variables import SysVarDict
import yaml_config as yc


class DummyVars(schedulers.SchedulerVariables):

    @schedulers.var_method
    def am_i_dumb(self):
        return True


class Dummy(schedulers.SchedulerPlugin):

    VAR_CLASS = DummyVars

    def __init__(self):
        super().__init__('dummy', 'I am dumb')

    def get_conf(self):
        return yc.KeyedElem('dummy', elements=[])

    def _schedule(self, test_obj, kickoff_path):
        """The dummy scheduler does nothing, because it's dumb."""

        return ""

    def job_status(self, pav_cfg, test):
        """Dummy jobs are always ok, because they're dumb."""
        if test.status.current().state == STATES.SCHEDULED:
            test.status.set(STATES.COMPLETE, "I'm done, dummy.")

        return test.status.current()

    def cancel_job(self, test):
        """Do nothing, like a lazy jerk Class."""

        return True, "There was nothing to cancel, dummy."
