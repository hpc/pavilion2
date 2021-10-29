"""Scheduler plugins give you the ability to (fairly) easily add new scheduling
mechanisms to Pavilion.
"""

# pylint: disable=no-self-use
import collections
import inspect
import json
import math
import os
import pickle
import pprint
import time
from abc import ABC
from pathlib import Path
from typing import List, Union, Dict, Any, NewType, Tuple, FrozenSet

import yaml_config as yc
from pavilion.scriptcomposer import ScriptHeader, ScriptComposer
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.test_config import file_format
from pavilion.test_run import TestRun
from yapsy import IPlugin
from .types import NodeInfo, Nodes, NodeList, NodeSet
from .vars import SchedulerVariables
from . import config
from . import node_selection


class SchedulerPluginError(RuntimeError):
    """Raised when scheduler plugins encounter an error."""


_SCHEDULER_PLUGINS = {}


class KickoffScriptHeader(ScriptHeader):
    """Base Class for kickoff script headers. Provides a common set of arguments.

    Most scheduler plugins should inherit from this, overriding the 'get_lines'
    method to add custom header lines to the kickoff script.
    """

    def __init__(self, job_name: str, sched_config: dict, nodes: NodeList):
        """Initialize the script header.

        :param job_name: The job should be named this under the scheduler, if possible.
        :param sched_config: The (validated) scheduler config.
        :param nodes: A list of specific nodes to kickoff the test under. Advanced
            schedulers should expect this, while basic scheduler classes should ignore
            it, but will have to implement 'include_nodes' and 'exclude_nodes' manually.
        """

        super().__init__()

        self._job_name = job_name
        self._config = sched_config
        self._nodes = nodes

    def get_lines(self):
        """Override and use included information to write a kickoff script header
        for this kickoff script."""

        raise NotImplementedError


def __reset():
    """This exists for testing purposes only."""

    if _SCHEDULER_PLUGINS is not None:
        for plugin in list(_SCHEDULER_PLUGINS.values()):
            plugin.deactivate()


def get_plugin(name):
    """Return a scheduler plugin

    :param str name: The name of the scheduler plugin.
    :rtype: SchedulerPlugin
    """

    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("No scheduler plugins loaded.")

    if name not in _SCHEDULER_PLUGINS:
        raise SchedulerPluginError(
            "Scheduler plugin not found: '{}'".format(name))

    return _SCHEDULER_PLUGINS[name]


def list_plugins():
    """Return a list of all available scheduler plugin names.

    :rtype: list
    """
    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("Scheduler Plugins aren't loaded.")

    return list(_SCHEDULER_PLUGINS.keys())


ChunksBySelect = NewType('ChunksBySelect', Dict[str, List[NodeList]])
ChunksByChunkSize = NewType('ChunksByChunkSize', Dict[int, ChunksBySelect])
ChunksByNodeListId = NewType('ChunksByNodeListId', Dict[int, ChunksByChunkSize])
TimeStamp = NewType('TimeStamp', float)
JobStatusDict = NewType('JobStatusDict', Dict['str', Tuple[TimeStamp, TestStatusInfo]])

BACKFILL = 'backfill'
DISCARD = 'discard'


