"""Tests for the various Pavilion parsers."""

import lark
from pavilion import plugins
from pavilion import unittest
from pavilion.test_config import parsers
from pavilion.test_config import variables
from pavilion import system_variables


class ParserTests(unittest.PavTestCase):

    def setUp(self) -> None:
        plugins.initialize_plugins(self.pav_cfg)

        self.var_man = variables.VariableSetManager()
        self.var_man.add_var_set('var', {
            'int1': "1",
            'int2': "2",
            'float1': '1.1',
            'str1': 'hello',
            'ints': ['0', '1', '2', '3', '4', '5'],
            'struct': {
                'cpus': '200',
                'flops': '2.1',
                'name': 'earth_chicken',
            },
            'structs': [
                {'type': 'cat', 'bites': '3', 'evil_rating': '5.2'},
                {'type': 'dog', 'bites': '0', 'evil_rating': '0.2'},
                {'type': 'fish', 'bites': '1', 'evil_rating': '9.7'},
            ]
        })
        self.var_man.add_var_set('sys', system_variables.get_vars(defer=True))

    def tearDown(self) -> None:
        plugins._reset_plugins()

    def test_visit_expression(self):

        expr_parser = parsers.get_expr_parser()

        expr = 'int1 + var.int2 * 11 * - sum([int1, int2])'

        tree = expr_parser.parse(expr)

        visitor = parsers.expressions.VarRefVisitor()
        print(visitor.visit(tree))

    def test_good_expressions(self):
        """Make sure good expressions work as expected."""

        expr_parser = parsers.get_expr_parser(self.var_man,
                                              debug=parsers.DEBUG_BASIC)
        err_parser = parsers.get_expr_parser(self.var_man,
                                             debug=parsers.DEBUG_TREE)

        expressions = {
            '': '',
            '1234': 1234,
            '"1234"': "1234",
            '1234.4321': 1234.4321,
            'True': True,
            'False': False,
            # list formation.
            'list_len([int1, 1, "hello",])': 3,
            'list_len([])': 0,
            'sum([1,2,3,4000])': 4006,
            'int1 + var.int2 * 11 * - sum([int1, int2])': -65,
            'int1 + var.float1 * -2 * -list_len(ints.*)': 14.200000000000001,
            'str1': 'hello',
            'ints.3': 3,
            'ints': 0,
            'struct.cpus // 7': 28,
            'structs.1.type': 'dog',
            'sum(structs.*.bites)': 4,
            'avg(structs.*.evil_rating)': 5.033333333333333,
            'int2^2': 4,
            'int2^(int1 + 1)': 4,
            'int2 - 2': 0,
            'int2 + 2': 4,
            '2 * 3 - 3': 3,
            'int2^2 * ints.3 - 5': 7,
            'int1 == 1 < ints.2 <= ints.3 > ints.1 >= ints.1 != int2': True,
            # Check all cases for all logic operations.
            'int1 == 1': True,
            'int1 == 2': False,
            'int1 != 2': True,
            'int1 != 1': False,
            'int1 > 0': True,
            'int1 > 1': False,
            'int1 < 2': True,
            'int1 < 1': False,
            'int1 >= 1': True,
            'int1 >= 1.1': False,
            'int1 <= 1': True,
            'int1 <= 0': False,
            'True or True': True,
            'False or True': True,
            'True or False': True,
            'False or False': False,
            'True and True': True,
            'False and True': False,
            'True and False': False,
            'False and False': False,
            'not True': False,
            'not False': True,
            'not True and False or not True and True': False,
            'not True or not False': True,
            '"foo" or "bar"': 'foo',
            '"foo" and 7': 7,
            # Check that multi-argument functions work.
            'int("0x44", 16)': 68,
            # And that no argument functions work.
            'random() < 1': True,
            # Deep nesting.
            '((((((((1))))))))': 1,
        }

        for expr, expected_result in expressions.items():
            result = expr_parser.parse(expr)
            ptree = err_parser.parse(expr).pretty()
            self.assertEqual(result, expected_result,
                             msg="Expr: '{}' should be '{}', got '{}'\n{}"
                                 .format(expr, expected_result, result, ptree))

    def test_bad_expressions(self):
        """Check all failure conditions."""

        unexpected_input = [
            # Bad format specs
            '1:abcd',
            # You can't format nothing.
            ':3s',
            # Doubled operations. This should error before
            # the fact that 'a' and 'b' are undefined is resolved.
            'a ++ b',
            # Note that 'a +- b' is valid
            'a -+ b',
            'a ** b',
            'a */ b',
            'a /// b',
            'a ==> c',
            'a or or b',
            'a and or b',
            'a + * b',
            # Missing trailing operand
            'a +',
            'b *',
            'c ^',
            'd or',
            'e and',
            'f ==',
            # Unmatched
            '(g',
            'func_(',
            '"hello',
            '["goodbye",',
            # Bad lists
            '[,foo,]',
            '[foo,,]',
            # Consecutive operands
            '1 2',
            'a b',
            'True False',
        ]

        expr_parser = parsers.get_expr_parser(self.var_man)
        err_parser = parsers.get_expr_parser(self.var_man,
                                             debug=parsers.DEBUG_TREE)

        for expr in unexpected_input:
            with self.assertRaises(lark.exceptions.UnexpectedInput):
                try:
                    expr_parser.parse(expr)
                except parsers.ParseError:
                    # Just in case it doesn't fail, we catch and pass
                    pass
                self.fail("Failed to fail on {}:\n{}"
                          .format(expr, err_parser.parse(expr).pretty()))

        bad_expressions = [
            '"hello" + 1',      # All arguments must be numbers
            '"hello" * 1',      # All arguments must be numbers
            '"hello" ^ 1',      # All arguments must be numbers
            '-"hello"',         # You can't negate a string.
            'var.1.2.3.4.5',    # To many var name parts (max 4)
            'nope.var',         # No such variable.
            'var.structs.0.*',  # '*' can't be used on struct values (yet)
            'funky_town()',     # No such function (but there should be)
            'sum(3)',           # Bad argument
            'floor(3.2, 5)',    # Wrong number of arguments
        ]

        for expr in bad_expressions:
            with self.assertRaises(parsers.ParseError):
                result = expr_parser.parse(expr)

                self.fail("Failed to fail on {} (got {}):\n{}"
                          .format(expr, result,
                                  err_parser.parse(expr).pretty()))

        with self.assertRaises(variables.DeferredError):
            expr_parser.parse("sys.host_name")

    def test_good_strings(self):

        strings = [
            '',
            'hello world',
            'hello\nworld',
            'hello \\{ world',
            'hello {{this is "ok:}"an expr 1234.3"}:":3d}} world',
            '{{this is "ok:}"an expr 1234.3"}:":3d}} world',
        ]

        string_parser = parsers.get_string_parser(self.var_man)
        for string in strings:
            print(string_parser.parse(string))

        # It's also important to come up with strings that should fail.
        # Strings that should fail.
        bad_strings = [
            'hello {{ foo',    # hanging expression
            'hello [~ foo',    # hanging sub-string
            '{{ expr {{ nope }} }}', # Expressions can't contain expressions.
        ]

