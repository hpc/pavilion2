
from pavilion.unittest import PavTestCase
from pavilion.test_config import (load_test_configs, TestConfigError, apply_overrides,
                                  resolve_permutations, resolve_all_vars)
from pavilion.test_config import variables, string_parser


class TestSetupTests(PavTestCase):

    def test_loading_tests(self):
        """Make sure get_tests can find tests and resolve inheritance."""

        with self.assertRaises(TestConfigError):
            # Non-existent host config
            load_test_configs(self.pav_cfg, 'nope', [], ['hello_world'])

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world'])
        self.assertEqual(sorted(['narf', 'hello', 'world']),
                         sorted([test['name'] for test in tests]))

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world.hello'])
        hello = tests.pop()

        # There should have only been 1
        self.assertFalse(tests)
        # Check some basic test attributes.
        self.assertEqual(hello['scheduler'], 'slurm')
        self.assertEqual(hello['suite'], 'hello_world')
        # Make sure the variable from the host config got propagated.
        self.assertIn('hosty', hello['variables'])

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world.narf'])
        narf = tests.pop()
        # Make sure this got overridden from 'world'
        self.assertEqual(narf['scheduler'], 'dummy')
        # Make sure this didn't get lost.
        self.assertEqual(narf['run']['cmds'], ['echo "Running World"'])

    def test_apply_overrides(self):
        """Make sure overrides get applied to test configs correctly."""

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world'])

        overrides = {
            'run': {
                'env': {
                    'foo': 'bar'
                }
            },
            'scheduler': 'fuzzy'
        }

        for test in tests:
            otest = test.copy()
            apply_overrides(test, overrides)

            # Make sure the overrides were applied
            self.assertEqual(test['scheduler'], 'fuzzy')
            self.assertEqual(test['run']['env']['foo'], 'bar')
            # Make sure other stuff wasn't changed.
            self.assertEqual(test['build'], otest['build'])
            self.assertEqual(test['run']['cmds'], otest['run']['cmds'])

    def test_resolve_permutations(self):
        """Make sure permutations are applied correctly."""

        raw_test = {
            'build': {
                'cmds':
                    ["echo {foo} {bar.p}", "echo {foo}", "echo {bar.q}"],
                'env':
                    {'baz': '{baz}'}
            },
            'permutations': {
                'foo': ['1', '2', '3'],
                'bar': [
                    {'p': '4', 'q': '4a'},
                    {'p': '5', 'q': '5a'},
                ],
                'baz': ['6'],
                'blarg': ['7', '8']
            }
        }

        orig_permutations = raw_test['permutations']

        test, permuted = resolve_permutations(raw_test, {}, {})

        # This should have been deleted
        self.assertNotIn('permutations', test)
        self.assertNotIn('variables', test)

        # Foo should triple the permutations, bar should double them -> 6
        # baz shouldn't have an effect (on the permutation count).
        # blarg shouldn't either, because it's never used.
        self.assertEqual(len(permuted), 6)

        # Make sure each possible 'combination' of variables is
        # present in the permuted var manager.
        combinations = []
        for foo in orig_permutations['foo']:
            for bar in orig_permutations['bar']:
                combinations.append({
                    'foo': foo,
                    'bar.p': bar['p'],
                    'bar.q': bar['q'],
                    'baz': '6'
                })

        for per in permuted:
            comb_dict = {}
            for key in combinations[0]:
                comb_dict[key] = per[key]

            self.assertIn(comb_dict, combinations)

    def test_resolve_all_vars(self):

        # Most of the variable resolution stuff is tested elsewhere,
        # but it's good to have it all put together in one final test.
        test = {
            'build': {
                'cmds':
                    ["echo {foo} {bar.p}", "echo {per.foo}", "echo {bar.q}"],
                'env': [
                    {'baz': '{baz}'},
                    {'oof': '{var.blarg.l}-{var.blarg.r}'},
                    {'pav': '{pav.nope}'},
                    {'sys': '{nope}'}]
            },
            'permutations': {
                'foo': ['1', '2'],
                'bar': [
                    {'p': '4', 'q': '4a'},
                ],
            },
            'variables': {
                'baz': ['6'],
                'blarg': {'l': '7', 'r': '8'}
            }
        }

        answer1 = {
                   'build': {
                       'cmds':
                           ["echo 1 4", "echo 1", "echo 4a"],
                       'env': [
                           {'baz': '6'},
                           {'oof': '7-8'},
                           {'pav': '9'},
                           {'sys': '10'}]
                   }
        }

        # This is all that changes between the two.
        import copy
        answer2 = copy.deepcopy(answer1)
        answer2['build']['cmds'] = ["echo 2 4", "echo 2", "echo 4a"]

        answers = [answer1, answer2]

        test, permuted = resolve_permutations(test,
                                              # Pav vars
                                              {'nope': '9'},
                                              # sys vars
                                              {'nope': '10'})

        self.assertEqual(len(permuted), 2)

        # Make sure each of our permuted results is in the list of answers.
        for var_man in permuted:
            out_test = resolve_all_vars(test, var_man, ['build'])
            self.assertIn(out_test, answers)

        # Make sure we can successfully disallow deferred variables in a
        # section.
        test = {
            'build': {
                'cmds': ['echo {foo}']
            }
        }

        dvar = variables.DeferredVariable('foo', 'sys')

        test, permuted = resolve_permutations(test, {}, {'foo': dvar})

        with self.assertRaises(string_parser.ResolveError):
            # No deferred variables in the build section.
            resolve_all_vars(test, permuted[0], ['build'])