class SchedulerPlugin(IPlugin.IPlugin):
    """The base scheduler plugin class. Scheduler plugins should inherit from
    this.
    """

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    KICKOFF_SCRIPT_EXT = '.sh'
    """The extension for the kickoff script."""

    KICKOFF_LOG_FN = 'kickoff.log'
    """The name of the kickoff log."""

    SCHED_LOG_FN = 'sched.log'
    """Some schedulers may keep a separate log. That log is redirected here if
    possible."""

    SCHED_DATA_FN = 'sched_data.txt'
    """This file holds scheduler data for a test, so that it doesn't have to be
    regenerated."""

    VAR_CLASS = SchedulerVariables
    """The scheduler's variable class."""

    KICKOFF_SCRIPT_HEADER_CLASS = KickoffScriptHeader
    """The class to use when generating headers for kickoff scripts."""

    NODE_SELECTION = {
        'contiguous': node_selection.contiguous,
        'random': node_selection.random,
        'rand_dist': node_selection.rand_dist,
        'distributed': node_selection.distributed,
    }

    CHUNK_EXTRA_OPTIONS = [
        BACKFILL,
        DISCARD,
    ]

    def __init__(self, name, description, priority=PRIO_CORE):
        """Scheduler plugin that is expected to be overriden by subclasses.
        The plugin will populate a set of expected 'sched' variables."""

        super().__init__()

        self.name = name
        self.description = description
        self.priority = priority

        self.path = inspect.getfile(self.__class__)
        self._is_available = None

        self._job_statuses = JobStatusDict({})  # type: JobStatusDict

        if self.VAR_CLASS is None:
            raise SchedulerPluginError("You must set the Var class for"
                                       "each plugin type.")

    def get_initial_vars(self, raw_sched_config: dict) -> SchedulerVariables:
        """Queries the scheduler to auto-detect its current state, and returns the
        dictionary of scheduler variables for that test given its config.

        :param raw_sched_config: The raw scheduler config for a given test.
        :returns: A tuple of the scheduler variables object and the node_list_id,
            which should be saved as part of the test config.
        """

        try:
            sched_config = config.validate_config(raw_sched_config)
        except config.SchedConfigError as err:
            raise SchedulerPluginError(
                "Error validating 'schedule' config section:\n{}".format(err.args[0]))

        if sched_config['num_nodes'] is None:
            raise SchedulerPluginError(
                "You must specify a value for schedule.num_nodes")

        return self._get_initial_vars(sched_config)

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Return the deferred scheduler variable object for the given scheduler
        config."""

        raise NotImplementedError("Overridden by the Basic/Advanced child classes.")

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Get the final, non-deferred scheduler variables for a test. This should
        only be called within an allocation."""

        raise NotImplementedError("Overridden by the Basic/Advanced child classes.")

    def schedule_tests(self, pav_cfg, tests: List[TestRun]):
        """Schedule each test using this scheduler."""

        raise NotImplementedError("Implemented in Basic/Advanced child classes.")

    def available(self) -> bool:
        """Returns true if this scheduler is available on this host."""

        if self._is_available is not None:
            return self._is_available

        else:
            return self._available()

    def _available(self) -> bool:
        """Return true if this scheduler is available on this system,
        false otherwise."""

        raise NotImplementedError("You must add a method to determine if the"
                                  "scheduler is available on this system.")

    JOB_STATUS_TIMEOUT = 1

    def job_status(self, pav_cfg, test) -> TestStatusInfo:
        """Get the job state from the scheduler, and map it to one of the
        of the following states: SCHEDULED, SCHED_ERROR, SCHED_CANCELLED,
        SCHED_WINDUP. This should only be called if the current recorded test state is
        'SCHEDULED'.

        The first SCHED_ERROR and SCHED_CANCELLED statuses encountered will be saved
        to the test status file, Other statuses are never saved. The test will also
        be set as complete.

        :param pav_cfg: The pavilion configuration.
        :param pavilion.test_run.TestRun test: The test we're checking on.
        :return: A StatusInfo object representing the status.
        """

        job_id = test.job_id

        if job_id in self._job_statuses:
            ts, status = self._job_statuses[test.job_id]
            if time.time() < ts + self.JOB_STATUS_TIMEOUT:
                return status

        status = self._job_status(pav_cfg, job_id)

        # Replace the windup state with the actual test state if it's already started.
        if status.state == STATES.SCHED_WINDUP:
            last_status = test.status.current()
            if last_status != STATES.SCHEDULED:
                return last_status
            else:
                return status

        # Record error and cancelled states if they haven't been seen before.
        if status.state in (STATES.SCHED_CANCELLED, STATES.SCHED_ERROR):
            if not test.status.has_state(status.state):
                test.status.add_status(status)
                test.set_run_complete()

        self._job_statuses[test.job_id] = time.time(), status

        return status

    def _job_status(self, pav_cfg, job_id: str) -> TestStatusInfo:
        """Override this to provide job status information given a job_id string.
        The format of the job_id string is scheduler dependent, and produced in the
        kickoff method. This can, optionally, set the job status for all jobs it can
        at once in the _job_statuses dict, which would greatly reduce the number of
        calls to the scheduler.

        It should always return a TestStatusInfo object with one of these states:
        SCHEDULED - The job is still waiting for an allocation.
        SCHED_ERROR - The job is dead because of some error.
        SCHED_CANCELLED - The job was cancelled.
        SCHED_WINDUP - Returned if the scheduler says the job is running or prepping to
            run. It's ok to return this if the test is actually running, it will be
            replaced with any newer state from the test status file.
        """

        raise NotImplementedError

    def get_conf(self) -> Union[yc.KeyedElem, None]:
        """Return the configuration object suitable for adding scheduler specific
        keys under 'scheduler.<scheduler_name> in the test configuration."""

        config_elements = self._get_config_elems()
        if not config_elements:
            return None

        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the {} scheduler.".format(self.name),
            elements=config_elements,
        )

    def _get_config_elems(self) -> List[yc.ConfigElement]:
        """Return the configuration elements specific to this scheduler."""

        return []

    def _create_kickoff_script_stub(self, pav_cfg, job_name: str, log_path: Path,
                                    sched_config: dict, chunk: NodeSet = None) \
            -> ScriptComposer:
        """Generate the kickoff script essentials preamble common to all scheduled
        tests.
        """

        chunk = chunk or []

        header = self._get_kickoff_script_header(job_name, sched_config, chunk)

        script = ScriptComposer(header=header)
        script.comment("Redirect all output to the kickoff log.")
        script.command("exec >{} 2>&1".format(log_path.as_posix()))

        # Make sure the pavilion spawned
        env_changes = {
            'PATH': '{}:${{PATH}}'.format(pav_cfg.pav_root/'bin'),
            'PAV_CONFIG_FILE': str(pav_cfg.pav_cfg_file),
        }
        if 'PAV_CONFIG_DIR' in os.environ:
            env_changes['PAV_CONFIG_DIR'] = os.environ['PAV_CONFIG_DIR']

        script.env_change(env_changes)

        # Run Kickoff Env setup commands
        for command in pav_cfg.env_setup:
            script.command(command)

        return script

    def _get_kickoff_script_header(self, job_name: str, sched_config: dict,
                                   nodes) -> KickoffScriptHeader:
        """Get a script header object for the kickoff script."""

        return self.KICKOFF_SCRIPT_HEADER_CLASS(
            job_name=job_name,
            sched_config=sched_config,
            nodes=nodes)

    def _kickoff_script_path(self, test: TestRun) -> Path:
        path = (test.path/'kickoff')
        return path.with_suffix(self.KICKOFF_SCRIPT_EXT)

    @staticmethod
    def _add_schedule_script_body(script, test):
        """Add the script body to the given script object. This default
        simply adds a comment and the test run command."""

        script.comment("Within the allocation, run the command.")
        script.command(test.run_cmd())

    def cancel_job(self, test) -> TestStatusInfo:
        """Tell the scheduler to cancel the given test, if it can. This should
        simply try it's best for the test given, and note in the test status
        (with a SCHED_ERROR) if there were problems. Update the test status to
        SCHED_CANCELLED if it succeeds.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: A status info object describing the state. If we actually
            cancel the job the test status will be set to SCHED_CANCELLED.
            This should return SCHED_ERROR when something goes wrong.
        :rtype: TestStatusInfo
        """

        job_id = test.job_id
        if job_id is None:
            test.set_run_complete()
            return test.status.set(STATES.SCHED_CANCELLED,
                                   "Job was never started.")

        cancel_result = self._cancel_job(test)
        test.set_run_complete()
        return cancel_result

    def _cancel_job(self, test):
        """Override in scheduler plugins to handle cancelling a job.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: Whether we're confident the job was canceled, and an
            explanation.
        :rtype: TestStatusInfo
        """
        raise NotImplementedError

    def activate(self):
        """Add this plugin to the scheduler plugin list."""

        name = self.name

        if name not in _SCHEDULER_PLUGINS:
            _SCHEDULER_PLUGINS[name] = self
            file_format.TestConfigLoader.add_subsection(self.get_conf())
        else:
            ex_plugin = _SCHEDULER_PLUGINS[name]
            if ex_plugin.priority > self.priority:
                pass
            elif ex_plugin.priority == self.priority:
                raise SchedulerPluginError(
                    "Two plugins for the same system plugin have the same "
                    "priority {}, {}.".format(self, _SCHEDULER_PLUGINS[name]))
            else:
                _SCHEDULER_PLUGINS[name] = self

    def deactivate(self):
        """Remove this plugin from the scheduler plugin list."""
        name = self.name

        if name in _SCHEDULER_PLUGINS:
            file_format.TestConfigLoader.remove_subsection(name)
            del _SCHEDULER_PLUGINS[name]


