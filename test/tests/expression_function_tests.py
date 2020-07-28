from pavilion import expression_functions
from pavilion import plugins
from pavilion.unittest import PavTestCase


class ExprFuncTests(PavTestCase):
    """Check each of the expression functions."""

    def setUp(self) -> None:

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self) -> None:

        plugins._reset_plugins()

    def test_core_functions(self):
        """Check core expression functions."""

        # Every core function must have at lest one test.
        # Each test is a list of (args, answer). An answer of None isn't
        # checked.
        tests = {
            'int': [(("1234", 8), 668)],
            'round': [((1.234,), 1)],
            'floor': [((1.234,), 1)],
            'ceil': [((1.234,), 2)],
            'sum': [(([1, 2, 3, 4.5],), 10.5),
                    (([1, 2, 3, 4],), 10)],
            'avg': [(([1, 2, 3, 4.5],), 2.625),
                    (([1, 2, 3, 4, 5],), 3.0)],
            'len': [(([1, 2, "foo"],), 3)],
            'random': [(tuple(), None)],
            'keys': [(({'a': 1, 'b': 2},), ['a', 'b']),
                     (({'b': 1, 'a': 2},), ['a', 'b'])],
            'all': [(([True, 1, 2],), True),
                    (([True, 0, 3],), False)],
            'any': [(([False, 1, 0],), True),
                    (([False, 0],), False)],
            're_search': [((r'hello (\w+)', 'hello world'), 'world'),
                          ((r'\d+', 'apples, 14, bananas'), '14')],
            'replace': [(('I am a banana! ', ' ', '_'), 'I_am_a_banana!_')],
            'outliers': [(([1, 2, 3, 4, 5, 6, 7, 99, 108],
                           ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'],
                           1.5),
                          {'h': 1.7581382586345833, 'i': 1.9752254521550119})]
        }

        exp_funcs = expression_functions.list_plugins()

        for func_name in exp_funcs:
            func = expression_functions.get_plugin(func_name)

            # Only check core functions
            if not func.core:
                continue

            self.assertIn(func_name, tests,
                          msg='You must provide tests for all core expression '
                              'functions.')
            if func_name not in tests or len(tests[func_name]) == 0:
                self.fail(msg='You must provide at least one test for each '
                              'core expression function. Missing {}'
                              .format(func_name))

            for args, answer in tests[func_name]:
                result = func(*args)
                if answer is None:
                    continue

                self.assertEqual(result, answer)
                self.assertEqual(type(result), type(answer))
