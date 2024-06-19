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
from .config import validate_config, AVAILABLE, BACKFILL, calc_node_range
from .scheduler import SchedulerPlugin
from ..errors import SchedulerPluginError
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

        self._nodes: Union[Nodes, None] = None
        self._node_lists: List[NodeList] = []  # type: List[NodeList]
        self._chunks: ChunksByNodeListId = ChunksByNodeListId({})

        # Refresh here, to ensure that a new object and a refreshed object have the same state.
        self.refresh()

    def refresh(self):
        """Clear all internal state variables."""

        self._nodes = None
        self._node_lists = []
        self._chunks = ChunksByNodeListId({})

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

        chunk_size = sched_config['chunking']['size']
        include_nodes = sched_config['include_nodes']
        # Note: When chunking isn't used (ie - node selection is left to the scheduler),
        # node inclusion is handled by the scheduler plugin.
        for node in include_nodes:
            if node not in filtered_nodes:
                errors.append(
                    "Requested node (via 'schedule.include_nodes') was filtered "
                    "due to other filtering ")

        if chunk_size not in (0, None) and len(include_nodes) >= chunk_size:
            errors.append(
                "Requested {} 'schedule.include_nodes' to include in every chunk, but "
                "set a 'chunking.size' of {}. "
                "The chunk size must be more than the number of include_nodes."
                .format(len(include_nodes, chunk_size)))

        # Min nodes is always >= 1, but max_nodes may be None
        min_nodes, max_nodes = calc_node_range(sched_config, len(filtered_nodes))
        if max_nodes is not None:
            if min_nodes > max_nodes:
                errors.append(
                    "Requested between {}-{} nodes, but the minimum is more than the maximum "
                    "node count"
                    .format(min_nodes, max_nodes))

            if max_nodes < len(include_nodes):
                errors.append(
                    "Requested {} 'schedule.include_nodes' to be included in every job, but "
                    "the job size is only {} via 'schedule.nodes'."
                    .format(len(include_nodes), max_nodes))

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
                "left after filtering. Nodes were filtered for the following reasons:\n{}\n"
                "Scheduler config:\n{}\n"
                .format(min_nodes, max_nodes, len(filtered_nodes),
                        reasons, pprint.pformat(sched_config)))

        try:
            node_list_id = self._node_lists.index(filtered_nodes)
        except ValueError:
            node_list_id = len(self._node_lists)
            self._node_lists.append(filtered_nodes)

        chunks = self._get_chunks(node_list_id, sched_config)

        nodes = Nodes({node: self._nodes[node] for node in filtered_nodes})
        sched_vars = self.VAR_CLASS(sched_config, nodes=nodes, chunks=chunks,
                                    node_list_id=node_list_id)
        sched_vars.add_errors(errors)
        return sched_vars

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Load our saved node data from kickoff time, and compute the final
        scheduler variables from that."""

        try:
            nodes = test.job.load_sched_data()
        except JobError as err:
            raise SchedulerPluginError("Could not load node info.", err)

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
                raise RuntimeError("Advanced schedulers must always return a node "
                                   "'name' key when transforming raw node data. "
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
        across_nodes = sched_config['across_nodes']
        exclude_nodes = sched_config['exclude_nodes']
        node_state = sched_config['node_state']

        filter_reasons = collections.defaultdict(lambda: [])
        available_msg = "Nodes not available ('schedule.node_state={}')".format(AVAILABLE)

        for node_name, node in nodes.items():
            if not node.get('up'):
                filter_reasons['Nodes not up'].append(node_name)
                continue

            if node_state == AVAILABLE and not node.get('available'):
                filter_reasons[available_msg].append(node_name)
                continue

            if (partition is not None
                    and 'partitions' in node
                    and partition not in node['partitions']):
                reason_key = "Requested 'schedule.partition' '{}' not in {}"\
                             .format(partition, node['partitions'])
                filter_reasons[reason_key].append(node_name)
                continue

            if 'reservations' in node:
                if (reservation is not None
                        and reservation not in node['reservations']):
                    reason_key = "Requested 'schedule.reservation' '{}' not in {}"\
                                 .format(reservation, node['reservations'])
                    filter_reasons[reason_key].append(node_name)
                    continue

            if across_nodes and node_name not in across_nodes:
                filter_reasons['Not in "schedule.across_nodes"'].append(node_name)
                continue

            if node_name in exclude_nodes:
                filter_reasons['Excluded via "schedule.exclude_nodes"'].append(node_name)
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

    def _make_chunk_group_id(self, node_list_id, sched_config):
        """Generate a 'chunk_group_id' - a tuple of values that denote a unique type of chunk."""

        nodes = list(self._node_lists[node_list_id])

        # Nodes to include in every chunk.
        include_id = ','.join(sorted(sched_config['include_nodes']))

        chunk_size = sched_config['chunking']['size']
        if isinstance(chunk_size, float):
            chunk_size = int(len(nodes) * chunk_size)
        # Chunk size 0/null is all the nodes.
        if chunk_size in (0, None) or chunk_size > len(nodes):
            chunk_size = len(nodes)
        chunk_extra = sched_config['chunking']['extra']
        node_select = sched_config['chunking']['node_selection']

        return (node_list_id, chunk_size, node_select, chunk_extra, include_id)

    def _get_chunks(self, node_list_id, sched_config) -> List[NodeSet]:
        """Chunking is specific to the node list, chunk size, and node selection
        settings of a job. The actual chunk used by a test_run won't be known until
        after the test is at least partially resolved, however. Until then, it only
        knows what chunks are available.

        This method retrieves or creates a list of ChunkInfo objects, and returns
        it."""

        nodes = list(self._node_lists[node_list_id])

        # Nodes to include in every chunk.
        include_nodes = sched_config['include_nodes']
        include_id = ','.join(sorted(include_nodes))

        chunk_size = sched_config['chunking']['size']
        if isinstance(chunk_size, float):
            chunk_size = int(len(nodes) * chunk_size)
        # Chunk size 0/null is all the nodes.
        if chunk_size in (0, None) or chunk_size > len(nodes):
            chunk_size = len(nodes)
        chunk_extra = sched_config['chunking']['extra']
        node_select = sched_config['chunking']['node_selection']

        chunk_group_id = self._make_chunk_group_id(node_list_id, sched_config)
        # If we already have chunks for our node list and settings, just return what
        # we've got.
        if chunk_group_id in self._chunks:
            return self._chunks[chunk_group_id]

        # We can potentially have no nodes, in which case return an empty chunk.
        if chunk_size == 0:
            self._chunks[chunk_group_id] = [NodeSet(frozenset([]))]
            return self._chunks[chunk_group_id]

        # Only count nodes that aren't required via 'include_nodes' when calculating chunks.
        for node in include_nodes:
            if node in nodes:
                nodes.remove(node)

        if len(nodes) == chunk_size:
            chunks = include_nodes
        else:
            chunk_size = chunk_size - len(include_nodes)
            chunks = []

            for i in range(len(nodes)//chunk_size):
                # Apply the selection function and get our chunk nodes.
                chunk = self.NODE_SELECTION[node_select](nodes, chunk_size)
                # Filter out any chosen from our node list.
                nodes = [node for node in nodes if node not in chunk]

                # Add the 'include_nodes' to every chunk.
                chunk = include_nodes + chunk
                chunks.append(chunk)

        if nodes and chunk_extra == BACKFILL:
            backfill = chunks[-1][:chunk_size - len(nodes)]
            chunks.append(backfill + nodes)

        chunk_info = []
        for chunk in chunks:
            chunk_info.append(NodeSet(frozenset(chunk)))

        self._chunks[chunk_group_id] = chunk_info

        return chunk_info

    def schedule_tests(self, pav_cfg, tests: List[TestRun]) -> List[SchedulerPluginError]:
        """Schedule each of the given tests using this scheduler using a
        separate allocation (if applicable) for each.

        :param pav_cfg: The pavilion config
        :param [pavilion.test_run.TestRun] tests: A list of pavilion tests
            to schedule.
        :returns: A list of Scheduler errors encountered when starting tests.
        """

        # type: Dict[FrozenSet[str], List[TestRun]]
        by_chunk = collections.defaultdict(lambda: [])
        usage = collections.defaultdict(lambda: 0)  # type: Dict[FrozenSet[str], int]
        sched_configs = {}  # type: Dict[str, dict]

        errors = []

        for test in tests:
            node_list_id = int(test.var_man.get('sched.node_list_id'))

            sched_config = validate_config(test.config['schedule'])
            sched_configs[test.full_id] = sched_config
            chunk_spec = test.config.get('chunk')
            if chunk_spec != 'any':
                # This is validated in test object creation.
                chunk_spec = int(chunk_spec)

            chunk_group_id = self._make_chunk_group_id(node_list_id, sched_config)

            chunks = self._chunks[chunk_group_id]

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
                    errors.append(SchedulerPluginError(
                        "Test selected chunk '{}', but there are only {} chunks "
                        "available.".format(chunk_spec, len(chunks)), tests=[test]))
                chunk = chunks[chunk_spec]
                by_chunk[chunk].append(test)

        for chunk, tests in by_chunk.items():
            errors.extend(self._schedule_chunk(pav_cfg, chunk, tests, sched_configs))

        return errors

    # Scheduling options in this list are denoted as those that change the nature
    # of the allocation being acquired. Tests with different values for these
    # should thus run under different allocations.
    # These allow us to form sharable groups given a specific nodelist - jobs with
    # different nodelists will never be shared.
    # This can be modified by subclasses. Separate multipart keys with a '.'.
    JOB_SHARE_KEY_ATTRS = ['partition', 'reservation', 'account', 'qos']

    def _schedule_chunk(self, pav_cfg, chunk: NodeSet, tests: List[TestRun],
                        sched_configs: Dict[str, dict]) -> List[SchedulerPluginError]:
        '''Schedule all the tests that belong to a given chunk. Group tests that can be scheduled in
        a shared allocation together.

        :returns: A list of encountered errors.
        '''

        # There are three types of test launches.
        # 1. Tests that can share an allocation. These may or may not use chunking.
        share_groups = collections.defaultdict(list)
        # 2. Tests that don't share an allocation and don't have nodes explicitly defined.
        flex_tests: List[TestRun] = []
        # 3. Tests that don't share an allocation and do have nodes explicitly defined.
        indi_tests: List[TestRun] = []

        errors = []

        for test in tests:
            sched_config = sched_configs[test.full_id]

            if not sched_config['share_allocation']:
                if sched_config['flex_scheduled']:
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
            else:
                # Only share allocations if the number of nodes needed by the test is the
                # same. This greatly simplifies how tests need to request nodes during their
                # run scripts.
                min_nodes, max_nodes = calc_node_range(sched_config, len(chunk))
                job_share_key = self.gen_job_share_key(sched_config, min_nodes, max_nodes)
                share_groups[job_share_key].append(test)

        # Pull out any 'shared' tests that would have run by themselves anyway.
        for job_share_key, tests in list(share_groups.items()):
            if len(tests) == 1:
                test = tests[0]
                if sched_configs[test.full_id]['chunking']['size'] in (0, None):
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
                del share_groups[job_share_key]

        for job_share_key, tests in share_groups.items():
            chunking_enabled = sched_configs[tests[0].full_id]['chunking']['size'] not in (0, None)
            # If the user really wants to use the same nodes even if other nodes are available,
            # setting share_allocation to max will allow that.
            use_same_nodes = True if sched_config['share_allocation'] == 'max' else False
            node_range = tuple(job_share_key[:2])
            max_nodes = node_range[1]
            # Schedule all these tests in one allocation. Chunked tests are already spread across
            # chunks, and these non-chunked tests are explicitly set to use one allocation.
            if chunking_enabled or use_same_nodes or max_nodes is None:
                errors.extend(self._schedule_shared(pav_cfg, tests, node_range,
                                                    sched_configs, chunk))
            # Otherwise, we need to bin the tests so they are spread across the machine.
            # Tests will still share allocations but will be divided up to maximally use the
            # machine.
            else:
                bin_count = max(len(chunk) // max_nodes, 1)
                bins = [[] for _ in range(bin_count)]
                for i, test in enumerate(tests):
                    bins[i % bin_count].append(test)
                for test_bin in bins:
                    if test_bin:
                        errors.extend(self._schedule_shared(pav_cfg, test_bin, node_range,
                                                            sched_configs, chunk))

        errors.extend(self._schedule_indi_flex(pav_cfg, flex_tests, sched_configs, chunk))
        errors.extend(self._schedule_indi_chunk(pav_cfg, indi_tests, sched_configs, chunk))

        return errors

    def _schedule_shared(self, pav_cfg, tests: List[TestRun], node_range: NodeRange,
                         sched_configs: Dict[str, dict], chunk: NodeSet) \
                         -> List[SchedulerPluginError]:
        """Scheduler tests in a shared allocation. This allocation will use chunking when
        enabled, or allow the scheduler to pick the nodes otherwise."""

        try:
            job = Job.new(pav_cfg, tests, self.KICKOFF_FN)
        except JobError as err:
            return [SchedulerPluginError("Error creating job.", prior_error=err, tests=tests)]

        # At this point the scheduler config should be effectively identical
        # for the test being allocated.
        base_test = tests[0]
        base_sched_config = sched_configs[base_test.full_id].copy()
        # Get the longest time limit for all the tests.
        base_sched_config['time_limit'] = max(conf['time_limit'] for conf in
                                              sched_configs.values())

        node_list = list(chunk)
        node_list.sort()

        if base_sched_config['flex_scheduled']:
            # We aren't using chunking, so let the scheduler pick.
            picked_nodes = None
            # Save the data for all (compatible) nodes, we never know which we will get.
            job.save_node_data(self._nodes)
        else:
            if node_range[1] is not None:
                picked_nodes = node_list[:node_range[1]]
            # Save the data for all the nodes we're using.
            job.save_node_data(self._nodes)
            # Clear the node range - it's only used for flexible scheduling.
            node_range = None


        job_name = 'pav_{}'.format(','.join(test.name for test in tests[:4]))
        if len(tests) > 4:
            job_name += ' ...'
        script = self._create_kickoff_script_stub(pav_cfg, job_name, job.kickoff_log,
                                                  base_sched_config, nodes=picked_nodes,
                                                  node_range=node_range,
                                                  shebang=base_test.shebang)

        # Run each test via pavilion
        script.command('echo "Starting {} tests - $(date)"'.format(len(tests)))
        script.command('pav _run {}'.format(" ".join(test.full_id for test in tests)))

        script.write(job.kickoff_path)

        # Create symlinks for each test to the one test with the kickoff script and
        # log.
        for test in tests:
            test.job = job

        try:
            job.info = self._kickoff(
                pav_cfg=pav_cfg,
                job=job,
                sched_config=base_sched_config,
                job_name=job_name,
                nodes=picked_nodes,
                node_range=node_range)
        except SchedulerPluginError as err:
            return [self._make_kickoff_error(err, tests)]
        except Exception as err:  # pylint: disable=broad-except
            return [SchedulerPluginError(
                "Unexpected error kicking off tests under '{}' scheduler."
                .format(self.name),
                prior_error=err, tests=tests)]

        for test in tests:
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off by {} scheduler in a shared allocation with {} other "
                "tests.".format(self.name, len(tests)))

        return []

    def _schedule_indi_flex(self, pav_cfg, tests: List[TestRun],
                            sched_configs: Dict[str, dict], chunk: NodeSet) \
                            -> List[SchedulerPluginError]:
        """Schedule tests individually in 'flexible' allocations, where the scheduler
        picks the nodes."""

        errors = []
        for test in tests:
            node_info = {node: self._nodes[node] for node in chunk}

            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
                job.save_node_data(self._nodes)
            except JobError as err:
                errors.append(SchedulerPluginError("Error creating job.",
                                                   prior_error=err, tests=[test]))
                continue

            sched_config = sched_configs[test.full_id]

            node_range = calc_node_range(sched_config, len(chunk))

            job_name = 'pav_{}'.format(test.name)
            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name=job_name,
                log_path=job.kickoff_log,
                sched_config=sched_config,
                node_range=node_range,
                shebang=test.shebang)

            script.command('pav _run {t.full_id}'.format(t=test))
            script.write(job.kickoff_path)

            test.job = job

            try:
                job.info = self._kickoff(
                    pav_cfg=pav_cfg,
                    job=job,
                    sched_config=sched_config,
                    job_name=job_name,
                    node_range=node_range,
                )
            except SchedulerPluginError as err:
                errors.append(self._make_kickoff_error(err, tests))
                continue
            except Exception as err:  # pylint: disable=broad-except
                errors.append(SchedulerPluginError(
                    "Unexpected error kicking off test under '{}' scheduler."
                    .format(self.name), prior_error=err))
                continue

            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually (flex)) under {} scheduler."
                .format(self.name))

        return errors

    def _schedule_indi_chunk(self, pav_cfg, tests: List[TestRun],
                             sched_configs: Dict[str, dict], chunk: NodeSet):
        """Schedule tests individually under the given chunk. These are not flex
        scheduled."""

        # Track which nodes are available for individual runs. We'll consume nodes
        # from this list as they're handed out to tests, and reset it when
        # a test needs more nodes than it has.
        chunk_usage = list(chunk)
        chunk_usage.sort()
        chunk_size = len(chunk)

        by_need = []

        errors = []

        # Figure out how many nodes each test needs and sort them least
        for test in tests:
            sched_config = sched_configs[test.full_id]

            min_nodes, max_nodes = calc_node_range(sched_config, chunk_size)
            if max_nodes is None:
                max_nodes = chunk_size
            needed_nodes = min(max_nodes, chunk_size)

            by_need.append((needed_nodes, test))
        by_need.sort(key=lambda tup: tup[0])

        for needed_nodes, test in by_need:
            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
            except JobError as err:
                errors.append(SchedulerPluginError("Error creating job.",
                                                   prior_error=err, tests=[test]))
                continue

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
                job.save_node_data(self._nodes)
            except JobError as err:
                errors.append(SchedulerPluginError("Error saving node info to job.",
                              prior_error=err, tests=[test]))
                continue

            job_name = 'pav_{}'.format(test.name)
            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name=job_name,
                log_path=job.kickoff_log,
                sched_config=sched_config,
                nodes=picked_nodes,
                shebang=test.shebang)

            script.command('pav _run {t.full_id}'.format(t=test))
            script.write(job.kickoff_path)

            test.job = job

            try:
                job.info = self._kickoff(
                    pav_cfg=pav_cfg,
                    job=job,
                    sched_config=sched_config,
                    job_name=job_name,
                    nodes=picked_nodes)
            except SchedulerPluginError as err:
                return [self._make_kickoff_error(err, [test])]
            except Exception as err:  # pylint: disable=broad-except
                errors.append(SchedulerPluginError(
                    "Unexpected error kicking off test under '{}' scheduler."
                    .format(self.name), prior_error=err, tests=[test]))

            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually) under {} scheduler with {} nodes."
                .format(self.name, len(test_chunk)))

        return errors
