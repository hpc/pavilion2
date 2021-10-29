"""Scheduler variable base class."""
from typing import List

from pavilion.schedulers.base_scheduler import Nodes, NodeList, NodeInfo
from pavilion.test_config import DeferredVariable
from pavilion.var_dict import VarDict, var_method, dfr_var_method


class SchedulerVariables(VarDict):
    """The base scheduler variables class. Each scheduler should have a child
class of this that contains all the variable functions it provides.

To add a scheduler variable, create a method and decorate it with
either ``@sched_var`` or ``@dfr_sched_var()``. The method name will be the
variable name, and the method will be called to resolve the variable
value. Methods that start with '_' are ignored.

Naming Conventions:

'alloc_*'
  Variable names should be prefixed with 'alloc\\_' if they are deferred.

'test_*'
  Variable names prefixed with test denote that the variable
  is specific to a test. These also tend to be deferred.
"""

    EXAMPLE = {
        'min_cpus': "3",
        'min_mem': "123412",
    }

    """Each scheduler variable class should provide an example set of
    values for itself to display when using 'pav show' to list the variables.
    These are easily obtained by running a test under the scheduler, and
    then harvesting the results of the test run."""

    def __init__(self, nodes: Nodes, sched_config: dict, chunks: List[NodeList] = None,
                 deferred=True):
        """Initialize the scheduler var dictionary. This will be initialized
        when preliminary variables are gathered vs when it is no longer deferred.
        Initial variables are based on the full node list and then given list
        of chunks. For deferred variables, however, the nodes only contain those
        nodes that are part of the actual allocation. 'chunks' is not given in this
        case.

        :param nodes: The dict of node names to node data. If None, will default to
            an empty dict.
        :param sched_config: The scheduler configuration for the corresponding test.
        :param chunks: The list of chunks, each of which is a list of node names. If
            None, will default to an empty list.
        :param deferred: Whether the variables are deferred.
        """

        super().__init__('sched', deferred=deferred)

        self._sched_config = sched_config
        self._nodes = nodes if nodes else {}
        self._chunks = chunks if chunks else []

        self._keys = self._find_vars()

    NO_EXAMPLE = '<no example>'

    def info(self, key):
        """Get the info dict for the given key, and add the example to it."""

        info = super().info(key)
        example = None
        try:
            example = self[key]
        except (KeyError, ValueError, OSError):
            pass

        if example is None or isinstance(example, DeferredVariable):
            example = self.EXAMPLE.get(key, self.NO_EXAMPLE)

        if isinstance(example, list):
            if len(example) > 10:
                example = example[:10] + ['...']

        info['example'] = example

        return info

    def __repr__(self):
        for k in self.keys():
            _ = self[k]

        return super().__repr__()

    # Variables
    # The methods that follow are all scheduler variables. They provide bare
    # basic single node functionality that may be good enough in certain
    # situations, namely when your general architecture is such that
    # front-end nodes have less resources than any compute node. Note that
    # they are all non-deferred, so they're safe to use in build scripts,

    def _get_min(self, nodes: List[NodeInfo], attr: str, default: int):
        """Get the minimum of the given attribute across the list of nodes,
        settling for the default if no node had useful info and there's
        no value in the scheduler configs cluster info."""

        min_val = None
        for node in nodes:
            val = node.get(attr)
            if val is not None:
                if min_val is None or val < min_val:
                    min_val = val

        if min_val is None:
            cluster_info = self._sched_config.get('cluster_info', {})
            min_val = cluster_info.get(attr, default)

        return min_val

    @var_method
    def test_cmd(self):
        """The command to prepend to a line to kick it off under the
        scheduler. This is blank by default, but most schedulers will
        want to define something that utilizes relevant scheduler
        parameters."""

        return ''

    @dfr_var_method
    def tasks_per_node(self) -> int:
        """The number of tasks to create per node. If the scheduler does not support
        node info, just returns 1."""

        tasks_per_node = self._sched_config['tasks_per_node']

        if isinstance(tasks_per_node, int):
            if tasks_per_node == 0:
                return self.min_cpus()
            else:
                return tasks_per_node
        else:  # Should be a float
            if self._nodes:
                return min(int(tasks_per_node * self.min_cpus()), 1)
            else:
                return 1

    @var_method
    def chunk_ids(self):
        """A list of indices of the available chunks."""
        return list(range(len(self._chunks)))

    @var_method
    def min_cpus(self):
        """Get a minimum number of cpus available on each (filtered) noded. Defaults to
        1 if unknown."""

        return self._get_min(list(self._nodes.values()), 'cpus', 1)

    @var_method
    def min_mem(self):
        """Get a minimum for any node across each (filtered) nodes. Returns
        a value in bytes (4 GB if unknown)."""

        return self._get_min(list(self._nodes.values()), 'mem', 4*1024**3)

    @var_method
    def nodes(self) -> int:
        """The number of nodes available on the system. If the scheduler
        supports auto-detection, this will be the filtered count of nodes. Otherwise,
        this will be the 'cluster_info.node_count' value, or 1 if that isn't set."""

        if self._nodes:
            return len(self._nodes)

        return self._sched_config.get('cluster_info', {}).get('node_count', 1)

    @var_method
    def node_list(self) -> NodeList:
        """The list of node names on the system. If the scheduler supports
        auto-detection, will be the filtered list. This list will otherwise be empty."""

        if self._nodes:
            return NodeList(list(self._nodes.keys()))
        else:
            return NodeList([])

    @dfr_var_method
    def test_nodes(self) -> int:
        """The number of nodes for this specific test, determined once the test
        has an allocation. Note that the allocation size may be larger than this
        number."""

        return len(self._nodes)

    @dfr_var_method
    def test_node_list(self) -> NodeList:
        """The list of nodes by name allocated for this test. Note that more
        nodes than this may exist in the allocation."""

        return NodeList(list(self._nodes.keys()))

    @dfr_var_method
    def test_min_cpus(self):
        """The min cpus for each node in the chunk. Defaults to 1 if no info is
        available."""

        return self._get_min(list(self._nodes.values()), 'cpus', 1)

    @dfr_var_method
    def test_min_mem(self):
        """The min memory for each node in the chunk in bytes. Defaults to 4 GB if
        no info is available."""

        return self._get_min(list(self._nodes.values()), 'mem', 4*1024**3)

    @dfr_var_method
    def tasks_total(self):
        """Total tasks to create, based on number of nodes actually acquired."""

        return self._sched_config.get('tasks_per_node', 1) * len(self._nodes)