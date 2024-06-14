from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union, List

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile

from .filter_functions import FILTER_FUNCS
from .aggregator import StateAggregate

from lark import Transformer, Discard, Token


MICROSECS_PER_SEC = 10**6


class FilterTransformer(Transformer):

    def __init__(self, agg: Union[StateAggregate, Dict]):
        super().__init__()
        self.aggregate = agg
    
    def partial_iso_date(self, iso: List[Token]) -> date:
        iso = tuple(map(int, iso))

        month = 1
        day = 1

        year = iso[0]
        
        if len(iso) > 1:
            month = iso[1]
        if len(iso) > 2:
            day = iso[2] 

        return date(year, month, day)

    def partial_iso_time(self, iso: List[Token]) -> time:
        if len(iso) == 3:
            hrs, mins, secs = tuple(iso)
            microsecs = (float(secs) - int(secs)) * MICROSECS_PER_SEC
            iso.append(microsecs)

        iso = tuple(map(int, iso))

        return time(*iso)

    def partial_iso(self, iso: List[Union[date, time]]) -> Union[date, time, datetime]:
        if len(iso) == 2:
            return datetime.combine(iso[0], iso[1])

        return iso[0]

    def INT(self, INT: Token) -> int:
        return int(INT)

    def WS(self, ws) -> Discard:
        return Discard

    def duration(self, duration: List[Token]) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        datetime.now() - timedelta(**{unit: num})

    def unary_expression(self, exp: List) -> bool:
        return not exp[1]

    def binary_expression(self, exp: List) -> bool:
        operand1, connective, operand2 = tuple(exp)

        if connective == f_and:
            return operand1 and operand2
        elif connective == f_or:
            return operand1 or operand2

    def comp_expression(self, exp: List) -> bool:
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

    def NUMBER(self, num: Token) -> float:
        return float(num)