class SchedulerPluginBasic(SchedulerPlugin, ABC):
    """A Scheduler plugin that does not support automatic node inventories. It relies
    on manually set parameters in 'schedule.cluster_info'."""

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get the initial variables for the basic scheduler."""

        return self.VAR_CLASS(sched_config)

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Gather node information from within the allocation."""

        sched_config = config.validate_config(test.config['schedule'])
        alloc_nodes = self._get_alloc_nodes()

        num_nodes = sched_config['num_nodes']
        alloc_nodes = alloc_nodes[:num_nodes]

        nodes = Nodes({})
        for node in alloc_nodes:
            nodes[node] = self._get_alloc_node_info(node)

        return self.VAR_CLASS(sched_config, nodes=nodes, deferred=False)

    def _get_alloc_nodes(self) -> NodeList:
        """Given that this is running on an allocation, return the allocation's
        node list."""

        raise NotImplementedError("This must be implemented, even in basic schedulers.")

    def _get_alloc_node_info(self, node_name) -> NodeInfo:
        """Given that this is running on an allocation, get information about
        the given node. While this is completely optional, it can help pavilion
        better populate variables like 'test_min_cpus' and 'test_min_mem'."""

        _ = node_name

        return NodeInfo({})

    def schedule_tests(self, pav_cfg, tests: List[TestRun]):
        """Schedule each test independently."""

        for test in tests:
            sched_config = config.validate_config(test.config['schedule'])
            sched_log_path = test.path / self.SCHED_LOG_FN

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav test {} ({})'.format(test.full_id, test.name),
                log_path=test.path/self.KICKOFF_LOG_FN,
                sched_config=sched_config)

            script_path = self._kickoff_script_path(test)
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(script_path)

            self._kickoff(pav_cfg, script_path, sched_config, sched_log_path)
            test.status.set(STATES.SCHEDULED,
                            "Test kicked off with the {} scheduler".format(self.name))

    def _kickoff(self, pav_cfg, script_path: Path, sched_config: dict,
                 sched_log_path: Path):
        """Schedule the test under this scheduler.

        :param pav_cfg: The pavilion config.
        :param script_path: The path to the kickoff script, if applicable.
        :param sched_config: The scheduler configuration for this test or group of
            tests.
        :param sched_log_path: If the scheduler writes its own log file, it should
            be directed here if possible.
        """

        raise NotImplementedError("How to perform test kickoff is left for the "
                                  "specific scheduler to specify.")


