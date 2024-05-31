from datetime import date, time, datetime, timedelta

# from pavilion.status_file import SERIES_STATES
# from filters import FILTER_FUNCS

from lark import Transformer, Discard

class FilterTransformer(Transformer):

    def __init__(self, ):
        ...

    def partial_iso_date(self, iso):
        iso = tuple(map(int, iso))

        month = 1
        day = 1

        year = iso[0]
        
        if len(iso) > 1:
            month = iso[1]
        if len(iso) > 2:
            day = iso[2] 

        return date(year, month, day)

    def partial_iso_time(self, iso):
        iso = tuple(map(int, iso))

        return time(*iso)

    def INT(self, INT):
        return int(INT)

    def WS(self, ws):
        return Discard

    def duration(self, duration):
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        print((num, unit))

        return datetime.now() - timedelta(**{unit: num})

    def eq(self, eq):
        return lambda x, y: x == y

    def lt(self, lt):
        return lambda x, y: x < y

    def gt(self, gt):
        return lambda x, y: x > y

    def lteq(self, lteq):
        return lambda x, y: x <= y

    def gteq(self, lteq):
        return lambda x, y: x >= y

    def WORD(self, word):
        return str(word)
