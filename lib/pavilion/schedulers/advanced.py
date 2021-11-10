"""The advanced scheduler base class. Enables cluster chunking, node selection
algorithms, and other advanced features."""

import collections
import math
import pickle
import pprint
from abc import ABC
from typing import Tuple, List, Any, Union, Dict, FrozenSet, NewType

from pavilion.jobs import Job, JobInfo, JobError
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from .config import validate_config, AVAILABLE, BACKFILL
from .scheduler import SchedulerPlugin, SchedulerPluginError
from .types import NodeInfo, NodeList, NodeSet, Nodes
from .vars import SchedulerVariables

ChunksBySelect = NewType('ChunksBySelect', Dict[str, List[NodeList]])
ChunksByChunkSize = NewType('ChunksByChunkSize', Dict[int, ChunksBySelect])
ChunksByNodeListId = NewType('ChunksByNodeListId', Dict[int, ChunksByChunkSize])

class SchedulerPluginAdvanced(SchedulerPlugin, ABC):
    """A scheduler plugin that supports automatic node inventories, and as a
    consequence chunking and other advanced features."""

    def __init__(self, name, description, priority=SchedulerPlugin.PRIO_COMMON):
        """Initialize tracking of node info and chunks, in addition to the basics."""

        super().__init__(name, description, priority=priority)

        self._nodes = None  # type: Union[Nodes, None]
        self._node_lists = []  # type: List[NodeList]
        self._chunks = ChunksByNodeListId({})  # type: ChunksByNodeListId

    # These additional methods need to be defined for advanced schedulers.

    def _get_raw_node_data(self, sched_config) -> Tuple[List[Any], Any]:
        """Get the raw data for the nodes on the current cluster/host.

        :returns: A list of raw data for each node (to be processed by
            _transform_raw_node_data, and an object (of any type) of data that applies
            to every node."""

        raise NotImplementedError("This must be implemented by the scheduler plugin.")

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Transform the raw node data into a node info dictionary. Not all keys are
        required, but you must provide enough information to filter out nodes that
        can't be used or to differentiate nodes that can't be used together. You may
        return additional keys, typically to use with scheduler specific filter
        parameters.

        Base supported keys:
        # Node Name (required)

        - name - The name of the node (from the scheduler's perspective)

        # Node Status - (required)

        - up (bool) - Whether the node is up (allocatable).
        - available (bool) - Whether the node is allocatable and unallocated.

        # Informational

        - cpus - The number of CPUs on the node.
        - mem - The node memory in GB

        # Partitions - this information is used to separate nodes into groups that
        #   can be allocated together. If this information is lacking, Pavilion will
        #   attempt to create allocations that aren't possible on a system, such as
        #   across partitions.

        - partitions (List) - The cluster partitions on which the node resides.
        - reservations (List) - List of reservations to which the node belongs.
        - features (List[str]) - A list of feature tags that differentiate nodes,
                typically on heterogeneous systems."""

        raise NotImplementedError("This must be implemented by the scheduler plugin.")

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict,
                 chunk: NodeList) -> JobInfo:
        """Schedule the test under this scheduler.

        :param pav_cfg: The pavilion config.
        :param job: The job to kick off.
        :param sched_config: The scheduler configuration for this test or group of
            tests.
        :param chunk: List of nodes on which to start this test.
        :returns: The job info of the kicked off job.
        """

        raise NotImplementedError("How to perform test kickoff is left for the "
                                  "specific scheduler to specify.")

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get initial variables (and chunks) for this scheduler."""

        self._nodes = self._get_system_inventory(sched_config)
        filtered_nodes, filter_reasons = self._filter_nodes(sched_config)
        filtered_nodes.sort()

        if sched_config['include_nodes']:
            for node in sched_config['include_nodes']:
                if node not in filtered_nodes:
                    raise SchedulerPluginError(
                        "Requested node (via 'schedule.include_nodes') was filtered "
                        "due to other filtering "
                    )

        if not filtered_nodes:
            reasons = "\n".join("{}: {}".format(k, v)
                                for k, v in filter_reasons.items())
            raise SchedulerPluginError(
                "All nodes were filtered out during the node filtering step. "
                "Nodes were filtered for the following reasons:\n{}\n"
                "Scheduler config:\n{}\n"
                .format(reasons, pprint.pformat(sched_config)))

        try:
            node_list_id = self._node_lists.index(filtered_nodes)
        except ValueError:
            node_list_id = len(self._node_lists)
            self._node_lists.append(filtered_nodes)

        chunks = self._get_chunks(node_list_id, sched_config)

        return self.VAR_CLASS(sched_config, nodes=self._nodes, chunks=chunks,
                              node_list_id=node_list_id)

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Load our saved node data from kickoff time, and compute the final
        scheduler variables from that."""

        nodes = self._load_sched_data(test)
        sched_config = validate_config(test.config['schedule'])

        return self.VAR_CLASS(sched_config, nodes=nodes, deferred=False)

    def _save_sched_data(self, test: TestRun, nodes: NodeSet):
        """Save node information (from kickoff time) for the given test. The saved
        node info is limited to only those nodes on which the test should run, which
        will be a subset of the chunk nodes. If those nodes can't be determined at
        kickoff time, `None` is saved."""

        test_nodes = {node: self._nodes[node] for node in nodes}
        try:
            with (test.path/self.SCHED_DATA_FN).open('wb') as data_file:
                pickle.dump(test_nodes, data_file)
        except OSError as err:
            raise SchedulerPluginError(
                "Could not save test scheduler data: {}".format(err))

    def _load_sched_data(self, test: TestRun) -> Nodes:
        """Load the scheduler data that was saved from the kickoff time."""

        try:
            with (test.path/self.SCHED_DATA_FN).open('rb') as data_file:
                return pickle.load(data_file)
        except OSError as err:
            raise SchedulerPluginError(
                "Could not load test scheduler data: {}".format(err))

    def _get_system_inventory(self, sched_config: dict) -> Union[Nodes, None]:
        """Returns a dictionary of node data, or None if the scheduler does not
        support node data acquisition."""

        raw_node_data, extra = self._get_raw_node_data(sched_config)
        if raw_node_data is None:
            return None

        nodes = Nodes({})

        for raw_node in raw_node_data:
            node_info = self._transform_raw_node_data(sched_config, raw_node,
                                                      extra)

            if 'name' not in node_info:
                raise RuntimeError("Advanced schedulers must always return a node"
                                   "'name' key when transforming raw node data."
                                   "Got: {}".format(node_info))

            nodes[node_info['name']] = node_info

        return nodes

    def _filter_nodes(self, sched_config: Dict[str, Any]) \
            -> Tuple[NodeList, Dict[str, List[str]]]:
        """
        Filter the system nodes down to just those we can use. This
        should check to make sure the nodes available are compatible with
        the test. The arguments for this function will vary by scheduler.

        :returns: A list of compatible node names.
        :rtype: list
        """

        nodes = self._nodes

        out_nodes = NodeList([])

        partition = sched_config.get('partition')
        reservation = sched_config.get('reservation')
        exclude_nodes = sched_config['exclude_nodes']
        node_state = sched_config['node_state']

        filter_reasons = collections.defaultdict(lambda: [])

        for node_name, node in nodes.items():
            if not node.get('up'):
                filter_reasons['not up'].append(node_name)
                continue

            if node_state == AVAILABLE and not node.get('available'):
                filter_reasons['not available'].append(node_name)
                continue

            if (partition is not None
                    and 'partitions' in node
                    and partition not in node['partitions']):
                filter_reasons['partition'].append(node_name)
                continue

            if (reservation is not None
                    and 'reservations' in node
                    and reservation not in node['reservations']):
                filter_reasons['reservation'].append(node)
                continue

            if node_name in exclude_nodes:
                filter_reasons['excluded'].append(node)
                continue

            # Filter according to scheduler plugin specific options.
            if not self._filter_custom(sched_config, node_name, node):
                filter_reasons[self.name].append(node)
                continue

            out_nodes.append(node_name)

        return out_nodes, filter_reasons

    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> bool:
        """Apply scheduler specific filters to the node list. Returns True
        if the node should be included."""

        _ = self, sched_config, node_name, node

        return True

    def _get_chunks(self, node_list_id, sched_config) -> List[NodeSet]:
        """Chunking is specific to the node list, chunk size, and node selection
        settings of a job. The actual chunk used by a test_run won't be known until
        after the test is at least partially resolved, however. Until then, it only
        knows what chunks are available.

        This method retrieves or creates a list of ChunkInfo objects, and returns
        it."""

        nodes = list(self._node_lists[node_list_id])

        chunk_size = sched_config['chunking']['size']
        # Chunk size 0/null is all the nodes.
        if chunk_size in (0, None) or chunk_size > len(nodes):
            chunk_size = len(nodes)
        chunk_extra = sched_config['chunking']['extra']
        node_select = sched_config['chunking']['node_selection']

        chunk_id = (node_list_id, chunk_size, node_select, chunk_extra)
        # If we already have chunks for our node list and settings, just return what
        # we've got.
        if chunk_id in self._chunks:
            return self._chunks[chunk_id]

        chunks = []
        for i in range(len(nodes)//chunk_size):
            # Apply the selection function and get our chunk nodes.
            chunk = self.NODE_SELECTION[node_select](nodes, chunk_size)
            # Filter out any chosen from our node list.
            nodes = [node for node in nodes if node not in chunk]
            chunks.append(chunk)

        if nodes and chunk_extra == BACKFILL:
            backfill = chunks[-1][:chunk_size - len(nodes)]
            chunks.append(backfill + nodes)

        chunk_info = []
        for chunk in chunks:
            chunk_info.append(NodeSet(frozenset(chunk)))

        self._chunks[chunk_id] = chunk_info

        return chunk_info

    def schedule_tests(self, pav_cfg, tests: List[TestRun]):
        """Schedule each of the given tests using this scheduler using a
        separate allocation (if applicable) for each.

        :param pav_cfg: The pavilion config
        :param [pavilion.test_run.TestRun] tests: A list of pavilion tests
            to schedule.
        """

        # type: Dict[FrozenSet[str], List[TestRun]]
        by_chunk = collections.defaultdict(lambda: [])
        usage = collections.defaultdict(lambda: 0)  # type: Dict[FrozenSet[str], int]
        sched_configs = {}  # type: Dict[str, dict]

        for test in tests:
            node_list_id = int(test.var_man.get('sched.node_list_id'))

            sched_config = validate_config(test.config['schedule'])
            sched_configs[test.full_id] = sched_config
            chunk_spec = test.config.get('chunk')
            if chunk_spec != 'any':
                # This is validated in test object creation.
                chunk_spec = int(chunk_spec)

            chunk_size = sched_config['chunking']['size']
            node_select = sched_config['chunking']['node_selection']
            chunk_extra = sched_config['chunking']['extra']

            node_list = self._node_lists[node_list_id]
            if chunk_size in (None, 0) or len(node_list):
                chunk_size = len(node_list)

            chunk_id = (node_list_id, chunk_size, node_select, chunk_extra)

            chunks = self._chunks[chunk_id]

            if chunk_spec == 'any':
                least_used = None
                least_used_chunk = None
                for chunk in chunks:
                    chunk_usage = usage[chunk]
                    if chunk_usage == 0:
                        least_used_chunk = chunk
                        break
                    elif least_used is None or chunk_usage < least_used:
                        least_used = chunk_usage
                        least_used_chunk = chunk

                usage[least_used_chunk] += 1
                by_chunk[least_used_chunk].append(test)
            else:
                if chunk_spec > len(chunks):
                    raise SchedulerPluginError(
                        "Test selected chunk '{}', but there are only {} chunks "
                        "available.".format(chunk_id, len(chunks)))
                chunk = chunks[chunk_id]
                usage[chunk] += 1
                by_chunk[chunk].append(test)

        for chunk, tests in by_chunk.items():
            self._schedule_chunk(pav_cfg, chunk, tests, sched_configs)

    # Scheduling options in this list are denoted as those that change the nature
    # of the allocation being acquired. Tests with different values for these
    # should thus run under different allocations.
    # This can be modified by subclasses. Separate multipart keys with a '.'.
    ALLOC_ACQUIRE_OPTIONS = ['partition', 'reservation', 'account', 'qos']

    def _schedule_chunk(self, pav_cfg, chunk: NodeSet, tests: List[TestRun],
                        sched_configs: Dict[str, dict]):

        # Group tests according to their allocation options. Mostly tests should
        # fall into two groups, tests that don't allow allocation sharing and
        # tests with all the same options. There's a chance for multiple groups though.
        # The 'None' share group is for tests that never share an allocation.
        share_groups = collections.defaultdict(list)

        for test in tests:
            sched_config = sched_configs[test.full_id]
            if not sched_config['share_allocation']:
                # This test will be allocated separately.
                acq_opts = None
            else:
                acq_opts = []
                for opt_name in self.ALLOC_ACQUIRE_OPTIONS:
                    opt = sched_config
                    for part in opt_name.split('.'):
                        if opt is not None and isinstance(opt, dict):
                            opt = opt.get(part)
                    # Make the option hashable if its a list.
                    if isinstance(opt, list):
                        opt = tuple(opt)
                    acq_opts.append(opt)

                acq_opts = tuple(acq_opts)

            share_groups[acq_opts].append(test)

        for acq_opts, tests in share_groups.items():
            if acq_opts is None:
                self._schedule_indi_chunk(pav_cfg, tests, sched_configs, chunk)
            else:
                self._schedule_shared_chunk(pav_cfg, tests, sched_configs, chunk)

    def _schedule_shared_chunk(self, pav_cfg, tests: List[TestRun],
                               sched_configs: Dict[str, dict], chunk: NodeSet):
        """Scheduler tests in a shared chunk."""

        try:
            job = Job.new(pav_cfg, tests, self.KICKOFF_FN)
        except JobError as err:
            raise SchedulerPluginError("Error creating job: \n{}".format(err))

        # At this point the scheduler config should be effectively identical
        # for the test being allocated.
        base_test = tests[0]
        base_sched_config = sched_configs[base_test.full_id].copy()
        # Get the longest time limit for all the tests.
        base_sched_config['time_limit'] = max(conf['time_limit'] for conf in
                                              sched_configs.values())

        # The set of nodes for a given test.
        test_nodes = {}

        node_list = list(chunk)
        node_list.sort()

        # The number of nodes needed for our shared allocation. Basically, the most
        # nodes needed out of all the tests that are to run.
        shared_nodes = 1
        for test in tests:
            sched_config = sched_configs[test.full_id]
            needed_nodes = sched_config['nodes']
            if isinstance(needed_nodes, float):
                needed_nodes = math.ceil(len(chunk) * needed_nodes)

            # Cap the number of nodes at the number in the actual chunk.
            if needed_nodes > len(chunk):
                test.status.set(STATES.SCHED_WARNING,
                                "Requested {} nodes, but only {} were available in the "
                                "chunk.".format(needed_nodes, len(chunk)))
                needed_nodes = len(chunk)

            test_nodes[test.full_id] = NodeSet(frozenset(node_list[:needed_nodes]))

            shared_nodes = max(needed_nodes, shared_nodes)

        # Reduce the effective chunk size to the most needed for any specific test.
        if chunk:
            chunk = NodeList(list(chunk)[:shared_nodes])

        job_name = 'pav {}'.format(','.join(test.name for test in tests[:4]))
        if len(tests) > 4:
            job_name.append(' ...')
        script = self._create_kickoff_script_stub(pav_cfg, job_name, job.kickoff_log,
                                                  base_sched_config, chunk)

        for test in tests:
            # Run each test via pavilion
            script.command('echo "Starting test {t.id} - $(date)"'.format(t=test))
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.command('echo "Finished test {t.id} - $(date)"'.format(t=test))
            script.newline()

            # Save the list of nodes that each test is to run on within the allocation
            self._save_sched_data(test, test_nodes[test.full_id])

        script.write(job.kickoff_path)

        # Create symlinks for each test to the one test with the kickoff script and
        # log.
        for test in tests:
            test.job = job

        job.info = self._kickoff(pav_cfg, job, base_sched_config, chunk)

        for test in tests:
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off by {} scheduler in a shared allocation with {} other "
                "tests and {} nodes.".format(self.name, len(tests), len(chunk)))

    def _schedule_indi_chunk(self, pav_cfg, tests: List[TestRun],
                             sched_configs: Dict[str, dict], chunk: NodeSet):
        """Schedule tests individually under the given chunk."""

        # Track which nodes are available for individual runs. We'll consume nodes
        # from this list as they're handed out to tests, and reset it when
        # a test needs more nodes than it has.
        chunk_usage = list(chunk)
        chunk_usage.sort()

        by_need = []

        # Figure out how many nodes each test needs and sort them least
        for test in tests:
            sched_config = sched_configs[test.full_id]

            needed_nodes = sched_config['nodes']
            if isinstance(needed_nodes, float):
                needed_nodes = math.ceil(needed_nodes * len(chunk))
            needed_nodes = min(needed_nodes, len(chunk))

            by_need.append((needed_nodes, test))
        by_need.sort()

        for needed_nodes, test in by_need:
            try:
                job = Job.new(pav_cfg, tests, self.KICKOFF_FN)
            except JobError as err:
                raise SchedulerPluginError("Error creating job: \n{}".format(err))

            sched_config = sched_configs[test.full_id]
            if chunk is not None:
                if needed_nodes > len(chunk_usage):
                    chunk_usage = list(chunk)
                    chunk_usage.sort()

                test_chunk = chunk_usage[:needed_nodes]
                chunk_usage = chunk_usage[needed_nodes:]
            else:
                test_chunk = chunk

            # Save node information for use on the scheduled job.
            self._save_sched_data(test, test_chunk)

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav {}'.format(test.name),
                log_path=job.kickoff_log,
                sched_config=sched_config,
                chunk=test_chunk)

            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(job.kickoff_path)

            job.info = self._kickoff(pav_cfg, job, sched_config, test_chunk)
            test.job = job
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually) under {} scheduler with {} nodes."
                .format(self.name, len(test_chunk)))
