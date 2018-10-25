from __future__ import print_function, unicode_literals, division

import unittest
import traceback

from pavilion import variables
from pavilion import string_parser

class TestStringParser(unittest.TestCase):

    var_data = {
        'var1': 'val1',
        'sep' : '-',
        'var2': ['0', '1', '2'],
        'var3': {'subvar1': 'subval1',
                 'subvar2': 'subval2'},
        'var4': [{'subvar1': 'subval0_1',
                  'subvar2': 'subval0_2'},
                 {'subvar1': 'subval1_1',
                  'subvar2': 'subval1_2'}]
    }

    pav_data = {
        'var1': 'pval1',
        'var2': ['p0', 'p1'],
        'var3': {'psubvar1': 'psubval1',
                 'psubvar2': 'psubval2'},
        'var4': [{'psubvar1': 'psubval0_1',
                  'psubvar2': 'psubval0_2'},
                 {'psubvar1': 'psubval1_1',
                  'psubvar2': 'psubval1_2'}]
    }

    var_set_manager = variables.VariableSetManager()
    var_set_manager.add_var_set('var', var_data)
    var_set_manager.add_var_set('pav', pav_data)

    def test_parser(self):
        """Check string parsing and variable substitution."""

        # Strings to test (unparsed string, expected result)
        test_strings = [
            # The empty string is valid.
            ('', ''),
            # So are randomly generic strings.
            ('Hello you punks.', 'Hello you punks.'),
            # Checking that escapes are escaped.
            (r'\\\{\}\[\]\ \a', r'\{}[] a'),
            # Basic variable substitution
            ('Hello {var1} World', 'Hello val1 World'),
            # Variable with var_set. We'll rely on the variable tests for the full combinations,
            # as they use the same functions under the hood.
            ('Hello {pav.var1} World', 'Hello pval1 World'),
            # Substring substitution with spaces.
            ('Hello [{var2}: ] World.', 'Hello 0 1 2 World.'),
            # Substring substitution as last item.
            ('Hello [{var2}]', 'Hello 012'),
            # Substring substitution with multiple loop vars and a non-loop var.
            ('Hello [{var2}{sep}{pav.var2}: ] World.',
             'Hello 0-p0 0-p1 1-p0 1-p1 2-p0 2-p1 World.'),
            # Substring substitution without spaces.
            ('Hello [{var2}]World.', 'Hello 012World.'),
            # Substring substitution with an escaped space.
            ('Hello [{var2}:\ ] World.', 'Hello 0: 1: 2:  World.'),
            # Sub-strings with repeated usage
            ('Hello [{var4.subvar1}-{var4.subvar2}: ] World.',
             'Hello subval0_1-subval0_2 subval1_1-subval1_2 World.'),
            # sub-sub strings
            ('Hello [{var2}-[{var4.subvar1}:-]: ] World.',
             'Hello 0-subval0_1-subval1_1 1-subval0_1-subval1_1 2-subval0_1-subval1_1 World.'),

        ]

        for test_str, answer_str in test_strings:
            self.assertEqual(string_parser.parse(test_str).resolve(self.var_set_manager),
                             answer_str)

    def test_parser_errors(self):
        test_strings = [
            # Missing close bracket on variable reference.
            ('Hello {bleh World.', string_parser.ScanError),
            # Bad variable name
            ('Hello {;;dasd} World.', string_parser.ScanError),
            # Bad var_set name (raised by VariableSetManager, re-caught in the tokenizer)
            ('Hello {;.foo.bar} World.', string_parser.ScanError),
            # Bad sub_var name
            ('Hello {pav.bar.;-} World.', string_parser.ScanError),
            # Extra close bracket
            ('Hello {hello}} World.', string_parser.ScanError),
            # Strings cannot end with the escape character.for
            ('Hello \\', string_parser.ScanError),
            # The 'Unknown scanning error' exception shouldn't be reachable.
            # Missing close square bracket.
            ('Hello [foo World', string_parser.ParseError),
            # The 'Unknown token of type' exception shouldn't be reachable.
            # Neither should the two RuntimeError's in Substring start and end.
        ]

        show_errors = False

        for test_str, error in test_strings:
            self.assertRaises(error,
                              lambda: string_parser.parse(test_str).resolve(self.var_set_manager))

            if show_errors:
                try:
                    string_parser.parse(test_str).resolve(self.var_set_manager)
                except error:
                    traceback.print_exc()


