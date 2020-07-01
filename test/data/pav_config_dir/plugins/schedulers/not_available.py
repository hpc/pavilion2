import yaml_config as yc
from pavilion import schedulers


class NotAvailable(schedulers.SchedulerPlugin):

    VAR_CLASS = schedulers.SchedulerVariables

    def __init__(self):
        super().__init__('not_available', description="Not Available")

    def get_conf(self):
        return yc.KeyedElem('not_available', elements=[])

    def _schedule(self, test_obj, kickoff_path):
        return ""

    def available(self):
        return False

    def _get_data(self):
        return {}
