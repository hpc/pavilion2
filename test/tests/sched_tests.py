import copy
import inspect

import pavilion.schedulers
from pavilion import output
from pavilion import plugins
from pavilion import schedulers
from pavilion.schedulers import SchedulerPluginAdvanced
from pavilion.schedulers import config as sconfig
from pavilion.schedulers.types import NodeSet, Nodes, NodeInfo
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

        nodes = Nodes({})
        for i in range(10):
            nodes['node{:02d}'.format(i)] = NodeInfo({})

        chunks = [NodeSet(frozenset(['node01', 'node02', 'node03']))]

        # Check with populated nodes and chunks.
        self._check_examples(test.config['schedule'], nodes, chunks)

        # Check with empty nodes and chunks.
        self._check_examples(test.config['schedule'], Nodes({}), [])

    def _check_examples(self, config, nodes, chunks):
        """Check examples with the given parameters."""

        scheds = pavilion.schedulers.list_plugins()
        for sched_name in scheds:
            sched = pavilion.schedulers.get_plugin(sched_name)
            sched_vars = sched.VAR_CLASS(
                config,
                nodes=nodes,
                chunks=chunks,
                node_list_id=3
            )

            for key in sched_vars.keys():
                module_path = inspect.getmodule(sched).__file__
                example = sched_vars.info(key)['example']
                self.assertNotEqual(
                    example, sched_vars.NO_EXAMPLE,
                    msg="The sched variable examples for scheduler {} at "
                        "({}) are missing key {}."
                        .format(sched_name, module_path, key))

    def test_sched_var_values(self):
        test = self._quick_test()

        nodes = Nodes({})
        for i in range(10):
            nodes['node{:02d}'.format(i)] = NodeInfo({
                'cpus': i+5,
                'mem': (i+10),
            })

        config = schedulers.validate_config(test.config['schedule'])

        chunks = [NodeSet(frozenset(['node01', 'node02', 'node03'])),
                  NodeSet(frozenset(['node05', 'node06', 'node07']))]

        expected = {
            'test_cmd': '',
            'tasks_per_node': '1',
            'chunk_ids': ['0', '1'],
            'node_list_id': '5',
            'min_cpus': '5',
            'min_mem': '10',
            'nodes': str(len(nodes)),
            'node_list': [str(key) for key in nodes.keys()],
            'test_nodes': str(len(nodes)),
            'test_node_list': [str(key) for key in nodes.keys()],
            'test_min_cpus': '5',
            'test_min_mem': '10',
            'tasks_total': str(len(nodes)),
        }

        sched_vars = schedulers.SchedulerVariables(
            config,
            nodes=nodes,
            chunks=chunks,
            node_list_id=5,
            deferred=False,
        )

        for key in sched_vars.keys():
            val = sched_vars[key]
            self.assertEqual(val, expected[key],
                             msg="Unexpected value for sched var '{}'.\n"
                                 "Got {}, expected {}"
                             .format(key, repr(val), repr(expected[key])))

    def test_sched_var_values_basic(self):
        """Test scheduler vars under the assumptions of the basic schedulers -
        that we know nothing about the nodes."""

        test_cfg = self._quick_test_cfg()
        test_cfg['schedule']['cluster_info'] = {
            'node_count': '50',
            'mem': str(8*1024**3),
            'cpus': '4',
        }

        test = self._quick_test(test_cfg)

        nodes = Nodes({})
        config = schedulers.validate_config(test.config['schedule'])
        chunks = None

        expected = {
            'test_cmd': '',
            'tasks_per_node': '1',
            'chunk_ids': [],
            'node_list_id': '5',
            'min_cpus': '4',
            'min_mem': str(8*1024**3),
            'nodes': '50',
            'node_list': [],
            'test_nodes': '0',
            'test_node_list': [],
            'test_min_cpus': '4',
            'test_min_mem': str(8*1024**3),
            'tasks_total': str(len(nodes)),
        }

        sched_vars = schedulers.SchedulerVariables(
            config,
            nodes=nodes,
            chunks=chunks,
            node_list_id=5,
            deferred=False,
        )

        for key in sched_vars.keys():
            val = sched_vars[key]
            self.assertEqual(val, expected[key],
                             msg="Unexpected value for sched var '{}'.\n"
                                 "Got {}, expected {}"
                             .format(key, repr(val), repr(expected[key])))

    def test_parse_node_range(self):
        """Test the node range parsing function."""

        good = {
            'node[0-5]a': ['node{}a'.format(i) for i in range(6)],
            'node0[0-5]a': ['node0{}a'.format(i) for i in range(6)],
            '[0-5]': ['{}'.format(i) for i in range(6)],
            'node[7-10]': ['node{:02d}'.format(i) for i in range(7, 11)],
            'node05': ['node05'],
        }

        bad = [
            'node[',
            'node]',
            'n[ode[]',
            'node[]]',
            'node[5]',
            'node[9-5]',
            'node[3--10]',
        ]

        for test_str, answer in good.items():
            nodes = schedulers.config.parse_node_range(test_str)
            self.assertEqual(nodes, answer)

        for test_str in bad:
            with self.assertRaises(ValueError):
                schedulers.config.parse_node_range(test_str)

    def test_node_filtering(self):
        """Test filtering via the dummy scheduler."""

        # The dummy scheduler returns info on 100 nodes.
        dummy = pavilion.schedulers.get_plugin('dummy')  # type: SchedulerPluginAdvanced

        # Check with defaults. Every 10th node is marked as not 'up', so this should
        # give 90 nodes.
        sched_vars = dummy.get_initial_vars({})
        node_list = dummy._node_lists[int(sched_vars.node_list_id())]
        self.assertEqual(len(node_list), 90)

        # 2/10ths of nodes aren't available.
        sched_vars = dummy.get_initial_vars({'node_state': 'available'})
        node_list = dummy._node_lists[int(sched_vars.node_list_id())]
        self.assertEqual(len(node_list), 80)

        # Every other node is in the baz partition.
        sched_vars = dummy.get_initial_vars({'partition': 'baz'})
        node_list = dummy._node_lists[int(sched_vars.node_list_id())]
        # All 'baz' nodes are up.
        self.assertEqual(len(node_list), 50)

        # The first 20 nodes (minus 2 down nodes) are in the 'rez1' reservation.
        sched_vars = dummy.get_initial_vars({'reservation': 'rez1'})
        node_list = dummy._node_lists[int(sched_vars.node_list_id())]
        self.assertEqual(len(node_list), 18)

        # Exclude nodes 10-19
        sched_vars = dummy.get_initial_vars({'exclude_nodes': [
            'node[9-20]', 'node05']})
        node_list = dummy._node_lists[int(sched_vars.node_list_id())]
        self.assertEqual(len(node_list), 79)

        with self.assertRaises(schedulers.SchedulerPluginError):
            dummy.get_initial_vars({'include_nodes': ['node00']})

    def test_chunking_size(self):
        """"""

        cfg = {
            'nodes': '50',
            'chunking': {
            }
        }

        dummy = pavilion.schedulers.get_plugin('dummy')  # type: SchedulerPluginAdvanced

        for size in None, 0, 15, 13, 1000:
            for extra in sconfig.NODE_EXTRA_OPTIONS:
                sched_config = copy.deepcopy(cfg)
                sched_config['chunking']['extra'] = extra
                if size is not None:
                    sched_config['chunking']['size'] = str(size)

                # Check basic contiguous chunking
                sched_vars = dummy.get_initial_vars(sched_config)
                node_list_id = int(sched_vars['node_list_id'])
                node_list = dummy._node_lists[node_list_id]
                if size in (0, None) or len(node_list) < size:
                    chunk_size = len(node_list)
                else:
                    chunk_size = size

                chunk_id = (node_list_id, chunk_size, 'contiguous', extra)
                chunks = dummy._chunks[chunk_id]
                for chunk in chunks:
                    self.assertEqual(len(chunk), chunk_size)

                # Make sure we have the right number of chunks too.
                num_chunks = len(node_list)//chunk_size
                if extra == sconfig.BACKFILL and len(node_list) % chunk_size:
                    num_chunks += 1
                self.assertEqual(len(chunks), num_chunks)

    def test_node_selection(self):
        """Make sure node selection works as expected."""

        chunk_size = 11
        cfg = {
            'chunking': {
                'size': str(chunk_size),
            }
        }

        # Make true to examine the node selection algorithm results.
        enable_view = False

        dummy = pavilion.schedulers.get_plugin('dummy')  # type: SchedulerPluginAdvanced

        for select in sconfig.NODE_SELECT_OPTIONS:
            sched_config = copy.deepcopy(cfg)
            sched_config['chunking']['node_selection'] = select

            # Exercise each node selection method.
            sched_vars = dummy.get_initial_vars(sched_config)
            node_list_id = int(sched_vars['node_list_id'])
            chunks = dummy._chunks[(node_list_id, chunk_size,
                                    select, sconfig.BACKFILL)]

            # This is here to debug node selection and visually examine the node
            # selection algorithm results, as they are mostly random.
            if enable_view:
                output.fprint(select, sorted(list(chunks[0])))

    def test_shared_kickoff(self):
        """Check that shared kickoffs work as expected."""

        base_test_cfg = self._quick_test_cfg()
        base_test_cfg['scheduler'] = 'dummy'

        tests = []
        for nodes in 1, 5, 20, 'all':
            test_cfg = copy.deepcopy(base_test_cfg)
            test_cfg['schedule'] = {
                'nodes': str(nodes),
                'share_allocation': 'True',
            }
            test = self._quick_test(test_cfg, finalize=False)
            tests.append(test)

        dummy = pavilion.schedulers.get_plugin('dummy')
        dummy.schedule_tests(self.pav_cfg, tests)

        # Make sure all the tests share a job.
        job1 = tests[0].job
        self.assertTrue(all([test.job == job1 for test in tests]))

        for test in tests:
            test.wait(10)

        for test in tests:
            self.assertEqual(test.results['result'], 'PASS')

    def test_kickoff_independent(self):
        """Check independent kickoff"""

        base_test_cfg = self._quick_test_cfg()
        base_test_cfg['scheduler'] = 'dummy'

        tests = []
        for nodes in 1, 5, 20, 'all':
            test_cfg = copy.deepcopy(base_test_cfg)
            test_cfg['schedule'] = {
                'nodes': str(nodes),
                'share_allocation': 'False',
            }
            test = self._quick_test(test_cfg, finalize=False)
            tests.append(test)

        dummy = pavilion.schedulers.get_plugin('dummy')
        dummy.schedule_tests(self.pav_cfg, tests)

        # Make sure each test has its own job.
        job1 = tests[0].job
        for test in tests[1:]:
            self.assertNotEqual(test.job, job1)

        for test in tests:
            try:
                test.wait(10)
            except TimeoutError:
                with open(test.path/'run.log') as run_log:
                    self.fail(msg=run_log.read()) 

        for test in tests:
            self.assertEqual(test.results['result'], 'PASS')
