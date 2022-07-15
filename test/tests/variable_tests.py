import sys

import pavilion.deferred
from pavilion.resolver import variables
from pavilion.errors import VariableError, DeferredError
from pavilion.unittest import PavTestCase


class TestVariables(PavTestCase):

    def test_good_queries(self):
        """Make sure all valid ways to lookup variables work."""

        data = {
            'var1': 'val1',
            'var2': ['0', '1', '2'],
            'var3': {'subvar1': 'subval1',
                     'subvar2': 'subval2'},
            'var4': [{'subvar1': 'subval0_1',
                      'subvar2': 'subval0_2'},
                     {'subvar1': 'subval1_1',
                      'subvar2': 'subval1_2'}]
        }

        sys_data = {
            'var1': 'sys.val1'
        }

        slurm_data = {
            'num_nodes': '45'
        }

        vsetm = variables.VariableSetManager()
        vsetm.add_var_set('var', data)
        vsetm.add_var_set('sys', sys_data)
        vsetm.add_var_set('sched', slurm_data)

        # Lookup without set name, this also conflicts across vsets and should
        # resolve correctly.
        self.assertEqual(vsetm['var1'], 'val1')
        # Lookup with set name
        self.assertEqual(vsetm['var.var1'], 'val1')
        # Explicit Index
        self.assertEqual(vsetm['var.var1.0'], 'val1')

        # Implicit Index
        self.assertEqual(vsetm['var2'], '0')
        # Explicit Index, set name
        self.assertEqual(vsetm['var.var2.2'], '2')
        # Negative Indexes are allowed (this one is at the edge of the range).
        self.assertEqual(vsetm['var.var2.-3'], '0')
        # Check the length of a variable list
        self.assertEqual(vsetm.len('var', 'var2'), 3)

        # Subkeys, when there's just one.
        self.assertEqual(vsetm['var3.subvar1'], 'subval1')
        self.assertEqual(vsetm['var3.subvar2'], 'subval2')
        # Subkey with explicit index
        self.assertEqual(vsetm['var3.0.subvar2'], 'subval2')

        # Multiple subkeys
        self.assertEqual(vsetm['var4.0.subvar1'], 'subval0_1')
        # Implicit index
        self.assertEqual(vsetm['var4.subvar1'], 'subval0_1')
        self.assertEqual(vsetm['var4.1.subvar1'], 'subval1_1')
        self.assertEqual(vsetm['var4.0.subvar2'], 'subval0_2')
        self.assertEqual(vsetm['var4.1.subvar2'], 'subval1_2')

        # Explicit access to conflicting variable
        self.assertEqual(vsetm['sys.var1'], 'sys.val1')

    def test_unacceptable_queries(self):
        """Make sure all invalid variable lookups break."""

        data = {
            'var1': 'val1',
            'var2': ['0', '1', '2'],
            'var3': {'subvar1': 'subval1',
                     'subvar2': 'subval2'},
            'var4': [{'subvar1': 'subval0_1',
                      'subvar2': 'subval0_2'},
                     {'subvar1': 'subval1_1',
                      'subvar2': 'subval1_2'}]
        }

        vsetm = variables.VariableSetManager()
        vsetm.add_var_set('var', data)

        # Missing var
        self.assertRaises(KeyError, lambda: vsetm['var99'])
        # Too many parts (no vset)
        self.assertRaises(KeyError, lambda: vsetm['var1.0.a.b'])
        # Too many parts (w/ vset)
        self.assertRaises(KeyError, lambda: vsetm['var.var1.0.a.b'])
        # Empty key
        self.assertRaises(KeyError, lambda: vsetm[''])
        # vset only
        self.assertRaises(KeyError, lambda: vsetm['var'])
        # empty vset
        self.assertRaises(KeyError, lambda: vsetm['.var1'])
        # empty index/subvar
        self.assertRaises(KeyError, lambda: vsetm['var1.'])
        # empty index
        self.assertRaises(KeyError, lambda: vsetm['var3..subvar1'])
        # Out of range index
        self.assertRaises(KeyError, lambda: vsetm['var2.1000'])
        # Out of range negative index
        self.assertRaises(KeyError, lambda: vsetm['var2.-4'])
        # Empty subvar
        self.assertRaises(KeyError, lambda: vsetm['var1.0.'])
        # Unknown subvar
        self.assertRaises(KeyError, lambda: vsetm['var1.0.bleh'])
        # Out of range
        self.assertRaises(KeyError, lambda: vsetm['var1.1'])
        # Missing subvar
        self.assertRaises(KeyError, lambda: vsetm['var3.0.nope'])
        # Has subvar but none referenced
        self.assertRaises(KeyError, lambda: vsetm['var3.0'])

        # Len of invalid key
        self.assertRaises(KeyError, lambda: vsetm.len('var', 'var99'))

        # Keys must be unicode or a list/tuple
        self.assertRaises(TypeError, lambda: vsetm[1])

    def test_bad_data(self):
        """Make sure bad data causes issues on ingest."""

        # Unknown vset name
        vsetm = variables.VariableSetManager()
        with self.assertRaises(ValueError):
            vsetm.add_var_set('blah', {})

        # Duplicate vset name
        vsetm.add_var_set('var', {})
        with self.assertRaises(ValueError):
            vsetm.add_var_set('var', {})

        # Mismatched subvars
        data = {
            'var4': [{'subvar1': 'subval0_1',
                      'subvar2': 'subval0_2'},
                     {'subvar1': 'subval1_1',
                      'subvar3': 'subval1_2'}]
        }
        with self.assertRaises(VariableError):
            vsetm.add_var_set('sys', data)

        slurm_data = {
            'num_nodes': 45
        }
        # Adding non-string data
        with self.assertRaises(VariableError):
            vsetm.add_var_set('sched', slurm_data)

    def test_deferred(self):
        """Test deferred variables."""

        data = {
            'var1': 'val1',
            'var3': {'subvar1': 'subval1',
                     'subvar2': 'subval2'},
        }

        sys_data = {
            'var1': pavilion.deferred.DeferredVariable(),
        }

        slurm_data = {
            'num_nodes': '45'
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', data)
        var_man.add_var_set('sys', sys_data)
        var_man.add_var_set('sched', slurm_data)

        with self.assertRaises(DeferredError):
            var_man.len('sys', 'var1')

        for key in (
                'sys.var1',
                'sys.var1.3',
                'sys.var1.1.subvar1',
                'sys.var1.noexist'):
            try:
                _ = var_man[key]
            except (KeyError, DeferredError):
                pass
            else:
                self.fail("Did not raise the appropriate error.")

    def test_resolve_references(self):
        """Check that references are resolved properly for variables."""

        user_vars = {
            'a': ['{{b}}1', '{{b}}2'],
            'b': ['3', '{{d}}'],
            'c': ['7', '8', '{{sched.nodes}}'],
            'd': ['1', '2', '10'],
            'e': ['{{sched.nodes}}'],
            'f': ['{{c}}']
        }
        answer = {
            'a': ['31', '32'],
            'b': ['3', '1'],
            'c': ['7', '8', '{{sched.nodes}}'],
            'd': ['1', '2', '10'],
            'e': ['{{sched.nodes}}'],
            'f': ['{{c}}']
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', user_vars)

        resolved = var_man.resolve_references(partial=True, skip_deps=['a', 'b', 'c'])
        self.assertEqual(sorted(resolved), ['b', 'd'])

        resolved = var_man.resolve_references(partial=True, skip_deps=['a', 'c'])
        self.assertEqual(sorted(resolved), ['a', 'b', 'd'])

        self.assertEqual(var_man.as_dict(), {'var': answer})

    def test_get_permutations(self):
        """Check that permutation creation works."""
        user_vars = {
            'a': ['{{b}}1', '{{b}}2'],
            'b': ['3', '{{d}}'],
            'c': ['7', '8', '{{sched.nodes}}'],
            'd': ['1', '2', '10'],
            'e': ['{{sched.nodes}}'],
            'f': ['{{c}}']
        }

        answers = [
            ('31', '3', '7'),
            ('31', '3', '8'),
            ('31', '3', '37'),
            ('32', '3', '7'),
            ('32', '3', '8'),
            ('32', '3', '37'),
            ('11', '1', '7'),
            ('11', '1', '8'),
            ('11', '1', '37'),
            ('12', '1', '7'),
            ('12', '1', '8'),
            ('12', '1', '37'),
        ]

        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', user_vars)
        var_man.resolve_references(partial=True, skip_deps=['a', 'b', 'c'])
        var_men = var_man.get_permutations([('var', 'b')])

        self.assertEqual(len(var_men), 2)
        all_var_men = []
        for var_man in var_men:
            var_man.resolve_references(partial=True, skip_deps=['a', 'c'])
            all_var_men.extend(var_man.get_permutations([('var', 'a')]))
        var_men = all_var_men
        self.assertEqual(len(var_men), 4)

        all_var_men = []
        for var_man in var_men:
            var_man.add_var_set('sched', {'nodes': '37'})
            var_man.resolve_references()
            all_var_men.extend(var_man.get_permutations([('var', 'c')]))
        var_men = all_var_men
        self.assertEqual(len(var_men), 12)

        # There are 12 answers and we assert that all permuted sets are unique,
        # therefore if ever permuted variable set is in answers all answers also exist.
        simplified = [(v['a'], v['b'], v['c']) for v in var_men]
        self.assertEqual(len(simplified), len(set(simplified)))
        for values in simplified:
            self.assertIn(values, answers)


