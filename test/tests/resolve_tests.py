from pavilion.unittest import PavTestCase
from pavilion import resolve
from pavilion import variables
from pavilion.errors import TestConfigError

class ResolveTests(PavTestCase):

    # For the most part, the config variable resolution code doesn't care about the 
    # format of the test. 
    GOOD_CONFIG = {
        'hello': 'there',
        'var1': '{{ var.single }}',
        'list': [
            'a', 
            '{{ var.single }}',
            '{{ var.list.* }}',]
        }

    def test_resolve(self):
        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', {'single': '1',
                                    'list': ['a', 'b', 'c']})

        resolved = resolve.test_config(self.GOOD_CONFIG, var_man)

        self.assertEqual(
            resolved, {'hello': 'there', 'list': ['a', '1', 'a', 'b', 'c'], 'var1': '1'})
    
    BAD_CONFIGS = [
        # List expressions can only extend lists.
        ({'hello': '{{ var.list.* }}'}, "Section 'hello' was set to"),
        ({'a': {'b': '{{ var.list.* }}'}}, "Key 'a.b' was set to"),
        ]

    def test_resolve_bad(self):
        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', {'single': '1',
                                    'list': ['a', 'b', 'c']})

        for bad_config, exp_error in self.BAD_CONFIGS:
            try:
                resolved = resolve.test_config(bad_config, var_man)
                self.fail("Config '{}' did not raise an error as expected.".format(bad_config))
            except TestConfigError as err:
                self.assertTrue(str(err).startswith(exp_error), msg="Did not get expected error.")
