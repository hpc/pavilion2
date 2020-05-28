from pavilion import plugins
from pavilion import schedulers
from pavilion.unittest import PavTestCase
import inspect


class SchedTests(PavTestCase):
    """Assorted tests to apply across all scheduler plugins."""

    def setUp(self):

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_check_examples(self):
        """Make sure scheduler examples are up-to-date."""

        scheds = schedulers.list_plugins()
        for sched_name in scheds:
            sched = schedulers.get_plugin(sched_name)
            sched_vars = sched.VAR_CLASS(sched, {})

            for key in sched_vars.keys():
                module_path = inspect.getmodule(sched).__file__
                self.assertIn(
                    key, sched_vars.EXAMPLE,
                    msg="The sched variable examples for scheduler {} at "
                        "({}) are missing key {}."
                        .format(sched_name, module_path, key))
