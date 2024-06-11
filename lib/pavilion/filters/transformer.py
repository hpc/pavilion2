from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile

from .filter_functions import FILTER_FUNCS

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

        return lambda _: date(year, month, day)

    def partial_iso_time(self, iso) -> time:
        iso = tuple(map(int, iso))

        return lambda _: time(*iso)

    def INT(self, INT) -> int:
        return lambda _: int(INT)

    def WS(self, ws):
        return Discard

    def duration(self, duration) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        return lambda _: datetime.now() - timedelta(**{unit: num})

    def expression(self, exp) -> Callable[[Dict], bool]:
        operand1, operation, operand2 = tuple(exp)

        operation = operation.data

        if operation == 'eq':
            return lambda x: operand1(x) == operand2(x)
        elif operation == 'lt':
            return lambda x: operand1(x) < operand2(x)
        elif operation == 'gt':
            return lambda x: operand1(x) > operand2(x)
        elif operation == 'lteq':
            return lambda x: operand1(x) <= operand2(x)
        elif operation == 'gteq':
            return lambda x: operand(x) >= operand2(x)

    def argument_binding(self, arg_bind) -> Callable[[Dict], bool]:
        ffunc, val = arg_bind

        return lambda x: FILTER_FUNCS[ffunc.data](x, val(x))

    def all_started(self, special):
        return FILTER_FUNCS['all_started']

    def complete(self, completed):
        return FILTER_FUNCS['complete']

    def CNAME(self, word) -> Union[Callable[[Any], Any]]:
        word = str(word)

        if word in FILTER_FUNCS:
            return FILTER_FUNCS[word.lower()]

        return lambda _: word
