"""Tests for the various Pavilion parsers."""

import lark
import pavilion.test_config.parsers.expressions
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
            'floats': ['0.1', '2.3'],
            'more_ints': ['0', '1'],
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

    def test_visitors(self):
        """Test the visitors used to collect all of the used variables."""

        expr_parser = parsers.get_expr_parser()

        # These visitors walk the parse tree and return the used
        # variables as a list (with unique items).
        expr = 'int1.3.foo + var.int2.*.bleh * 11 * - sum([int1, int1])'
        tree = expr_parser.parse(expr)
        visitor = pavilion.test_config.parsers.expressions.VarRefVisitor()
        used_vars = visitor.visit(tree)

        self.assertEqual(sorted(used_vars),
                         sorted(['int1.3.foo', 'var.int2.*.bleh', 'int1']))

        # Pretty much the same as above, but for a whole string an not just
        # an expression (it uses the above visitor for the expressions).
        string_parser = parsers.get_string_parser()
        tree = string_parser.parse("hello {{var.foo.1.baz:1s}} world "
                                   "{{sys.bar}}")
        visitor = parsers.strings.StringVarRefVisitor()
        var_list = visitor.visit(tree)
        self.assertEqual(sorted(['var.foo.1.baz', 'sys.bar']),
                         sorted(var_list))

    GOOD_EXPRESSIONS = {
        '': '',
        ' int1 + int2 ': 3,
        '1234': 1234,
        '"1234"': "1234",
        '1234.4321': 1234.4321,
        'True': True,
        'False': False,
        # list formation.
        'len([int1, 1, "hello",])': 3,
        'len([])': 0,
        'sum([1,2,3,4000])': 4006,
        'int1 + var.int2 * 11 * - sum([int1, int2])': -65,
        'int1 + var.float1 * -2 * -len(ints.*)': 14.200000000000001,
        'str1': 'hello',
        'ints.3': 3,
        'ints': 0,
        'struct.cpus * 0': 0,
        'struct.cpus // 7': 28,
        'struct.cpus / 7': 28.571428571428573,
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
        '"foo" or "bar"': True,
        '"foo" and 7': True,
        # Check that multi-argument functions work.
        'int("0x44", 16)': 68,
        # And that no argument functions work.
        'random() < 1': True,
        # Deep nesting.
        '((((((((1))))))))': 1,
        '[1, 2, 3, 4] + 1':            [2, 3, 4, 5],
        '[1, 2, 3, 4] // 2':           [0, 1, 1, 2],
        '[1, 2, 3, 4] ^ 2':           [1, 4, 9, 16],
        '[1, 2, 3, 4] * [4, 4, 2, 1]': [4, 8, 6, 4],
        '[1, 2, 3, 4] < 3 < 10 < [10, 11, 12, 13]': [False, True, False, False],
        '[1, "foo", False, 0, ""] and 2': [True, True, False, False, False],
    }

    def test_good_expressions(self):
        """Make sure good expressions work as expected."""

        expr_parser = lark.Lark(
            grammar=parsers.expressions.EXPR_GRAMMAR,
            parser='lalr',
        )
        trans = parsers.expressions.ExprTransformer(self.var_man)

        for expr, expected_result in self.GOOD_EXPRESSIONS.items():
            tree = expr_parser.parse(expr)
            result = trans.transform(tree)
            self.assertEqual(result, expected_result,
                             msg="Expr: '{}' should be '{}', got '{}'\n{}"
                                 .format(expr, expected_result, result,
                                         tree.pretty()))

    BAD_EXPRESSIONS = {
        # Doubled operations. This should error before
        # the fact that 'a' and 'b' are undefined is resolved.
        # Note that 'a +- b' is valid
        'a */ b': 'Invalid Syntax',
        'a /// b': 'Invalid Syntax',
        'a ==> c': 'Invalid Syntax',
        'a or or b': 'Invalid Syntax',
        'a and or b': 'Invalid Syntax',
        'a + * b': 'Invalid Syntax',
        'f ==': 'Invalid Syntax',
        '1 / 0': 'Division by zero',
        '-5 ^ 0.5': 'Power expression has complex result',
        # Missing trailing operand
        'a +': 'Hanging Operation',
        'b *': 'Hanging Operation',
        'c ^': 'Hanging Operation',
        'd or': 'Hanging Operation',
        'e and': 'Hanging Operation',
        # Unmatched
        '(g': 'Unmatched "("',
        'func_(': 'Unmatched "("',
        '"hello': 'Unclosed String',
        '["goodbye",': 'Unclosed List',
        # Bad lists
        '[,foo,]': 'Misplaced Comma',
        '[foo,,]': 'Unclosed List',
        # Consecutive operands
        '1 2': 'Invalid Syntax',
        'a b': 'Invalid Syntax',
        'True False': 'Invalid Syntax',
        '"hello" + 1': "Non-numeric value 'hello' in math operation.",
        '"hello" * 1': "Non-numeric value 'hello' in math operation.",
        '"hello" ^ 1': "Non-numeric value 'hello' in math operation.",
        '-"hello"': "Non-numeric value 'hello' in math operation.",
        'var.1.2.3.4.5': "Invalid variable 'var.1.2.3.4.5': too many name "
                         "parts.",
        'var.structs.0.*': "Could not resolve reference 'var.structs.0.*': "
                           "Unknown sub_var: '*'",
        'funky_town()': "No such function 'funky_town'",
        'sum(3)': "Invalid argument '3'. Expected a list.",
        'floor(3.2, 5)': 'Invalid number of arguments defined for function '
                         'floor. Got 2, but expected 1',
        '[1, 2, 3] + [1, 2]': "List operations must be between two equal "
                              "length lists. Arg1 had 3 values, arg2 had 2.",
        '[1, "foo", 3] * 2': "Non-numeric value 'foo' in list in math "
                             "operation.",
        '3 + [1, "foo", 3]': "Non-numeric value 'foo' in list in math "
                             "operation.",

    }

    def test_bad_expressions(self):
        """Check all failure conditions. We validate messages in
        test_bad_strings."""

        expr_parser = lark.Lark(
            parsers.expressions.EXPR_GRAMMAR,
            parser='lalr',
        )
        trans = parsers.expressions.ExprTransformer(self.var_man)

        for expr in self.BAD_EXPRESSIONS:
            try:
                tree = expr_parser.parse(expr)
                result = trans.transform(tree)
            except (parsers.ParserValueError, lark.UnexpectedInput):
                pass
            else:
                self.fail("Failed to fail on {} (got {}):\n{}"
                          .format(expr, result, tree.pretty()))

        with self.assertRaises(variables.DeferredError):
            tree = expr_parser.parse("sys.host_name")
            trans.transform(tree)

    def test_good_strings(self):

        strings = {
            '': '',
            'hello world': 'hello world',
            'hello\nworld': 'hello\nworld',
            'trailing newlines\n': 'trailing newlines\n',
            'trailing newlines\n\n': 'trailing newlines\n\n',
            # The string parser should be able to handle any combination
            # of A and B, where A is a basic string and B is an escape,
            # expression, or iteration.
            r'a[~b~]': 'ab',
            r'a[~b~]a': 'aba',
            r'a[~b~]a[~b~]': 'abab',
            r'a[~b~][~b~]a': 'abba',
            r'[~b~]': 'b',
            r'[~b~]a': 'ba',
            r'[~b~][~b~]a': 'bba',
            r'[~b~]a[~b~]': 'bab',
            # Making sure we can deal with reserved characters and intermixed
            # strings in expressions.
            'hello {{len("ok:}") +  int1 + 1234.3 + len("}:"):3.2f}} world':
                'hello 1241.30 world',
            '{{len("ok:}") + 1234.3 + len("}:"):05.7f}} world':
                '1240.3000000 world',
            # Check iterations.
            '[~{{more_ints}}-{{floats}}~_]': '0-0.1_0-2.3_1-0.1_1-2.3',
            '[~{{more_ints}}~alonger sep]': '0alonger sep1',
            r'[~{{more_ints}}~ \]hi\] ]': '0 ]hi] 1',
            '[~no iteration {{ints.0}}~bleh]': 'no iteration 0',
            # Use of parts of special sequences, including at the end of
            # a string.
            '${hello}': '${hello}',
            'also{': 'also{',
            '[0-9]': '[0-9]',
        }

        for expr, result in self.GOOD_EXPRESSIONS.items():
            if isinstance(result, (str, int, float)):
                result = str(result)
                strings['({{' + expr + '}})'] = '(' + result + ')'

        string_parser = parsers.get_string_parser()
        transformer = parsers.StringTransformer(self.var_man)
        for string, expected in strings.items():
            try:
                tree = string_parser.parse(string)
                result = transformer.transform(tree)

            except Exception as err:
                self.fail('Good str: "{}"\n{}'.format(string, err))
            self.assertEqual(result, expected,
                             msg="For string {}, expected '{}' but got '{}'"
                                 .format(string, expected, result))

    def test_bad_strings(self):
        """Make sure we get errors for the things we expect."""

        # Matching the exact failure strings is fragile, and that's intentional.
        # The whole syntax is incredibly fragile, the tiniest change can have
        # unforeseen consequences, and this is one of the best places to
        # look for those.
        bad_syntax = {
            'hello {{ foo bar baz what 9 + 3': 'Unmatched "{{"',
            '{{': 'Unmatched "{{"',
            'hello [~ foo': 'Unmatched "[~"',
            '[~': 'Unmatched "[~"',
            '{{ expr {{ nope }} }}': 'Nested Expression',
            'foo}}': 'Unmatched "}}"',
            '}}': 'Unmatched "}}"',
            '[~ }} ~]': 'Unmatched "}}"',
            'foo\\': 'Trailing Backslash',
            '~foo': 'Unescaped tilde',
            '[~ foo [~bar~]~]': 'Nested Iteration',
            '~_]': 'Unmatched "~<sep>]"',
            '[~foo ~] ~]': 'Unmatched "~<sep>]"',
            # You can't both iterate over a variable and use an a specific
            # part of it.
            '[~ {{ints.1}} {{ints}} ~]': "Variable var.ints.1 was referenced, "
                                         "but is also being iterated over. You "
                                         "can't do both.",
            # Bad expression
            '{{ nope }}': "Could not find a variable named 'nope' in any "
                          "variable set.",
        }

        for expr, expected in self.BAD_EXPRESSIONS.items():
            bad_syntax['p{{{{{}}}}}t'.format(expr)] = expected

        for string, exp_error in bad_syntax.items():
            try:
                result = parsers.parse_text(string, self.var_man)
            except parsers.StringParserError as err:
                self.assertEqual(err.message, exp_error,
                                 msg="Bad example '{}' produced an error '{}' "
                                     "that did not match expected error '{}'"
                                     .format(string, err.message, exp_error))
            else:
                self.fail(
                    "Failed to fail on '{}', parsed to: '{}'"
                    .format(string, result))