class SchedulerPluginAdvanced(SchedulerPlugin, ABC):
    """A scheduler plugin that supports automatic node inventories, and as a
    consequence chunking and other advanced features."""

    def __init__(self, name, description, priority=SchedulerPluginBasic.PRIO_COMMON):
        """Initialize tracking of node info and chunks, in addition to the basics."""

        super().__init__(name, description, priority=priority)

        self._nodes = None  # type: Union[Nodes, None]
        self._node_lists = []  # type: List[NodeList]
        self._chunks = ChunksByNodeListId({})  # type: ChunksByNodeListId

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get initial variables (and chunks) for this scheduler."""

        self._nodes = self._get_system_inventory(sched_config)
        filtered_nodes, filter_reasons = self._filter_nodes(sched_config)
        filtered_nodes.sort()

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
        sched_config = config.validate_config(test.config['schedule'])

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
                return json.load(data_file)
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
            node_name, node = self._transform_raw_node_data(sched_config, raw_node,
                                                            extra)
            nodes[node_name] = node

        return nodes

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

    def _filter_nodes(self, sched_config: Dict[str, Any]) \
            -> Tuple[NodeList, Dict[str, int]]:
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
        exclude_nodes = sched_config.get(self.name, {}).get('exclude_nodes', [])
        node_state = sched_config['node_state']

        filter_reasons = collections.defaultdict(lambda: 0)

        for node_name, node in nodes.items():
            if not node.get(node_state):
                filter_reasons['state'] += 1
                continue

            if 'partition' in node and node['partition'] != partition:
                filter_reasons['partition'] += 1
                continue

            if 'reservation' in node and node['reservation'] != reservation:
                filter_reasons['reservation'] += 1
                continue

            if node_name in exclude_nodes:
                filter_reasons['excluded'] += 1
                continue

            # Filter according to scheduler plugin specific options.
            if not self._filter_custom(sched_config, node_name, node):
                filter_reasons[self.name] += 1
                continue

            out_nodes.append(node_name)

        return out_nodes, filter_reasons

    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> bool:
        """Apply scheduler specific filters to the node list. Returns True
        if the node should be included."""

        _ = sched_config, node_name, node

        return True

    def _get_chunks(self, node_list_id, sched_config) -> List[NodeSet]:
        """Chunking is specific to the node list, chunk size, and node selection
        settings of a job. The actual chunk used by a test_run won't be known until
        after the test is at least partially resolved, however. Until then, it only
        knows what chunks are available.

        This method retrieves or creates a list of ChunkInfo objects, and returns
        it."""

        nodes = list(self._node_lists[node_list_id])

        id_chunks = self._chunks.get(node_list_id, {})
        self._chunks[node_list_id] = id_chunks

        chunk_size = sched_config['chunk_size']

        # Chunk size 0/null is all the nodes.
        if chunk_size == 0:
            chunk_size = len(nodes)

        chunk_extra = sched_config['chunk_extra']
        node_select = sched_config['chunk_node_selection']

        known_chunks = self._chunks[node_list_id].get(chunk_size, {})
        self._chunks[node_list_id][chunk_size] = known_chunks

        # If we already have chunks for this node list, chunk size, and selection
        # method just return what we've got.
        if node_select in known_chunks:
            return known_chunks[node_select]

        chunks = []
        for i in range(len(nodes)//chunk_size):
            # Apply the selection function and get our chunk nodes.
            chunk = self.NODE_SELECTION[node_select](nodes, chunk_size)
            # Filter out any chosen from our node list.
            nodes = [node for node in nodes if node not in chunk]
            chunks.append(chunk)

        if nodes and chunk_extra == BACKFILL:
            backfill = chunks[-1][len(nodes) - chunk_size]
            chunks.append(backfill + nodes)

        chunk_info = []
        for chunk in chunks:
            chunk_info.append(NodeSet(frozenset(chunk)))
        known_chunks[node_select] = chunk_info

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
            node_list_id = test.var_man.get('sched.node_list_id')

            sched_config = config.validate_config(test.config['schedule'])
            sched_configs[test.full_id] = sched_config
            chunk_id = test.config.get('chunk')
            if chunk_id == 'any':
                # This is validated in test object creation.
                chunk_id = int(chunk_id)

            chunk_size = sched_config['chunk_size']
            node_select = sched_config['chunk_node_selection']

            chunks = self._chunks[node_list_id][chunk_size][node_select]

            if chunk_id == 'any':
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
                if chunk_id > len(chunks):
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
                acq_opts = tuple(sched_config.get(key)
                                 for key in self.ALLOC_ACQUIRE_OPTIONS)

            share_groups[acq_opts].append(test)

        for acq_opts, tests in share_groups:
            if acq_opts is None:
                self._schedule_indi_chunk(pav_cfg, tests, sched_configs, chunk)
            else:
                self._schedule_shared_chunk(pav_cfg, tests, sched_configs, chunk)

    def _schedule_shared_chunk(self, pav_cfg, tests: List[TestRun],
                               sched_configs: Dict[str, dict], chunk: NodeSet):
        """Scheduler tests in a shared chunk."""

        # At this point the scheduler config should be effectively identical
        # for the test being allocated.
        base_test = tests[0]
        sched_config = sched_configs[base_test.full_id].copy()
        # Get the longest time limit for all the tests.
        sched_config['time_limit'] = max(conf['time_limit'] for conf in
                                         sched_configs.values())

        # The set of nodes for a given test.
        test_nodes = {}

        node_list = list(chunk)
        node_list.sort()

        # The number of nodes needed for our shared allocation. Basically, the most
        # nodes needed out of all the tests that are to run.
        shared_nodes = 1
        for test in tests:
            needed_nodes = sched_config['num_nodes']
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
            chunk = chunk[:shared_nodes]

        log_path = base_test.path/self.KICKOFF_LOG_FN
        job_name = 'pav tests {}'.format(','.join(test.full_id for test in tests))
        script = self._create_kickoff_script_stub(pav_cfg, job_name, log_path,
                                                  sched_config, chunk)

        for test in tests:
            # Run each test via pavilion
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))

            # Save the list of nodes that each test is to run on within the allocation
            self._save_sched_data(test, test_nodes[test.full_id])

        script_path = self._kickoff_script_path(base_test)
        script.write(script_path)

        # Create symlinks for each test to the one test with the kickoff script and
        # log.
        sched_log_path = base_test.path/self.SCHED_LOG_FN
        for test in tests:
            if test is not base_test:
                symlink_script_path = self._kickoff_script_path(test)
                symlink_script_path.symlink_to(script_path)
                symlink_log_path = base_test.path/self.KICKOFF_LOG_FN
                symlink_log_path.symlink_to(log_path)
                symlink_sched_log_path = base_test.path/self.SCHED_LOG_FN
                symlink_sched_log_path.symlink_to(sched_log_path)

        self._kickoff(pav_cfg, script_path, sched_config, chunk, sched_log_path)
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

            needed_nodes = sched_config['num_nodes']
            if isinstance(needed_nodes, float):
                needed_nodes = math.ceil(needed_nodes * len(chunk))
            needed_nodes = min(needed_nodes, len(chunk))

            by_need.append((needed_nodes, test))
        by_need.sort()

        for needed_nodes, test in by_need:
            sched_config = sched_configs[test.full_id]
            if chunk is not None:
                if needed_nodes > len(chunk_usage):
                    chunk_usage = list(chunk)
                    chunk_usage.sort()

                test_chunk = chunk_usage[:needed_nodes]
                chunk_usage = chunk_usage[needed_nodes:]
            else:
                test_chunk = chunk

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav test {} ({})'.format(test.full_id, test.name),
                log_path=test.path/self.KICKOFF_LOG_FN,
                sched_config=sched_config,
                chunk=test_chunk)

            script_path = self._kickoff_script_path(test)
            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(script_path)

            sched_log_path = test.path / self.SCHED_LOG_FN

            self._kickoff(pav_cfg, script_path, sched_config, test_chunk,
                          sched_log_path)
            test.status.set(
                STATES.SCHEDULED,
                "Test kicked off (individually) under {} scheduler with {} nodes."
                .format(self.name, len(test_chunk)))

    def _kickoff(self, pav_cfg, script_path: Path, sched_config: dict,
                 chunk: NodeList, sched_log_path: Path):
        """Schedule the test under this scheduler.

        :param pav_cfg: The pavilion config.
        :param script_path: The path to the kickoff script, if applicable.
        :param sched_config: The scheduler configuration for this test or group of
            tests.
        :param chunk: List of nodes on which to start this test.
        :param sched_log_path: If the scheduler writes its own log file, it should
            be directed here if possible.
        """

        raise NotImplementedError("How to perform test kickoff is left for the "
                                  "specific scheduler to specify.")
