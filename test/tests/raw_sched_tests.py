import pavilion.schedulers
from pavilion.unittest import PavTestCase
from pavilion.deferred import DeferredVariable


class RawSchedTests(PavTestCase):

    def test_sched_vars(self):
        """Make sure the scheduler variable class works as expected."""

        non_deferred = {}

        expected = {
            'requested_nodes': '',
            'tasks_total': None,
            'account': '',
            'test_node_list': None,
            'test_min_mem': None,
            'test_nodes': None,
            'nodes': '1',
            'srun_args': None,
            'test_min_cpus': None,
            'errors': [],
            'qos': 'fake-qos',
            'chunk_size': '',
            'node_list_id': '',
            'partition': 'fake-partition',
            'concurrent_default': '100',
            'test_cmd': '',
            'tasks_per_node': None,
            'min_mem': '1000',
            'chunk_ids': [],
            'node_list': [],
            'min_cpus': '4',
            'reservation': '',
            }

        test_cfg = self._quick_test_cfg()
        test_cfg['schedule'] = {
            'qos': 'fake-qos',
            'partition': 'fake-partition',
            'nodes': '3'
            }
        test = self._quick_test(test_cfg)

        raw_sched = pavilion.schedulers.get_plugin('raw')

        vars = raw_sched.get_initial_vars(test.config['schedule'])

        for key in vars.keys():
            self.assertIn(key, expected, msg=f"Raw sched var '{key}' does not have a testable value.")
            val = vars[key]
            exp_val = expected[key]
            if exp_val is None and isinstance(val, DeferredVariable):
                continue
            self.assertEqual(val, exp_val,
                msg=f"Raw sched var '{key}' does not match expected value: '{val}' != '{exp_val}'")

        # Get these and check them.
        fvars = raw_sched.get_final_vars()
