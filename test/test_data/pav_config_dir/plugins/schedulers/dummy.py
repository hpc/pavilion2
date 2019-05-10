from pavilion import schedulers
from pavilion.status_file import STATES
import yaml_config as yc


class DummyVars(schedulers.SchedulerVariables):
    pass


class Dummy(schedulers.SchedulerPlugin):

    VAR_CLASS = DummyVars

    def __init__(self):
        super().__init__('dummy')

    def _get_conf(self):

        return yc.KeyedElem('dummy', elements=[])

    def _schedule(self, test_obj, kickoff_path):
        """The dummy scheduler does nothing, because it's dumb."""

        return ""

    def check_job(self, pav_cfg, test):
        """Dummy jobs are always ok, because they're dumb."""
        if test.status.current().state == STATES.SCHEDULED:
            test.status.set(STATES.COMPLETE, "I'm done, dummy.")

        return test.status.current()


