from pavilion.test_config import variables
from pavilion.test_config.variables import VariableError
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
            'var1': variables.DeferredVariable(),
        }

        slurm_data = {
            'num_nodes': '45'
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', data)
        var_man.add_var_set('sys', sys_data)
        var_man.add_var_set('sched', slurm_data)

        with self.assertRaises(ValueError):
            var_man.len('sys', 'var1')

        for key in (
                'sys.var1',
                'sys.var1.3',
                'sys.var1.1.subvar1',
                'sys.var1.noexist'):
            try:
                _ = var_man[key]
            except (KeyError, variables.DeferredError):
                pass
            else:
                self.fail("Did not raise the appropriate error.")
