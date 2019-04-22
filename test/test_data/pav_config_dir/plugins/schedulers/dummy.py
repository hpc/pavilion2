from pavilion import schedulers
import yaml_config as yc

class DummyVars(schedulers.SchedulerVariables):
    pass


class Dummy(schedulers.SchedulerPlugin):

    VAR_CLASS = DummyVars

    def __init__(self):
        super().__init__('dummy')

    def get_conf(self):

        return yc.KeyedElem('dummy', elements=[])
