from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion.test_config import variables
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase
from pavilion.test_config import VariableSetManager
import re

class RawSchedTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Do a default pav config, which will load from
        # the pavilion lib path.
        self.pav_config = config.PavilionConfigLoader().load_empty()
        self.pav_config.config_dirs = [self.TEST_DATA_ROOT/'pav_config_dir']

    def setUp(self):

        plugins.initialize_plugins(self.pav_config)

    def tearDown(self):

        plugins._reset_plugins()

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

            def _in_alloc(self):
                return self.in_alloc_var

        test = TestRun(
            self.pav_cfg,
            {
                'name': 'sched-vars',
                'scheduler': 'dummy'
            },
            VariableSetManager(),
        )

        dummy_sched = DummySched()

        svars = dummy_sched.get_vars(test)

        # There should only be three keys.
        self.assertEqual(len(list(svars.keys())), 3)
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

        test = TestRun(
            self.pav_cfg,
            {
                'name': 'sched-vars',
                'scheduler': 'dummy'
            },
            VariableSetManager(),
        )

        dummy_sched = schedulers.get_scheduler_plugin('dummy')
        path = dummy_sched._create_kickoff_script(pav_cfg, test)
        with path.open() as file:
            lines = file.readlines()
        for i in range(0,len(lines)):
            lines[i] = lines[i].strip()
        testlist = pav_cfg['env_setup']
        self.assertTrue(set(testlist).issubset(lines))
        self.assertTrue(re.match(r'pav _run.*', lines[-1]))



