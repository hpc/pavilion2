from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile

from .filter_functions import FILTER_FUNCS
from .aggregator import StateAggregate

from lark import Transformer, Discard


class FilterTransformer(Transformer):

    def __init__(self, agg: Union[StateAggregate, Dict]):
        super().__init__()
        self.aggregate = agg
    
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

    def WS(self, ws) -> Discard:
        return Discard

    def duration(self, duration) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        datetime.now() - timedelta(**{unit: num})

    def expression(self, exp) -> bool:
        operand1, operation, operand2 = tuple(exp)

        operation = operation.data

        if operation == 'eq':
            return operand1 == operand2
        elif operation == 'lt':
            return operand1 < operand2
        elif operation == 'gt':
            return operand1 > operand2
        elif operation == 'lteq':
            return operand1 <= operand2
        elif operation == 'gteq':
            return operand >= operand2

    def argument_binding(self, arg_bind) -> bool:
        ffunc, val = arg_bind

        FILTER_FUNCS[ffunc.data](self.aggregate, val)

    def all_started(self, _) -> bool:
        return self.aggregate.get('all_started')

    def complete(self, _) -> bool:
        return self.aggregate.get('complete')

    def CNAME(self, word) -> Union[Callable[[Any], Any]]:
        word = str(word)

        if word in FILTER_FUNCS:
            return FILTER_FUNCS[word.lower()](self.aggregate)

        # if not a recognized property, treat it as a literal string
        return self.aggregate.get(word, word)
