"""Test the various components of the test resolver."""

import copy
import io
import random
import time

from pavilion import arguments
from pavilion import commands
from pavilion import errors
from pavilion import plugins
from pavilion import resolve
from pavilion import resolver
from pavilion import schedulers
from pavilion import test_run
from pavilion import variables
from pavilion.deferred import DeferredVariable
from pavilion.errors import TestConfigError, TestRunError
from pavilion.pavilion_variables import PavVars
from pavilion.sys_vars import base_classes
from pavilion.unittest import PavTestCase


class ResolverTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        """Initialize plugins and setup a resolver."""
        plugins.initialize_plugins(self.pav_cfg)

        self.resolver = resolver.TestConfigResolver(self.pav_cfg, host='this')

    def test_resolve_speed(self):

        self.resolver.load(['speed'])

    def test_requests(self):
        """Check request parsing."""

        requests = (
            ('hello',                   ('hello', None, 1)),

            ('hello123',                ('hello123', None, 1)),
            ('123-_hello',              ('123-_hello', None, 1)),
            ('123hello.world',          ('123hello', 'world', 1)),
            ('123hello.123world',       ('123hello', '123world', 1)),
            ('123hello.123-_world-',    ('123hello', '123-_world-', 1)),
            ('5*123hello.world',        ('123hello', 'world', 5)),
            ('5*123hello.123world',     ('123hello', '123world', 5)),
            ('5*123hello.123-_world-',  ('123hello', '123-_world-', 5)),
            ('123hello.world3*6',       ('123hello', 'world3', 6)),
            ('123hello.123world3*6',    ('123hello', '123world3', 6)),
            ('123hello.123-_world-3*6', ('123hello', '123-_world-3', 6)),
        )

        for req_str, answer in requests:
            req = resolver.TestRequest(req_str)
            self.assertEqual((req.suite, req.test, req.count), answer)

        for request, answer in (
                ('3*hello.world*5', 'cannot have both a pre-count'),
                ('foo.bar.baz.quux', 'must be in the form'),):
            with self.assertRaisesRegex(TestConfigError, answer):
                resolver.TestRequest(request)

    def test_loading_tests(self):
        """Make sure get_tests can find tests and resolve inheritance."""

        tests = self.resolver.load(['hello_world'])
        self.assertEqual(sorted(['narf', 'hello', 'world']),
                         sorted([ptest.config['name'] for ptest in tests]))

        tests = list(self.resolver.load(['hello_world.hello']))
        hello_cfg = tests[0].config

        # There should have only been 1
        self.assertEqual(len(tests), 1)
        # Check some basic test attributes.
        self.assertEqual(hello_cfg['scheduler'], 'raw')
        self.assertEqual(hello_cfg['suite'], 'hello_world')
        # Make sure the variable from the host config got propagated.
        self.assertIn('hosty', hello_cfg['variables'])

        tests = list(self.resolver.load(['hello_world.narf']))
        narf_cfg = tests[0].config
        # Make sure this got overridden from 'world'
        self.assertEqual(narf_cfg['scheduler'], 'dummy')
        # Make sure this didn't get lost.
        self.assertEqual(narf_cfg['run']['cmds'], ['echo "Running World"'])

    def test_loading_hidden(self):
        """Make sure we only get hidden tests when specifically requested."""

        tests = self.resolver.load(['hidden'])
        names = sorted([t.config['name'] for t in tests])
        self.assertEqual(names, ['hello', 'narf'])
        tests = self.resolver.load(['hidden._hidden'])
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

                    rslvr = resolver.TestConfigResolver(self.pav_cfg, host=host)

                    tests = rslvr.load(
                        [test],
                        modes=modes)
                    self.assertEqual(
                        tests[0].config['summary'], answer,
                        msg="host: {}, test: {}, modes: {}"
                            .format(host, test, modes))

    def test_defaulted_variables(self):
        """Make sure default variables work as expected."""

        rslvr = resolver.TestConfigResolver(self.pav_cfg, host='defaulted')
        tests = rslvr.load(
            tests=['defaulted'],
            modes=['defaulted'],
        )

        def find_test(tests, name):
            """Find a test with the given name in the list of tests and return it."""
            for test in tests:
                if name in test.config['name']:
                    return test
            raise ValueError("Could not find test {}".format(name))

        test_vars = find_test(tests, 'base').config['variables']

        # These make sure variable defaults with sub-dicts are resolved
        # properly.
        stack1a_vars = find_test(tests, 'stack1a').config['variables']
        stack1b_vars = find_test(tests, 'stack1b').config['variables']
        stack2a_vars = find_test(tests, 'stack2a').config['variables']
        stack2b_vars = find_test(tests, 'stack2b').config['variables']

        self.assertEqual(test_vars['host_def'], [{None: 'host'}])
        self.assertEqual(test_vars['mode_def'], [{None: 'mode'}])
        self.assertEqual(test_vars['test_def'], [{None: 'test'}])
        self.assertEqual(test_vars['stack_def'], [{'a': 'base', 'b': 'base'}])
        self.assertNotIn('no_val', test_vars)

        # stack1 just sets defaults all the way up, so the values
        # at each level should just be the defaults set at that level.
        self.assertEqual(stack1a_vars['stack_def'][0]['a'], '1a-a')
        self.assertEqual(stack1a_vars['stack_def'][0]['b'], '1a-b')
        self.assertEqual(stack2a_vars['stack_def'][0]['a'], '2a-a')
        self.assertEqual(stack2a_vars['stack_def'][0]['b'], '2a-b')

        # Stack2 sets 'a' but not 'b', so 'b' should be 'base' except
        # at stack2b, where the default is changed. 'a' should be '1b-a'
        # at levels higher than 'base'
        self.assertEqual(stack1b_vars['stack_def'][0]['a'], '1b-a')
        self.assertEqual(stack1b_vars['stack_def'][0]['b'], 'base')
        self.assertEqual(stack2b_vars['stack_def'][0]['a'], '1b-a')
        self.assertEqual(stack2b_vars['stack_def'][0]['b'], '2b-b')


        with self.assertRaisesRegex(TestConfigError,
                                    "Variable values must be unicode"):
            rslvr.load(
                tests=['defaulted_error.error'],
                modes=['defaulted'])

    def test_variable_consistency(self):
        """Make sure the variable consistency checks catch what they're supposed to."""

        bad_tests = [
            ('var_consistency.empty_var_list', "'foo' was defined but wasn't given a value."),
            ('var_consistency.empty_var', "must be unicode strings, got 'None'"),
            ('var_consistency.empty_subvar', "must be unicode strings, got 'None'"),
            ('var_consistency2.inconsistent_var1', "section has items of differing formats."),
            ('var_consistency3.inconsistent_var2', "section has items of differing formats."),
            ('var_consistency.inconsistent_var3', "Idx 1 had keys"),
            ('var_consistency.inconsistent_var4', "Idx 1 had keys"),
            ('var_consistency.foo', "Error processing variable key 'var.foo.1'"),
        ]

        for bad_test, bad_excerpt in bad_tests:
            with self.assertRaisesRegex(TestConfigError, bad_excerpt):
                try:
                    self.resolver.load([bad_test])
                except errors.PavilionError as err:
                    raise


    def test_wildcards(self):
        """Make sure wildcarded tests and permutations work"""

        for test_request, result_count, result_unique in (
                ('wildcard.some[tm]est', 8, 8),
                ('wildcard.some*', 8, 8),
                ('wildcard.*', 9, 9),
                ('2*wildcard.some?est', 16, 8),
                ('wildcard.**2', 18, 9),
                ('wildcard', 9, 9),
                ('wildcard._base', 1, 1)):
            tests = self.resolver.load(tests=[test_request])

            self.assertEqual(len(tests), result_count)
            test_names = [(test.config['suite'], test.config['name'], test.config['subtitle']) for test in tests]
            test_names = set(test_names)
            self.assertEqual(len(test_names), result_unique)

        for perm_request, result_count in (
                ('wildcard.*.b-1', 2),
                ('wildcard.*.*', 8),
                ('wildcard.sometest.*-1', 2),
                ('wildcard.sometest.a-**2', 4),
                ('2 * wildcard.somemest.c-4', 2),
                ('wildcard.somemest.[cb]-*', 4)):
            tests = self.resolver.load(tests=[perm_request])

            self.assertEqual(len(tests), result_count)

        for bad_request, bad_excerpt in (
                ('wildcard.noperms.*', "doesn't have permutations at all"),
                ('wildcard.sometest.not_me', "Available permutations:"),
                ('wildcard.doesnt_exist', "test that matches 'doesnt_exist'"),
                ('wildcard.[invalidfnmatch', r"test that matches '\[invalidfnmatch'")):
            with self.assertRaisesRegex(TestConfigError, bad_excerpt):
                self.resolver.load([bad_request])

    def test_extended_variables(self):
        """Make sure extending variables works correctly."""

        rslvr = resolver.TestConfigResolver(self.pav_cfg, host='extended')
        tests = rslvr.load(
            tests=['extended.test'],
            modes=['extended'],
        )

        cfg = tests[0].config
        long_answer = ['checking', 'for', 'proper', 'extending', 'including',
                       'including', 'including', 'duplicates']
        long_answer = [{None: word} for word in long_answer]
        self.assertEqual(cfg['variables']['long_base'], long_answer)
        self.assertEqual(cfg['variables']['single_base'],
                         [{None: key} for key in ['host', 'test', 'mode']])
        self.assertEqual(cfg['variables']['no_base_mode'],
                         [{None: 'mode'}])
        self.assertEqual(cfg['variables']['no_base'],
                         [{None: 'test'}])
        self.assertEqual(cfg['variables']['null_base_mode'],
                         [{None: 'mode'}])
        self.assertEqual(cfg['variables']['null_base'],
                         [{None: 'test'}])

    def test_apply_overrides(self):
        """Make sure overrides get applied to test configs correctly."""

        overrides = [
            # A basic value.
            'schedule.nodes=3',
            # A specific list item.
            'run.cmds.0="echo nope"',
            # An item that doesn't exist (and must be normalized by yaml_config)
            'variables.foo="hello"',
            # A complex variable value
            'variables.bar={"hello": "world"}'
        ]

        bad_overrides = [
            # No such variables
            ('florp.blorp=3', "there is no such key"),
            # run.cmds is a list
            ('run.cmds.eeeh="hello"', "a non-integer 'eeeh' in key"),
            # Invalid index.
            ('run.cmds.10000="ok"', "index is out of range"),
            # Summary isn't a dict.
            ('summary.nope=blarg', "but 'nope' isn't a dict or list."),
            # A very empty key.
            ('=empty', "given a blank key"),
            # A very empty key.
            ('foo.a b=empty', "has whitespace in its key"),
            # A very empty key.
            ('foo.=empty', "has an empty key part"),
            # Value is an incomplete mapping.
            ("summary={asdf", "Invalid value '{asdf'"),
        ]

        proto_tests = self.resolver.load(['hello_world'],
                                         overrides=overrides)

        for ptest in proto_tests:
            alt_cfg = copy.deepcopy(ptest.config)

            # Make sure the overrides were applied
            self.assertEqual(alt_cfg['schedule']['nodes'], "3")
            self.assertEqual(alt_cfg['run']['cmds'], ['echo nope'])
            # Make sure other stuff wasn't changed.
            self.assertEqual(ptest.config['build'], alt_cfg['build'])
            self.assertEqual(ptest.config['run']['env'], alt_cfg['run']['env'])

        # Make sure we get appropriate errors in several bad key cases.
        for bad_override, bad_excerpt in bad_overrides:
            with self.assertRaisesRegex(TestConfigError, bad_excerpt):
                self.resolver.load(['hello_world'], overrides=[bad_override])

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
            'scheduler': 'raw',
        }

        orig_permutations = raw_test['variables']
        var_man = copy.deepcopy(self.resolver._base_var_man)
        rproto = resolver.RawProtoTest(resolver.TestRequest('dummy'),
                                       raw_test, var_man)
        var_man.add_var_set('var', raw_test['variables'])

        ptests = rproto.resolve_permutations()

        # Foo should triple the permutations, bar should double them -> 6
        # baz shouldn't have an effect (on the permutation count).
        # blarg shouldn't either, because it's never used.
        self.assertEqual(len(ptests), 6)

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

        for ptest in ptests:
            comb_dict = {}
            for key in combinations[0]:
                comb_dict[key] = ptest.var_man[key]

            self.assertIn(comb_dict, combinations)

    def test_permute_on_ref(self):
        """A regression test to make sure we handle references in the complex part
        of a permuted variable correctly."""

        # Make sure permute variables that reference themselves resolve correctly. There
        # was a bug that resolved these variables before they were permuted on.
        ptests = self.resolver.load(['permute_on_ref.multi'])
        results = set()
        expected = {'7', '11', '15'}
        for ptest in ptests:
            results.add(ptest.config['run']['cmds'][0])
        self.assertEqual(results, expected)

        # Similarly ensure that permutation variables that reference scheduler variables
        # get permuted on after we get scheduler info. This wasn't a bug, but is a case
        # that was similarly untested for.
        results2 = set()
        ptests2 = self.resolver.load(['permute_on_ref.sched'])
        expected2 = {'0', '1', '90'}
        for ptest in ptests2:
            results2.add(ptest.config['run']['cmds'][0])
        self.assertFalse(self.resolver.errors)
        self.assertEqual(results2, expected2)

        # Check that indirect self-references are permuted on as well
        ptests = self.resolver.load(['permute_on_ref.indirect'])
        results = set()
        expected = {'7', '11'}
        for ptest in ptests:
            results.add(ptest.config['run']['cmds'][0])
        self.assertEqual(results, expected)

    def test_deferred_errors(self):
        """Using deferred variables in inappropriate places should raise
        errors."""
        tests = [({'permute_on': ['sys.def'],
                   'variables': {}},
                   "sys.def' references a deferred variable"),
                 ({'permute_on': ['foo.1'],
                   'variables': {'foo': 'bleh'}},
                  "Permutation variable 'foo.1' contains"),
                 ({'permute_on': ['no_exist'],
                   'variables': {}},
                  "Permutation variable 'no_exist' is not defined")]

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'def': DeferredVariable()})

        for test, answer in tests:

            rptest = resolver.RawProtoTest(
                request=resolver.TestRequest('dummy'),
                config=test,
                base_var_man=var_man)

            with self.assertRaisesRegex(TestConfigError, answer):
                rptest.resolve_permutations()

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

        var_dict = test.var_man.as_dict()['var']
        for var in expected:
            self.assertEqual(expected[var], var_dict[var],
                             msg="Mismatch for var '{}'".format(var))

    def test_resolve_vars_in_vars(self):
        """Check resolution of variables within variables."""

        test = {
            'permute_on': ['fruit', 'snacks'],
            'variables': {
                'fruit': ['apple', 'orange', 'banana'],
                'snacks': ['{{fruit}}-x', '{{sys.soda}}'],
                'stuff': 'y{{fruit}}-{{snacks}}',
            },
            'scheduler': 'raw',
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'soda': 'pepsi'})

        rptest = resolver.RawProtoTest(
            request=resolver.TestRequest('dummy'),
            config=test,
            base_var_man=var_man)

        ptests = rptest.resolve_permutations()

        possible_stuff = ['yapple-apple-x',
                          'yapple-pepsi',
                          'yorange-orange-x',
                          'yorange-pepsi',
                          'ybanana-banana-x',
                          'ybanana-pepsi']

        stuff = [ptest.var_man['var.stuff'] for ptest in ptests]
        possible_stuff.sort()
        stuff.sort()
        self.assertEqual(possible_stuff, stuff)

    def test_circular_variable_references(self):
        """Check detection of variables that refer to themselves."""

        test = {
            'variables': {
                'a': '--{{d}}-{{b}}-',
                'b': '--{{e}}--',
                'c': '--{{a}}-{{b}}-',
                'd': '--{{c}}--',
                'e': '--e--',
            },
            'permute_on': [],
            'scheduler': 'raw',
        }

        rptest = resolver.RawProtoTest(
            request=resolver.TestRequest('dummy'),
            config=test,
            base_var_man=self.resolver._base_var_man)

        with self.assertRaisesRegex(TestConfigError, 'contained reference loop'):
            rptest.resolve_permutations()

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

        undefered_sys_vars = base_classes.SysVarDict(
            unique=True,
        )

        fin_var_man = variables.VariableSetManager()
        fin_var_man.add_var_set('sys', undefered_sys_vars)
        sched = schedulers.get_plugin('raw')
        fin_var_man.add_var_set('sched', sched.get_final_vars(test))

        test.finalize(fin_var_man)

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
                'bloop': '{{baz}}'
            },
            'permute_on': ['foo', 'bar'],
            'subtitle': None,
            'scheduler': 'raw',
            'schedule': {
                'nodes': '{{bar.0.p}}',
                # Make sure recursive vars work too.
                'reservation': '{{bloop}}',

            },
        }

        answer1 = {
                'permute_on': ['foo', 'bar'],
                'subtitle': '_bar_-1',
                'build': {
                       'cmds': ["echo 1 4", "echo 1", "echo 4a"],
                       'env': [
                           {'baz': '6'},
                           {'oof': '7-8'},
                           {'pav': '9'},
                           {'sys': '10'}]
                   },
                'scheduler': 'raw',
                'schedule': {
                    'nodes': '4',
                    'reservation': '6',
                }
        }

        # This is all that changes between the two.
        answer2 = copy.deepcopy(answer1)
        answer2['build']['cmds'] = ["echo 2 4", "echo 2", "echo 4a"]
        answer2['subtitle'] = '_bar_-2'

        answers = [answer1, answer2]

        var_man = variables.VariableSetManager()
        var_man.add_var_set('pav', {'nope': '9'})
        var_man.add_var_set('sys', {'nope': '10'})

        rptest = resolver.RawProtoTest(resolver.TestRequest('dummy'), test, var_man)

        ptests = rptest.resolve_permutations()

        self.assertEqual(len(ptests), 2)

        # Make sure each of our permuted results is in the list of answers.
        for ptest in ptests:
            out_test = resolve.test_config(test, ptest.var_man)
            # This is a random number that gets added. It can't be predicted.
            del out_test['permute_base']
            del out_test['variables']
            self.assertIn(out_test, answers)

        # Make sure we can successfully disallow deferred variables in a
        # section.
        test = {
            'build': {
                'cmds': ['echo {{foo}}']
            },
            'permute_on': [],
            'scheduler': 'raw',
            'variables': {}
        }

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sys', {'foo': DeferredVariable()})

        rptest = resolver.RawProtoTest(resolver.TestRequest('dummy'), test, var_man)

        ptest = rptest.resolve_permutations()[0]

        with self.assertRaisesRegex(TestConfigError, 'Deferred variable.*where it isn.t allowed'):
            # No deferred variables in the build section.
            resolve.test_config(ptest.config, ptest.var_man)

    def test_env_order(self):
        """Make sure environment variables keep their order from the test
        config to the final run scripts."""

        ptests = self.resolver.load(['order'])

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

                    rslvr = resolver.TestConfigResolver(self.pav_cfg, host=host)
                    tests = rslvr.load([test], modes=modes)
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

        ptests = self.resolver.load(['version_compatible'])

        expected = {
            'one': '1.2.3',
            'two': 'beta',
            'three': '0.0',
        }

        for ptest in ptests:
            self.assertEqual(ptest.config['test_version'],
                             expected[ptest.config['name']])
            self.assertEqual(ptest.var_man['pav.version'], pav_version)

        with self.assertRaisesRegex(TestConfigError, 'has incompatibility'):
            self.resolver.load(['version_incompatible'])

    def test_sched_errors(self):
        """Scheduler config errors are deferred until tests are saved, if possible."""

        # This test has an from when it tried to get scheduler vars. It should be
        # thrown when we try to save the test.
        tests = self.resolver.load(['sched_errors.a_error'])
        test = test_run.TestRun(self.pav_cfg, tests[0].config, tests[0].var_man)
        with self.assertRaises(TestRunError):
            test.save()

        # This test has the same error, but is skipped. It should throw an error
        # from trying to save a skipped test.
        tests = self.resolver.load(['sched_errors.b_skipped'])
        test = test_run.TestRun(self.pav_cfg, tests[0].config, tests[0].var_man)
        with self.assertRaises(RuntimeError):
            test.save()

        # This test should have an error but denote that other sched var errors might
        # be the problem.
        with self.assertRaises(TestConfigError):
            self.resolver.load(['sched_errors.c_other_error'])

        # This test should be fine.
        self.resolver.load(['sched_errors.d_no_nodes'])

    def test_permute_order(self):
        """Check that tests resolve with both variable/permute resolution orders."""

        for test, count in ('sched', 90), ('multi-sched', 5), ('both', 10):
            test = 'permute_order.{}'.format(test)
            tests = self.resolver.load([test])
            self.assertEqual(len(tests), count)

    def test_parse_error(self):
        """Make sure errors in parsing are handled properly."""


        for test_name in (
                'bad_var_syntax',
                'bad_var_ref',
                'bad_ref',
                'bad_syntax',
                # Yaml errors
                'missing_key_same',
                'missing_key_above',
                'missing_key_below',
                'missing_key_collect',
                'invalid_yaml',
                ):
            test_name = 'parse_errors.{}'.format(test_name)

            with self.assertRaises(TestConfigError):
                try:
                    self.resolver.load([test_name])
                except TestConfigError as err:
                    # Make sure the error can be formatted.
                    err.pformat()
                    raise

    def test_yaml_parse_error(self):
        """Make sure Yaml parse errors are handled reasonably."""

        for suite_name in (
                'missing_key_same',
                'missing_key_above',
                'missing_key_below',
                'missing_key_collect',
                'invalid_yaml',
                ):

            try:
                self.resolver.load([suite_name])
            except TestConfigError as err:
                # Make sure the error can be formatted.
                err.pformat()

    def test_incremental_load(self):
        """Check that incremental loading is both incremental and loading."""

        # Incremental loading allows us to break up the resolution of tests
        # so they get their scheduler information last minute. It's not perfect -
        # permutations can span multiple load sets.
        # The dummy scheduler counts the mumber of times we've reset it, and we add
        # that to the test name to check that the tests actually got new sched info.
        requests = []
        answers = []
        # 14 copies of the same basic test.
        requests += ['incremental.simple']*14
        answers.append(['simple.1']*7)
        answers.append(['simple.2']*7)
        # A permuted test that's fits exactly in the batch size
        requests += ['incremental.permuted_exact']
        answers.append(['permuted_exact.3']*7)
        # A bunch of separate requests for a permuted test that's smaller than batch size
        requests += ['incremental.permuted_odd']*6
        answers.append(['permuted_odd.4']*7)
        answers.append(['permuted_odd.4']*2 + ['permuted_odd.5']*5)
        # A permuted test too big for the batch size
        requests += ['incremental.permuted_big', 'incremental.permuted_odd']
        answers.append(['permuted_odd.5'] + ['permuted_odd.6']*3 + ['permuted_big.6']*3)
        answers.append(['permuted_big.6']*7)
        # A multiplied test, plus testing the remainders.
        requests += ['5*incremental.permuted_odd']
        answers.append(['permuted_odd.8']*7)
        answers.append(['permuted_odd.8']*2 + ['permuted_odd.9']*5)
        answers.append(['permuted_odd.9'] + ['permuted_odd.10']*3)
        answers.reverse()

        for tests in self.resolver.load_iter(requests, batch_size=7,
                                             overrides=['scheduler=dummy']):


            # Reset scheduler plugins
            # The test set will do this for us, but we have to here.
            for sched_name in schedulers.list_plugins():
                sched = schedulers.get_plugin(sched_name)
                sched.refresh()

            answer = answers.pop()

            result = ['{}.{}'.format(test.config['name'], test.var_man['sched.refresh_count'])
                      for test in tests]
            # The actual orders will be random because of multiprocessing
            answer.sort()
            result.sort()
            self.assertEqual(result, answer)
            self.assertEqual(self.resolver.errors, [])
