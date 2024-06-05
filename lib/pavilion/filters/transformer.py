from datetime import date, time, datetime, timedelta
from typing import Any

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile
from filters import FILTER_FUNCS

from lark import Transformer, Discard


class FilterTransformer(Transformer):
    
    def partial_iso_date(self, iso) -> date:
        iso = tuple(map(int, iso))

        month = 1
        day = 1

        year = iso[0]
        
        if len(iso) > 1:
            month = iso[1]
        if len(iso) > 2:
            day = iso[2] 

        return date(year, month, day)

    def partial_iso_time(self, iso) -> time:
        iso = tuple(map(int, iso))

        return time(*iso)

    def INT(self, INT) -> int:
        return int(INT)

    def WS(self, ws):
        return Discard

    def duration(self, duration) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        return datetime.now() - timedelta(**{unit: num})

    def eq(self, eq) -> Callable[[Any], bool]:
        f = eq.children[0]
        g = eq.children[1]

        return lambda x: f(x) == g(x)

    def lt(self, lt) -> Callable[[Any], bool]:
        f = eq.children[0]
        g = eq.children[1]

        return lambda x: f(x) < g(x)

    def gt(self, gt) -> Callable[[Any], bool]:
        f = eq.children[0]
        g = eq.children[1]

        return lambda x: f(x) > g(x)

    def lteq(self, lteq) -> Callable[[Any], bool]:
        f = eq.children[0]
        g = eq.children[1]

        return lambda x: f(x) <= g(x)

    def gteq(self, lteq) -> Callable[[Any], bool]:
        f = eq.children[0]
        g = eq.children[1]

        return lambda x: f(x) >= g(x)

    def WORD(self, word) -> Callable[[str], Any]:
        if word in FILTER_FUNCS:
            return FILTER_FUNCS[word]

        return lambda x: x.get(word)
