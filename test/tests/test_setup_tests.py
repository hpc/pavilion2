
from pavilion.unittest import PavTestCase
from pavilion import system_variables
from pavilion.test_config import (load_test_configs,
                                  TestConfigError,
                                  apply_overrides,
                                  resolve_permutations,
                                  resolve_config)
from pavilion.test_config import variables, string_parser
from pavilion import plugins


class TestSetupTests(PavTestCase):

    def test_loading_tests(self):
        """Make sure get_tests can find tests and resolve inheritance."""

        plugins.initialize_plugins(self.pav_cfg)

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world'])
        self.assertEqual(sorted(['narf', 'hello', 'world']),
                         sorted([test['name'] for test in tests]))

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world.hello'])
        hello = tests.pop()

        # There should have only been 1
        self.assertFalse(tests)
        # Check some basic test attributes.
        self.assertEqual(hello['scheduler'], 'raw')
        self.assertEqual(hello['suite'], 'hello_world')
        # Make sure the variable from the host config got propagated.
        self.assertIn('hosty', hello['variables'])

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hello_world.narf'])
        narf = tests.pop()
        # Make sure this got overridden from 'world'
        self.assertEqual(narf['scheduler'], 'dummy')
        # Make sure this didn't get lost.
        self.assertEqual(narf['run']['cmds'], ['echo "Running World"'])

        plugins._reset_plugins()

    def test_loading_hidden(self):
        """Make sure we only get hidden tests when specifically requested."""

        plugins.initialize_plugins(self.pav_cfg)

        tests = load_test_configs(self.pav_cfg, 'this', [], ['hidden'])
        names = sorted([t['name'] for t in tests])
        self.assertEqual(names, ['hello', 'narf'])

        tests = load_test_configs(self.pav_cfg, 'this', [],
                                  ['hidden._hidden'])
        names = sorted([t['name'] for t in tests])
        self.assertEqual(names, ['_hidden'])

        plugins._reset_plugins()

    def test_layering(self):
        """Make sure test config layering works as expected."""

        plugins.initialize_plugins(self.pav_cfg)

        for host in ('this', 'layer_host'):
            for modes in ([], ['layer_mode']):
                for test in ('layer_tests.layer_test',
                             'layer_tests.layer_test_part'):
                    answer = 'standard'
                    if host == 'layer_host':
                        answer = 'host'
                    if modes:
                        answer = 'mode'
                    if test.endswith('part'):
                        answer = 'test'

                    tests = load_test_configs(
                        pav_cfg=self.pav_cfg,
                        host=host,
                        modes=modes,
                        tests=[test])
                    self.assertEqual(tests[0]['slurm']['partition'], answer)

        plugins._reset_plugins()

    def test_defaulted_variables(self):
        """Make sure default variables work as expected."""

        plugins.initialize_plugins(self.pav_cfg)

        tests = load_test_configs(
            self.pav_cfg,
            host='defaulted',
            modes=['defaulted'],
            tests=['defaulted.test']
        )

        test = tests[0]
        self.assertEqual(test['variables']['host_def'], ['host'])
        self.assertEqual(test['variables']['mode_def'], ['mode'])
        self.assertEqual(test['variables']['test_def'], ['test'])
        self.assertNotIn('no_val', test['variables'])

        with self.assertRaises(TestConfigError):
            tests = load_test_configs(
                self.pav_cfg,
                host='defaulted',
                modes=['defaulted'],
                tests=['defaulted_error.error']
            )

        plugins._reset_plugins()

    def test_extended_variables(self):
        """Make sure default variables work as expected."""

        plugins.initialize_plugins(self.pav_cfg)

        tests = load_test_configs(
            self.pav_cfg,
            host='extended',
            modes=['extended'],
            tests=['extended.test']
        )

        test = tests[0]
        self.assertEqual(test['variables']['long_base'],
                         ['what', 'are', 'you', 'up', 'to', 'punk?'])
        self.assertEqual(test['variables']['single_base'],
                         ['host', 'mode', 'test'])
        self.assertEqual(test['variables']['no_base_mode'],
                         ['mode'])
        self.assertEqual(test['variables']['no_base'],
                         ['test'])
        self.assertEqual(test['variables']['null_base_mode'],
                         ['mode'])
        self.assertEqual(test['variables']['null_base'],
                         ['test'])


        plugins._reset_plugins()

    def test_apply_overrides(self):
        """Make sure overrides get applied to test configs correctly."""

        plugins.initialize_plugins(self.pav_cfg)

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

        plugins._reset_plugins()

    def test_resolve_permutations(self):
        """Make sure permutations are applied correctly."""

        raw_test = {
            'build': {
                'cmds':
                    ["echo {{foo}} {{bar.p}}",
                     "echo {{foo}}",
                     "echo {{bar.q}}"],
                'env':
                    {'baz': '{{baz}}'}
            },
            'variables': {
                'foo': ['1', '2', '3'],
                'bar': [
                    {'p': '4', 'q': '4a'},
                    {'p': '5', 'q': '5a'},
                ],
                'baz': ['6'],
                'blarg': ['7', '8']
            },
            'permute_on': ['foo', 'bar', 'baz']
        }

        orig_permutations = raw_test['variables']

        test, permuted = resolve_permutations(raw_test, {}, {})

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

    def test_deferred_errors(self):
        test = {
            'permute_on': ['sys.def'],
            'variables': {},
        }

        with self.assertRaises(TestConfigError):
            resolve_permutations(
                test, {}, {'def': variables.DeferredVariable()})

        test = {
            'permute_on': ['foo.1'],
            'variables': {
                'foo': 'bleh'
            }
        }

        with self.assertRaises(TestConfigError):
            resolve_permutations(test, {}, {})

        test = {
            'permute_on': ['no_exist'],
            'variables': {},
        }

        with self.assertRaises(TestConfigError):
            resolve_permutations(test, {}, {})

    def test_resolve_vars_in_vars(self):
        test = {
            'permute_on': ['fruit', 'snacks'],
            'variables': {
                'fruit': ['apple', 'orange', 'banana'],
                'snacks': ['{{fruit}}-x', '{{sys.soda}}'],
                'stuff': 'y{{fruit}}-{{snacks}}'
            }
        }

        test, permuted = resolve_permutations(test, {}, {'soda':'pepsi'})

        possible_stuff = ['yapple-apple-x',
                          'yapple-pepsi',
                          'yorange-orange-x',
                          'yorange-pepsi',
                          'ybanana-banana-x',
                          'ybanana-pepsi']

        stuff = [var_man['var.stuff'] for var_man in permuted]
        possible_stuff.sort()
        stuff.sort()
        self.assertEqual(possible_stuff, stuff)

    def test_for_circular_variable_references(self):
        test = {
            'variables': {
                'a': '--{{d}}-{{b}}-',
                'b': '--{{e}}--',
                'c': '--{{a}}-{{b}}-',
                'd': '--{{c}}--',
                'e': '--e--',
            },
            'permute_on': []
        }

        with self.assertRaises(variables.VariableError):
            resolve_permutations(test, {}, {})

    def test_finalize(self):

        plugins.initialize_plugins(self.pav_cfg)

        cfg = self._quick_test_cfg()

        cfg['run']['cmds'] = [
            'echo "{{sys.host_name}}"'
        ]

        cfg['results'] = {
            'regex': [{
                'key': 'foo',
                'regex': '{{sys.host_name}}',
            }]
        }

        test = self._quick_test(cfg, 'finalize_test',
                                build=False, finalize=False)

        test.build()

        undefered_sys_vars = system_variables.SysVarDict(
            defer=False,
            unique=True,
        )

        fin_var_man = variables.VariableSetManager()
        fin_var_man.add_var_set('sys', undefered_sys_vars)

        test.finalize(fin_var_man)

        results = test.gather_results(test.run())
        test.save_results(results)

        plugins._reset_plugins()

    def test_resolve_all_vars(self):

        # Most of the variable resolution stuff is tested elsewhere,
        # but it's good to have it all put together in one final test.
        test = {
            'build': {
                'cmds':
                    ["echo {{foo}} {{bar.p}}",
                     "echo {{var.foo}}",
                     "echo {{bar.q}}"],
                'env': [
                    {'baz': '{{baz}}'},
                    {'oof': '{{var.blarg.l}}-{{var.blarg.r}}'},
                    {'pav': '{{pav.nope}}'},
                    {'sys': '{{nope}}'}]
            },
            'variables': {
                'baz': ['6'],
                'blarg': [{'l': '7', 'r': '8'}],
                'foo': ['1', '2'],
                'bar': [
                    {'p': '4', 'q': '4a'},
                ],
            },
            'permute_on': ['foo', 'bar']
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
            out_test = resolve_config(test, var_man, ['build'])
            self.assertIn(out_test, answers)

        # Make sure we can successfully disallow deferred variables in a
        # section.
        test = {
            'build': {
                'cmds': ['echo {{foo}}']
            },
            'permute_on': [],
            'variables': {}
        }

        dvar = variables.DeferredVariable()

        test, permuted = resolve_permutations(test, {}, {'foo': dvar})

        with self.assertRaises(string_parser.ResolveError):
            # No deferred variables in the build section.
            resolve_config(test, permuted[0], ['build'])

    def test_env_order(self):
        """Make sure environment variables keep their order from the test
        config to the final run scripts."""

        plugins.initialize_plugins(self.pav_cfg)

        test_conf = load_test_configs(self.pav_cfg, 'this', [], ['order'])[0]

        test = self._quick_test(test_conf, "order")

        # Each exported variable in this config has a value that denotes its
        # expected place in the order. The variable names are random letter
        # sequences in a random order; hash order should be decidedly different
        # than the listed order.
        exports = []
        with (test.path/'build.sh').open() as build_script:
            for line in build_script:
                if line.startswith('export'):
                    if 'TEST_ID' in line or 'PAV_CONFIG_FILE' in line:
                        continue

                    _, var_val = line.split()
                    var, val = line.split('=')
                    try:
                        val = int(val)
                    except ValueError:
                        raise

                    exports.append((var, val))

        # The values should be the numbers for 0..99, in that order.
        self.assertEqual(list(range(len(exports))),
                         [val for var, val in exports],
                         msg="Environment variable order not preserved.  \n"
                             "Got the following instead: \n{}"
                             .format(''.join(["{}: {}\n".format(*v) for v in
                                              exports])))

        plugins._reset_plugins()
