"""Test the various components of the test resolver."""

import copy
import io
import json
import random

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import system_variables
from pavilion.pavilion_variables import PavVars
from pavilion.test_config import TestConfigError, resolver
from pavilion.test_config import variables
from pavilion.unittest import PavTestCase


class ResolverTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        """Initialize plugins and setup a resolver."""
        plugins.initialize_plugins(self.pav_cfg)

        self.resolver = resolver.TestConfigResolver(self.pav_cfg)

    def tearDown(self):
        """Reset the plugins."""
        plugins._reset_plugins()

    def test_loading_tests(self):
        """Make sure get_tests can find tests and resolve inheritance."""

        tests = self.resolver.load(['hello_world'], host='this')
        self.assertEqual(sorted(['narf', 'hello', 'world']),
                         sorted([ptest.config['name'] for ptest in tests]))

        tests = self.resolver.load(['hello_world.hello'], host='this')
        hello_cfg = tests[0].config

        # There should have only been 1
        self.assertEqual(len(tests), 1)
        # Check some basic test attributes.
        self.assertEqual(hello_cfg['scheduler'], 'raw')
        self.assertEqual(hello_cfg['suite'], 'hello_world')
        # Make sure the variable from the host config got propagated.
        self.assertIn('hosty', hello_cfg['variables'])

        tests = self.resolver.load(['hello_world.narf'], host='this')
        narf_cfg = tests[0].config
        # Make sure this got overridden from 'world'
        self.assertEqual(narf_cfg['scheduler'], 'dummy')
        # Make sure this didn't get lost.
        self.assertEqual(narf_cfg['run']['cmds'], ['echo "Running World"'])

    def test_loading_hidden(self):
        """Make sure we only get hidden tests when specifically requested."""

        tests = self.resolver.load(['hidden'], 'this', [])
        names = sorted([t.config['name'] for t in tests])
        self.assertEqual(names, ['hello', 'narf'])

        tests = self.resolver.load(['hidden._hidden'], 'this', [])
        names = sorted([t.config['name'] for t in tests])
        self.assertEqual(names, ['_hidden'])

    def test_layering(self):
        """Make sure test config layering works as expected."""

        for host in ('this', 'layer_host'):
            for modes in ([], ['layer_mode']):
                for test in ('layer_tests.layer_test',
                             'layer_tests.layer_test_part'):
                    answer = None
                    if host == 'layer_host':
                        answer = 'host'
                    if test.endswith('part'):
                        answer = 'test'
                    if modes:
                        answer = 'mode'

                    tests = self.resolver.load(
                        [test],
                        host=host,
                        modes=modes)
                    self.assertEqual(
                        tests[0].config['summary'], answer,
                        msg="host: {}, test: {}, modes: {}"
                            .format(host, test, modes))

    def test_defaulted_variables(self):
        """Make sure default variables work as expected."""

        tests = self.resolver.load(
            tests=['defaulted.test'],
            host='defaulted',
            modes=['defaulted'],
        )

        cfg = tests[0].config
        self.assertEqual(cfg['variables']['host_def'], ['host'])
        self.assertEqual(cfg['variables']['mode_def'], ['mode'])
        self.assertEqual(cfg['variables']['test_def'], ['test'])
        self.assertNotIn('no_val', cfg['variables'])

        with self.assertRaises(TestConfigError):
            self.resolver.load(
                tests=['defaulted_error.error'],
                host='defaulted',
                modes=['defaulted'],
            )

    def test_extended_variables(self):
        """Make sure default variables work as expected."""

        tests = self.resolver.load(
            tests=['extended.test'],
            host='extended',
            modes=['extended'],
        )

        cfg = tests[0].config
        self.assertEqual(cfg['variables']['long_base'],
                         ['what', 'are', 'you', 'up', 'to', 'punk?'])
        self.assertEqual(cfg['variables']['single_base'],
                         ['host', 'test', 'mode'])
        self.assertEqual(cfg['variables']['no_base_mode'],
                         ['mode'])
        self.assertEqual(cfg['variables']['no_base'],
                         ['test'])
        self.assertEqual(cfg['variables']['null_base_mode'],
                         ['mode'])
        self.assertEqual(cfg['variables']['null_base'],
                         ['test'])

    def test_apply_overrides(self):
        """Make sure overrides get applied to test configs correctly."""

        overrides = [
            # A basic value.
            'slurm.num_nodes=3',
            # A specific list item.
            'run.cmds.0="echo nope"',
            # An item that doesn't exist (and must be normalized by yaml_config)
            'variables.foo="hello"',
        ]

        bad_overrides = [
            # No such variables
            'florp.blorp=3',
            # You can't override the scheduler
            'scheduler="raw"',
            # run.cmds is a list
            'run.cmds.eeeh="hello"',
            # Invalid index.
            'run.cmds.10000="ok"',
            # Summary isn't a dict.
            'summary.nope=blarg',
            # A very empty key.
            '""="empty"',
            # Value is an incomplete mapping.
            "summary={asdf",
        ]

        proto_tests = self.resolver.load(['hello_world'], 'this',
                                         overrides=overrides)

        for ptest in proto_tests:
            alt_cfg = copy.deepcopy(ptest.config)

            # Make sure the overrides were applied
            self.assertEqual(alt_cfg['slurm']['num_nodes'], "3")
            self.assertEqual(alt_cfg['run']['cmds'], ['echo nope'])
            # Make sure other stuff wasn't changed.
            self.assertEqual(ptest.config['build'], alt_cfg['build'])
            self.assertEqual(ptest.config['run']['env'], alt_cfg['run']['env'])

        # Make sure we get appropriate errors in several bad key cases.
        for bad_override in bad_overrides:
            with self.assertRaises(TestConfigError):
                self.resolver.load(['hello_world'], 'this',
                                   overrides=[bad_override])

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
            'permute_on': ['foo', 'bar', 'baz'],
            'subtitle': '{{foo}}-{{bar.p}}-{{baz}}',
        }

        orig_permutations = raw_test['variables']
        var_man = copy.deepcopy(self.resolver.base_var_man)
        var_man.add_var_set('var', raw_test['variables'])

        test, permuted = self.resolver.resolve_permutations(
            raw_test, var_man
        )

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
        """Using deferred variables in inappropriate places should raise
        errors."""
        test = {
            'permute_on': ['sys.def'],
            'variables': {},
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'def': variables.DeferredVariable()})

        with self.assertRaises(TestConfigError):
            self.resolver.resolve_permutations(
                test, var_man)

        test = {
            'permute_on': ['foo.1'],
            'variables': {
                'foo': 'bleh'
            }
        }

        with self.assertRaises(TestConfigError):
            self.resolver.resolve_permutations(test, var_man)

        test = {
            'permute_on': ['no_exist'],
            'variables': {},
        }

        with self.assertRaises(TestConfigError):
            self.resolver.resolve_permutations(test, var_man)

    def test_resolve_deferred(self):
        """Make sure deeply nested deferred references are resolved
        correctly"""

        cfg = self._quick_test_cfg()

        cfg['variables'] = {
            'testa': '{{sys.host_name}}',
            'testb': '{{testa}}',
            'testc': ['{{testa}}', '{{testb}}'],
            'testd': {
                'd1': '{{testa}}',
                'd2': '{{testc.1}}',
            },
            'teste': '{{testd.d1}}',
            'testf': '{{testi}}',
            'testg': '{{testh}}',
            'testh': '{{testa}}',
            'testi': '{{testg}}',
            # Resolved, this will have four elements.
            'testj': '{{len(sys.dumb_list.*)}}'
        }

        # Shuffle the dictionary order, to make sure order doesn't matter.
        new_vars = {}
        keys = list(cfg['variables'].keys())
        random.shuffle(keys)
        for key in keys:
            new_vars[key] = cfg['variables'][key]
        cfg['variables'] = new_vars

        test = self._quick_test(cfg, 'deep_deferred')

        host_name = test.var_man['sys.host_name']
        # It looks nuts that these all resolve to the same basic thing, but
        # what's important is that they get resolved at all.
        expected = {
            'testa': [host_name],
            'testb': [host_name],
            'testc': [host_name, host_name],
            'testd': [{'d1': host_name, 'd2': host_name}],
            'teste': [host_name],
            'testf': [host_name],
            'testg': [host_name],
            'testh': [host_name],
            'testi': [host_name],
            'testj': ["4"]
        }

        vars = test.var_man.as_dict()['var']
        for var in expected:
            self.assertEqual(expected[var], vars[var],
                             msg="Mismatch for var '{}'".format(var))

    def test_resolve_vars_in_vars(self):
        test = {
            'permute_on': ['fruit', 'snacks'],
            'variables': {
                'fruit': ['apple', 'orange', 'banana'],
                'snacks': ['{{fruit}}-x', '{{sys.soda}}'],
                'stuff': 'y{{fruit}}-{{snacks}}',
            }
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'soda': 'pepsi'})
        var_man.add_var_set('var', test['variables'])

        test, permuted = self.resolver.resolve_permutations(test, var_man)

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

        var_man = copy.deepcopy(self.resolver.base_var_man)
        var_man.add_var_set('var', test['variables'])

        with self.assertRaises(variables.VariableError):
            self.resolver.resolve_permutations(test, var_man)

    def test_finalize(self):

        cfg = self._quick_test_cfg()

        cfg['run']['cmds'] = [
            'echo "{{sys.host_name}}"'
        ]

        cfg['result_parse'] = {
            'regex': {
                'foo': {'regex': '{{sys.host_name}}'}
            }
        }

        test = self._quick_test(cfg, 'finalize_test',
                                build=False, finalize=False)

        test.build()

        undefered_sys_vars = system_variables.SysVarDict(
            unique=True,
        )

        fin_var_man = variables.VariableSetManager()
        fin_var_man.add_var_set('sys', undefered_sys_vars)

        resolver.TestConfigResolver.finalize(test, fin_var_man)

        results = test.gather_results(test.run())
        test.save_results(results)

    def test_resolve_all_vars(self):
        """Most of the variable resolution stuff is tested elsewhere,
        but it's good to have it all put together in one final test."""

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
            'permute_on': ['foo', 'bar'],
            'subtitle': None,
        }

        answer1 = {
                'permute_on': ['foo', 'bar'],
                'subtitle': '1-_bar_',
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
        answer2 = copy.deepcopy(answer1)
        answer2['build']['cmds'] = ["echo 2 4", "echo 2", "echo 4a"]
        answer2['subtitle'] = '2-_bar_'

        answers = [answer1, answer2]

        var_man = variables.VariableSetManager()
        var_man.add_var_set('pav', {'nope': '9'})
        var_man.add_var_set('sys', {'nope': '10'})
        var_man.add_var_set('var', test['variables'])
        del test['variables']

        test, permuted = self.resolver.resolve_permutations(test, var_man)

        self.assertEqual(len(permuted), 2)

        # Make sure each of our permuted results is in the list of answers.
        for var_man in permuted:
            out_test = self.resolver.resolve_test_vars(test, var_man)
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

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'foo': variables.DeferredVariable()})
        var_man.add_var_set('var', {})

        test, permuted = self.resolver.resolve_permutations(test, var_man)

        with self.assertRaises(resolver.TestConfigError):
            # No deferred variables in the build section.
            self.resolver.resolve_test_vars(test, permuted[0])

    def test_env_order(self):
        """Make sure environment variables keep their order from the test
        config to the final run scripts."""

        ptests = self.resolver.load(['order'], host='this')

        test_conf = ptests[0].config

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

    def test_command_inheritance(self):
        """Make sure command inheritance works as expected."""

        tests = self.resolver.load(['cmd_inherit_extend'])

        correct = {
            'test1': {
                'build': {
                    'cmds': ['echo "and I say hello"'],
                },
                'run': {
                    'cmds': ['echo "Hello"'],
                }
            },
            'test2': {
                'build': {
                    'cmds': [
                        'echo "You say goodbye"',
                        'echo "and I say hello"'
                    ]
                },
                'run': {
                    'cmds': [
                        'echo "Hello"',
                        'echo ", hello"'
                    ]
                }
            },
            'test3': {
                'build': {
                    'cmds': [
                        'echo "You say goodbye"',
                        'echo "and I say hello"'
                    ]
                },
                'run': {
                    'cmds': [
                        'echo "Hello"',
                        'echo ", hello"',
                        'echo "I dont know why you say goodbye,"',
                        'echo "I say hello"'
                    ]
                }
            }
        }

        for test in tests:
            test_name = test.config.get('name')

            for sec in ['build', 'run']:
                self.assertEqual(test.config[sec]['cmds'],
                                 correct[test_name][sec]['cmds'])

    def test_cmd_inheritance_layering(self):
        """Test command inheritance with host and mode configs."""

        correct = {
            'test1': {
                'build': {
                    'cmds': ['echo "and I say hello"'],
                },
                'run': {
                    'cmds': ['echo "Hello"'],
                }
            },
            'test2': {
                'build': {
                    'cmds': [
                        'echo "You say goodbye"',
                        'echo "and I say hello"'
                    ]
                },
                'run': {
                    'cmds': [
                        'echo "Hello"',
                        'echo ", hello"'
                    ]
                }
            },
            'test3': {
                'build': {
                    'cmds': [
                        'echo "You say goodbye"',
                        'echo "and I say hello"'
                    ]
                },
                'run': {
                    'cmds': [
                        'echo "Hello"',
                        'echo ", hello"',
                        'echo "I dont know why you say goodbye,"',
                        'echo "I say hello"'
                    ]
                }
            }
        }

        for host in ('this', 'layer_host'):
            for modes in ([], ['layer_mode']):
                for test in ('cmd_inherit_extend.test1',
                             'cmd_inherit_extend.test2',
                             'cmd_inherit_extend.test3'):
                    answer = None

                    tests = self.resolver.load([test], host=host,modes=modes)
                    test_cfg = tests[0].config
                    test_name = test_cfg.get('name')
                    for sec in ['build', 'run']:
                        self.assertEqual(test_cfg[sec]['cmds'],
                                         correct[test_name][sec]['cmds'])
                    self.assertEqual(test_cfg['host'], host)
                    self.assertEqual(test_cfg['modes'], modes)

    def test_version_compatibility(self):
        """Make sure version compatibility checks are working and populate the
        results.json file correctly."""

        pav_version = PavVars().version()

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-w',
            '5',
            'version_compatible'
        ])

        expected_results = {
            'version_compatible.one': {
                'test_version': '1.2.3',
                'pav_version': pav_version
            },
            'version_compatible.two': {
                'test_version': 'beta',
                'pav_version': pav_version
            },
            'version_compatible.three': {
                'test_version': '0.0',
                'pav_version': pav_version
            }
        }

        # Ensures Version information gets populated correclty even with empty
        # version section in test config
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        for test in run_cmd.last_tests:
            test.wait(timeout=1)
            results = test.load_results()
            name = results['name']
            for key in expected_results[name].keys():
                self.assertEqual(expected_results[name][key],
                                 results[key])

    def test_version_incompatibility(self):
        """Make sure incompatible versions exit gracefully when attempting to
        run."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'version_incompatible'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.errfile = run_cmd.outfile
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 22)
