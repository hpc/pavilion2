import pavilion.schedulers.vars
from pavilion import schedulers


class NotAvailable(schedulers.SchedulerPlugin):

    VAR_CLASS = pavilion.schedulers.vars.SchedulerVariables

    def __init__(self):
        super().__init__('not_available', description="Not Available")

    def available(self):
        return False

    def _get_data(self):
        return {}
