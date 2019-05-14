from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion.test_config import variables
from pavilion.pav_test import PavTest
from pavilion.unittest import PavTestCase


class RawSchedTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Do a default pav config, which will load from
        # the pavilion lib path.
        self.pav_config = config.PavilionConfigLoader().load_empty()

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

        test = PavTest(
            self.pav_cfg,
            {
                'name': 'sched-vars',
                'scheduler': 'dummy'
            },
            {}
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
