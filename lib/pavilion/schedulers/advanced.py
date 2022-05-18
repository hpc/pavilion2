"""The advanced scheduler base class. Enables cluster chunking, node selection
algorithms, and other advanced features."""

import collections
import pprint
from abc import ABC
from typing import Tuple, List, Any, Union, Dict, FrozenSet, NewType

from pavilion.jobs import Job, JobError
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from pavilion.types import NodeInfo, Nodes, NodeList, NodeSet, NodeRange
from .config import validate_config, AVAILABLE, BACKFILL
from .scheduler import SchedulerPlugin, SchedulerPluginError
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

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get initial variables (and chunks) for this scheduler."""

        if self._nodes is None:
            self._nodes = self._get_system_inventory(sched_config)
        filtered_nodes, filter_reasons = self._filter_nodes(sched_config)
        filtered_nodes.sort()

        errors = []

        if sched_config['include_nodes']:
            for node in sched_config['include_nodes']:
                if node not in filtered_nodes:
                    errors.append(
                        "Requested node (via 'schedule.include_nodes') was filtered "
                        "due to other filtering ")

        min_nodes, max_nodes = self._calc_node_range(sched_config, len(filtered_nodes))
        if min_nodes > max_nodes:
            errors.append(
                "Requested between {}-{} nodes, but the minimum is more than the maximum "
                "node count"
                .format(min_nodes, max_nodes))

        if len(filtered_nodes) < min_nodes:
            reasons = []
            for reason, reas_nodes in filter_reasons.items():
                if len(reas_nodes) > 10:
                    reas_node_list = ','.join(reas_nodes[:10]) + ', ...'
                else:
                    reas_node_list = ','.join(reas_nodes)
                reasons.append("({}) {:30s} {}"
                               .format(len(reas_nodes), reason, reas_node_list))

            reasons = "\n".join(reasons)

            errors.append(
                "Insufficient nodes. Asked for {}-{} nodes, but only {} were "
                "left after filtering. Nodes for filtered for the following reasons:\n{}\n"
                "Scheduler config:\n{}\n"
                .format(min_nodes, max_nodes, len(filtered_nodes),
                        reasons, pprint.pformat(sched_config)))

        try:
            node_list_id = self._node_lists.index(filtered_nodes)
        except ValueError:
            node_list_id = len(self._node_lists)
            self._node_lists.append(filtered_nodes)

        chunks = self._get_chunks(node_list_id, sched_config)

        sched_vars = self.VAR_CLASS(sched_config, nodes=self._nodes, chunks=chunks,
                                    node_list_id=node_list_id)
        sched_vars.add_errors(errors)
        return sched_vars

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Load our saved node data from kickoff time, and compute the final
        scheduler variables from that."""

        try:
            nodes = test.job.load_sched_data()
        except JobError as err:
            raise SchedulerPluginError("Could not load node info: {}".format(err.args[0]))

        # Get the list of allocation nodes
        alloc_nodes = self._get_alloc_nodes(test.job)
        nodes = Nodes({node: nodes[node] for node in alloc_nodes})

        sched_config = validate_config(test.config['schedule'])

        return self.VAR_CLASS(sched_config, nodes=nodes, deferred=False)

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
                reason_key = "partition '{}' not in {}".format(partition, node['partitions'])
                filter_reasons[reason_key].append(node_name)
                continue

            if 'reservations' in node:
                if (reservation is not None
                        and reservation not in node['reservations']):
                    reason_key = "reservation '{}' not in {}"\
                                 .format(reservation, node['reservations'])
                    filter_reasons[reason_key].append(node_name)
                    continue

            if node_name in exclude_nodes:
                filter_reasons['excluded'].append(node_name)
                continue

            # Filter according to scheduler plugin specific options.
            custom_result = self._filter_custom(sched_config, node_name, node)
            if custom_result is not None:
                filter_reasons[custom_result].append(node_name)
                continue

            out_nodes.append(node_name)

        return out_nodes, filter_reasons

    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> Union[None, str]:
        """Apply scheduler specific filters to the node list. Returns a reason why the node
        should be filtered out, or None if it shouldn't be."""

        _ = self, sched_config, node_name, node

        return None

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

        # We can potentially have no nodes, in which case return an empty chunk.
        if chunk_size == 0:
            self._chunks[chunk_id] = [NodeSet(frozenset([]))]
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
            if chunk_size in (None, 0) or chunk_size > len(node_list):
                chunk_size = len(node_list)

            chunks_id = (node_list_id, chunk_size, node_select, chunk_extra)

            chunks = self._chunks[chunks_id]

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
                        "available.".format(chunk_spec, len(chunks)))
                chunk = chunks[chunk_spec]
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

        # There are three types of test launches.
        # 1. Tests that can share an allocation (
        share_groups = collections.defaultdict(list)
        flex_tests: List[TestRun] = []
        indi_tests: List[TestRun] = []

        for test in tests:
            sched_config = sched_configs[test.full_id]
            if not sched_config['share_allocation']:
                if sched_config['chunking']['size'] in (0, None):
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
            else:
                # Only share allocations if the number of nodes needed by the test is the
                # same. This greatly simplifies how tests need to request nodes during their
                # run scripts.
                min_nodes, max_nodes = self._calc_node_range(sched_config, len(chunk))

                acq_opts = [(min_nodes, max_nodes)]

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

        # Pull out any 'shared' tests that would have run by themselves anyway.
        for acq_opts, tests in list(share_groups.items()):
            if len(tests) == 1:
                test = tests[0]
                if sched_configs[test.full_id]['chunking']['size'] in (0, None):
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
                del share_groups[acq_opts]

        for acq_opts, tests in share_groups.items():
            node_range = acq_opts[0]
            self._schedule_shared_chunk(pav_cfg, tests, node_range, sched_configs, chunk)

        self._schedule_flex_chunk(pav_cfg, flex_tests, sched_configs, chunk)
        self._schedule_indi_chunk(pav_cfg, indi_tests, sched_configs, chunk)

    def _schedule_shared_chunk(self, pav_cfg, tests: List[TestRun], node_range: NodeRange,
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

        node_list = list(chunk)
        node_list.sort()

        if base_sched_config['chunking']['size'] in (0, None):
            picked_nodes = node_range
            job.save_node_data({node: self._nodes[node] for node in chunk})
        else:
            picked_nodes = node_list[:node_range[1]]
            job.save_node_data({node: self._nodes[node] for node in picked_nodes})

        job_name = 'pav_{}'.format(','.join(test.name for test in tests[:4]))
        if len(tests) > 4:
            job_name += ' ...'
        script = self._create_kickoff_script_stub(pav_cfg, job_name, job.kickoff_log,
                                                  base_sched_config, picked_nodes)

        for test in tests:
            # Run each test via pavilion
            script.command('echo "Starting test {t.id} - $(date)"'.format(t=test))
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.command('echo "Finished test {t.id} - $(date)"'.format(t=test))
            script.newline()

        script.write(job.kickoff_path)

        # Create symlinks for each test to the one test with the kickoff script and
        # log.
        for test in tests:
            test.job = job

        job.info = self._kickoff(pav_cfg, job, base_sched_config)

        for test in tests:
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off by {} scheduler in a shared allocation with {} other "
                "tests.".format(self.name, len(tests)))

    def _schedule_flex_chunk(self, pav_cfg, tests: List[TestRun],
                             sched_configs: Dict[str, dict], chunk: NodeSet):
        """Schedule tests in an individualized chunk that doesn't actually use
        chunking, leaving the node picking to the scheduler."""

        for test in tests:
            node_info = {node: self._nodes[node] for node in chunk}

            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
                job.save_node_data(node_info)
            except JobError as err:
                raise SchedulerPluginError("Error creating job: \n{}".format(err))

            sched_config = sched_configs[test.full_id]

            node_range = self._calc_node_range(sched_config, len(chunk))

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav_{}'.format(test.name),
                log_path=job.kickoff_log,
                sched_config=sched_config,
                picked_nodes=node_range)

            script.command('date +%s.%N')
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(job.kickoff_path)

            job.info = self._kickoff(pav_cfg, job, sched_config)
            test.job = job
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually (flex)) under {} scheduler."
                .format(self.name))

    def _schedule_indi_chunk(self, pav_cfg, tests: List[TestRun],
                             sched_configs: Dict[str, dict], chunk: NodeSet):
        """Schedule tests individually under the given chunk. Unlike with flex scheduling,
        we distribute the jobs across nodes manually."""

        # Track which nodes are available for individual runs. We'll consume nodes
        # from this list as they're handed out to tests, and reset it when
        # a test needs more nodes than it has.
        chunk_usage = list(chunk)
        chunk_usage.sort()
        chunk_size = len(chunk)

        by_need = []

        # Figure out how many nodes each test needs and sort them least
        for test in tests:
            sched_config = sched_configs[test.full_id]

            min_nodes, max_nodes = self._calc_node_range(sched_config, chunk_size)
            needed_nodes = min(max_nodes, chunk_size)

            by_need.append((needed_nodes, test))
        by_need.sort(key=lambda tup: tup[0])

        for needed_nodes, test in by_need:
            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
            except JobError as err:
                raise SchedulerPluginError("Error creating job: \n{}".format(err))

            sched_config = sched_configs[test.full_id]
            if needed_nodes == 0:

                if needed_nodes > len(chunk_usage):
                    chunk_usage = list(chunk)
                    chunk_usage.sort()

                test_chunk = chunk_usage[:needed_nodes]
                chunk_usage = chunk_usage[needed_nodes:]
            else:
                test_chunk = chunk

            picked_nodes = chunk_usage[:needed_nodes]

            try:
                job.save_node_data({node: self._nodes[node] for node in picked_nodes})
            except JobError as err:
                raise SchedulerPluginError("Error saving node info to job.: \n{}".format(err))

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav_{}'.format(test.name),
                log_path=job.kickoff_log,
                sched_config=sched_config,
                picked_nodes=picked_nodes)

            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(job.kickoff_path)

            job.info = self._kickoff(pav_cfg, job, sched_config)
            test.job = job
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually) under {} scheduler with {} nodes."
                .format(self.name, len(test_chunk)))
