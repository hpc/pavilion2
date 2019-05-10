from pavilion.var_dict import VarDict, var_method
import time
import datetime
import tzlocal


class PavVars(VarDict):
    def __init__(self):
        super().__init__('pav')

        self._now = tzlocal.get_localzone().localize(
            datetime.datetime.now()
        )

    @var_method
    def ts(self):
        return time.time()

    @var_method
    def year(self):
        return self._now.year

    @var_method
    def month(self):
        return self._now.month

    @var_method
    def day(self):
        return self._now.day

    @var_method
    def weekday(self):
        return self._now.strftime('%A')

    @var_method
    def time(self):
        return self._now.strftime('%H:%M:%S.%f')
