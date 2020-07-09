import inspect
import re

from pavilion import plugins
from pavilion import schedulers
from pavilion.test_config import variables
from pavilion.unittest import PavTestCase


class SchedTests(PavTestCase):
    """Assorted tests to apply across all scheduler plugins."""

    def setUp(self):

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_check_examples(self):
        """Make sure scheduler examples are up-to-date."""

        test = self._quick_test()

        scheds = schedulers.list_plugins()
        for sched_name in scheds:
            sched = schedulers.get_plugin(sched_name)
            sched_vars = sched.VAR_CLASS(sched, test.config[sched_name])

            for key in sched_vars.keys():
                module_path = inspect.getmodule(sched).__file__
                example = sched_vars.info(key)['example']
                self.assertNotEqual(example, sched_vars.NO_EXAMPLE,
                    msg="The sched variable examples for scheduler {} at "
                        "({}) are missing key {}."
                        .format(sched_name, module_path, key))

    def test_sched_vars(self):
        """Make sure the scheduler variable class works as expected."""

        class TestVars(schedulers.SchedulerVariables):

            @schedulers.var_method
            def hello(self):
                return 'hello'

            @schedulers.var_method
            def foo(self):
                return self.sched_data['foo']

            @schedulers.dfr_var_method()
            def bar(self):
                return 'bar'

            def not_a_key(self):
                pass

        class DummySched(schedulers.SchedulerPlugin):
            VAR_CLASS = TestVars

            def __init__(self):
                super().__init__('dummy', 'more dumb')

                self.in_alloc_var = False

            def _get_data(self):
                return {
                    'foo': 'baz'
                }

            def available(self):
                return True

            def _in_alloc(self):
                return self.in_alloc_var

        config = {
                     'name':      'sched-vars',
                     'scheduler': 'dummy'
                 }

        test = self._quick_test(config)

        dummy_sched = DummySched()

        svars = dummy_sched.get_vars(test)

        # There should only be three keys.
        self.assertEqual(svars['hello'], 'hello')
        self.assertEqual(svars['foo'], 'baz')
        # Make sure we get a deferred variable when outside of an allocation
        self.assert_(isinstance(svars['bar'], variables.DeferredVariable))
        # And the real thing inside
        dummy_sched.in_alloc_var = True
        del svars['bar']
        self.assertEqual(svars['bar'], 'bar')

    def test_kickoff_env(self):

        pav_cfg = self.pav_cfg
        pav_cfg['env_setup'] = ['test1', 'test2', 'test3']

        config = {
                     'name':      'sched-vars',
                     'scheduler': 'dummy'
                 }
        test = self._quick_test(config)

        dummy_sched = schedulers.get_plugin('dummy')
        path = dummy_sched._create_kickoff_script(pav_cfg, test)
        with path.open() as file:
            lines = file.readlines()
        for i in range(0,len(lines)):
            lines[i] = lines[i].strip()
        testlist = pav_cfg['env_setup']
        self.assertTrue(set(testlist).issubset(lines))
        self.assertTrue(re.match(r'pav _run.*', lines[-1]))
