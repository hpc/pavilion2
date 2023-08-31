"""Functions and definitions relating to scheduler configuration in tests."""

from typing import Any, Dict, Union, List, Tuple
import math

import yaml_config as yc
from pavilion import utils


MPIRUN_BIND_OPTS = ('slot', 'hwthread', 'core', 'L1cache', 'L2cache', 'L3cache',
                    'socket', 'numa', 'board', 'node')


class ScheduleConfig(yc.KeyedElem):
    """Scheduling configuration."""

    ELEMENTS = [
        yc.StrElem('core_spec',
            help_text="The count identifies the number of cores to be reserved"
                      " for system overhead on each allocated compute node."),
        yc.StrElem(
            'nodes',
            help_text="The number of nodes to acquire to scheduler the job as "
                      "whole. This may be a number, a percentage, "
                      "or the keyword 'all'. In all cases, this limit is applied "
                      "after chunking, so 'all' when the chunk.size is 1000 will be "
                      "1000 nodes. A single node is both the default and "
                      "minimum selection."),
        yc.StrElem(
            'min_nodes',
            help_text="The minimum number of nodes to allocate. This is only supported "
                      "in basic schedulers as a way to schedule a node range when "
                      "the total number of nodes isn't reliably known."),
        yc.StrElem(
            'node_state',
            help_text="Filter nodes based on their current state. Options are "
                      "'up' (default) or 'available'. 'Up' counts/includes only nodes "
                      "in allocations that are usable regardless of current allocation "
                      "status. Available nodes are up, and also not currently "
                      "allocated."),
        yc.StrElem(
            'share_allocation',
            help_text="If true, share the allocation with other tests in the same "
                      "chunk. The allocation will have a number of nodes equal to "
                      "the test that needs the most. Tests started with "
                      "{{sched.run_cmd}} will start with the right number of nodes."
                      "Tests are run one at a time within the allocation. This is "
                      "great for large tests over a many/all nodes, especially on "
                      "large systems where node setup/cleanup takes a while."),
        yc.StrElem(
            'tasks',
            help_text="The total number of tasks to run, across all nodes. How this "
                      "interacts with 'tasks_per_node' is scheduler dependent. Under "
                      "slurm, tasks_per_node becomes the maximum tasks per node."),
        yc.StrElem(
            'tasks_per_node',
            help_text="The number of tasks to start per node. This can be"
                      "an integer, the keyword 'all', or a percentage."
                      "'all' will create a number of tasks per node equal "
                      "to the CPUs for the node with the least CPUs in the "
                      "selected nodes. A percentage will create a task "
                      "for that percentage of the 'all', rounded down (min 1)."),
        yc.StrElem(
            'min_tasks_per_node',
            help_text="A minimum number of tasks per node. Must be an integer (or undefined),"
                      "This will take precedence over 'tasks_per_node' if it is larger than that "
                      "value after it is calculated."),
        yc.StrElem(
            'partition',
            help_text="The partition to run the test on."),
        yc.StrElem(
            'qos',
            help_text="The QOS to use when creating an allocation."),
        yc.StrElem(
            'account',
            help_text="The account to use when creating an allocation."),
        yc.StrElem(
            'wrapper',
            help_text="Wrapper for the scheduler command."),
        yc.StrElem(
            'reservation',
            help_text="The reservation to use when creating an allocation. When blank "
                      "nodes in reservations are filtered. Use the keyword 'any' to "
                      "select nodes regardless of reservation."),
        yc.StrElem(
            'time_limit',
            help_text="The job time limit in hours. It is assumed that this is used to "
                      "increase time the time limit beyond the cluster default. "
                      "Tests that share an allocation share the largest given time "
                      "limit."),
        yc.ListElem(
            'across_nodes',
            sub_elem=yc.StrElem(),
            help_text="Only nodes in this list are considered when running a test. "
                      "Each listed node may be a node range as per 'exclude_nodes'. "
                      "Nodes in this may also be 'included' (in each chunk) or "
                      "'excluded'."),
        yc.ListElem(
            'include_nodes',
            sub_elem=yc.StrElem(),
            help_text="Nodes to always include in every allocation on which this test "
                      "runs. Each listed node may be a node range, as per "
                      "'exclude_nodes'. "
                      "In advanced schedulers, these nodes are added to every "
                      "chunk."),
        yc.ListElem(
            'exclude_nodes',
            sub_elem=yc.StrElem(),
            help_text="Nodes to exclude. Each given node can contain a range in "
                      "square brackets, in which case all nodes in that range "
                      "will be excluded. Numbers in expanded ranges are zero "
                      "padded to the length of the longest number, so "
                      "'node[9-11]' -> node09, node10, node11."),
        yc.KeyedElem(
            'chunking',
            help_text="Options in this section control how the machine is divided into "
                      "'chunks' of nodes.",
            elements=[
                yc.StrElem(
                    'size',
                    help_text="Divide the allocation into chunks of this many nodes."
                              "A variable 'sched.chunks' will hold a list of "
                              "these chunks that can be permuted over in the test "
                              "config. No values or 0 sets the chunk size to include "
                              "all nodes."),
                yc.StrElem(
                    'node_selection',
                    default='contiguous',
                    help_text="Determines how Pavilion chooses nodes for each chunk. "
                              "Chunks generally won't overlap, and can run "
                              "simultaneously."
                              " 'contiguous' - Try to use adjacent nodes. \n"
                              " 'random' - Randomly select nodes. \n"
                              " 'distributed' - Choose approximately every nth node.\n"
                              " 'rand_dist' - Randomly select from nth group of "
                              "nodes.\n"),
                yc.StrElem(
                    'extra',
                    help_text="What to do with extra nodes that don't fit in a chunk.\n"
                              "Options are:\n"
                              " 'backfill (default) - The extra nodes will be padded "
                              " out with nodes from the last chunk.\n"
                              " 'discard' - Don't use the extra nodes.\n"),
            ]
        ),
        yc.KeyedElem(
            'cluster_info',
            help_text="Defaults and node information for clusters that have "
                      "schedulers that don't support auto-detection. "
                      "Auto-detection always overrides these values.",
            elements=[
                yc.StrElem(
                    'node_count',
                    help_text="Number of nodes on the system, if all nodes "
                              "were up."),
                yc.StrElem(
                    'mem',
                    help_text="The amount of memory per node, in bytes."),
                yc.StrElem(
                    'cpus',
                    help_text="CPUS per node."),
            ]
        ),
        yc.KeyedElem(
            'mpirun_opts',
            help_text="Config elements for MPI-related options.",
            elements=[
                yc.StrElem(
                    name='bind_to',
                    help_text="MPIrun --bind-to option. See `man mpirun`"
                ),
                yc.StrElem(
                    name='rank_by',
                    help_text="MPIrun --rank-by option. See `man mpirun`"
                ),
                yc.ListElem(
                    name='mca', sub_elem=yc.StrElem(),
                    help_text="MPIrun mca module options (--mca). See `man mpirun`"
                ),
                yc.ListElem(
                    name='extra', sub_elem=yc.StrElem(),
                    help_text="Extra arguments to add to mpirun commands."
                )
            ]
        )
    ]

    def __init__(self):
        super().__init__(
            'schedule', elements=self.ELEMENTS,
            help_text="This section describes how to schedule a test. Schedulers are "
                      "divided into 'basic' and 'advanced' types, and not all "
                      "options apply to both. Additionally, individual schedulers "
                      "may not support some options regardless of type. In general, "
                      "an option isn't supported, it is ignored.")

    @classmethod
    def add_subsection(cls, sched_section):
        """Use this method to add scheduler specific subsections to the config.

        :param yc.ConfigElem sched_section: A yaml config element to add. Keyed
            elements are expected, though any ConfigElem based instance
            (whose leave elements are StrElems) should work.
        """

        if not isinstance(sched_section, yc.ConfigElement):
            raise RuntimeError("Tried to add a subsection to the config, but it "
                               "wasn't a yaml_config ConfigElement instance (or "
                               "an instance of a ConfigElement child class).\n"
                               "Got: {}".format(sched_section))

        name = sched_section.name

        names = [el.name for el in cls.ELEMENTS]

        if name in names:
            raise RuntimeError("Tried to add a subsection to the config called "
                               "{0}, but one already exists.".format(name))

        try:
            cls.check_leaves(sched_section)
        except ValueError as err:
            raise ValueError("Tried to add result parser named '{}', but "
                             "leaf element '{}' was not string based."
                             .format(name, err.args[0]))

        cls.ELEMENTS.append(sched_section)

    @classmethod
    def remove_subsection(cls, subsection_name):
        """Remove a subsection from the config. This is really only for use
        in plugin deactivate methods."""

        for section in list(cls.ELEMENTS):
            if subsection_name == section.name:
                cls.ELEMENTS.remove(section)
                return

    @classmethod
    def check_leaves(cls, elem):
        """Make sure all of the config elements have a string element or
        equivalent as the final node.

        :param yc.ConfigElement elem:
        """

        # pylint: disable=protected-access

        if hasattr(elem, 'config_elems'):
            for sub_elem in elem.config_elems.values():
                cls.check_leaves(sub_elem)
        elif hasattr(elem, '_sub_elem') and elem._sub_elem is not None:
            cls.check_leaves(elem._sub_elem)
        elif issubclass(elem.type, str):
            return
        else:
            raise ValueError(elem)


class SchedConfigError(ValueError):
    """Raised when there's a problem with the scheduler configuration."""


def min_int(name, min_val, required=True):
    """Return a callback that ensures the argument >= min_val. If not required,
    an empty value will return None."""

    def validator(val):
        """Validate that val > min_val"""

        val = val.strip()

        if not required and val in (None, ''):
            return None

        try:
            val = int(val)
        except ValueError:
            raise SchedConfigError(
                "Invalid value for '{}'. Got '{}'. Must be an integer."
                .format(name, val))

        if val < min_val:
            raise SchedConfigError(
                "Invalid value for '{}'. Got '{}'. Must be greater than or "
                "equal to {}.".format(name, val, min_val))

        return val

    return validator


def validate_list(val) -> List[str]:
    """Ensure that a list is a list."""

    if val is None:
        return []

    if isinstance(val, list):
        return val

    raise ValueError("Expected list, got {}".format(val))


def _validate_nodes(val) -> Union[float, int, None]:
    """Parse and check the nodes (or min_nodes) value. A float value
    represents a percentage of nodes, ints are an exact node count. None denotes
    that no value was given."""

    if val is None:
        return None
    elif val == 'all':
        val = 1.0
    elif val.endswith('%'):
        try:
            val = float(val[:-1])/100.0
        except ValueError:
            raise SchedConfigError(
                "Invalid percent value. Got '{}'."
                .format(val))
    else:
        try:
            val = int(val)
        except ValueError:
            raise SchedConfigError(
                "Invalid node count value. Got '{}'.".format(val))

    return val


def _validate_tasks_per_node(val) -> Union[int, float]:
    """This accepts a positive integer, a percentage, or the keywords 'all' and
    'min'. All translates to 100%, and min to an integer 1."""

    val = val.strip()

    if val == 'all':
        return 1.0
    if val == 'min':
        return 1

    if val.endswith('%'):
        try:
            val = float(val[:-1])/100.0
        except ValueError:
            raise SchedConfigError("Invalid tasks_per_node % value: {}".format(val))
    else:
        try:
            val = int(val)
        except ValueError:
            raise SchedConfigError("Invalid tasks_per_node value: {}".format(val))

    if val <= 0:
        raise SchedConfigError("tasks_per_node must be more than 0, got '{}'"
                               .format(val))

    return val


def parse_node_range(node: str) -> List[str]:
    """Parse a node range and return the list of nodes that it represents.

    Node ranges are text with a single numeric range in brackets. Text before
    the brackets are prepended as a suffix, and text after the brackets are
    appended as a suffix. All numbers in the range are padded out with zeros
    to the longer of the numbers.

    Examples:
    - 'node[5-200]b' -> ['node005b', 'node006b', ...]
    - 'node0[5-9]' -> ['node05', 'node06', ...]
    - 'node123' -> ['node123']

    :param node: The node range to parse.
    :return:
    """

    range_start = range_end = None
    if '[' in node:
        range_start = node.index('[')
    if ']' in node:
        range_end = node.index(']')

    if range_start is None and range_end is None:
        # No range in node text
        return [node]
    elif range_start is None:
        raise ValueError("Missing closing bracket on node range.")
    elif range_end is None:
        raise ValueError("Missing open bracket on node range.")

    if node.count('[') > 1:
        raise ValueError("Node names can only contain a single open bracket '[': "
                         "'{}'".format(node))
    if node.count(']') > 1:
        raise ValueError("Node names can only contain a single closing "
                         "bracket '[': '{}'".format(node))

    prefix = node[:range_start]
    suffix = node[range_end + 1:]

    range_txt = node[range_start +1 :range_end]
    if '-' not in range_txt:
        raise ValueError("Range in node range missing '-': {}".format(node))
    start, end = range_txt.split('-', 1)
    digits = max(len(start), len(end))
    try:
        start = int(start)
    except ValueError:
        raise ValueError("Invalid start value for node range '{}': {}"
                         .format(node, start))
    try:
        end = int(end)
    except ValueError:
        raise ValueError("Invalid end value for node range '{}': {}"
                         .format(node, end))

    if end <= start:
        raise ValueError("Invalid node range '{}'. Range start must be less than "
                         "its end. Got {} - {}.".format(node, start, end))

    if end < 0:
        raise ValueError("Negative end value (probably an extra '-' in node range "
                         "'{}'.".format(node))

    nodes = []
    for i in range(start, end+1):
        nodes.append(''.join([
            prefix,
            '{:0{digits}d}'.format(i, digits=digits),
            suffix]))

    return nodes


def _validate_node_list(items) -> List[str]:
    """Validate a list of node ranges, returning the combined list of nodes."""

    nodes = []

    if isinstance(items, str):
        items = [items]

    for item in items:
        nodes.extend(parse_node_range(item))

    return nodes

def _validate_allocation_str(val) -> Union[str, None]:
    """Validates string and returns true, false or max for the share_allocation feature"""

    if isinstance(val, str):
        if val.lower() == 'false':
            return False
        elif val.lower() == 'max':
            return val.lower()
        else:
            return True
    else:
        return True


CONTIGUOUS = 'contiguous'
RANDOM = 'random'
DISTRIBUTED = 'distributed'
RAND_DIST = 'rand_dist'
NODE_SELECT_OPTIONS = (CONTIGUOUS, RANDOM, DISTRIBUTED, RAND_DIST)

DISCARD = 'discard'
BACKFILL = 'backfill'
NODE_EXTRA_OPTIONS = (DISCARD, BACKFILL)

UP = 'up'
AVAILABLE = 'available'
NODE_STATE_OPTIONS = [UP, AVAILABLE]

# This is a dictionary of key -> callback/val_list/dict/None pairs. A callback will be
# called to perform a type conversion on each entry, and to validate those values.
# A tuple will trigger a check to ensure the value is one of the items.
# None - no normalization will occur - the value will be a string or None.
# A dict will cause the items within to be validated in the same way.
CONFIG_VALIDATORS = {
    'nodes':            _validate_nodes,
    'min_nodes':        _validate_nodes,
    'chunking':         {
        'size':           _validate_nodes,
        'node_selection': NODE_SELECT_OPTIONS,
        'extra':          NODE_EXTRA_OPTIONS,
    },
    'tasks_per_node':   _validate_tasks_per_node,
    'tasks':            min_int('tasks', min_val=1, required=False),
    'min_tasks_per_node': min_int('min_tasks_per_node', min_val=1, required=False),
    'node_state':       NODE_STATE_OPTIONS,
    'partition':        None,
    'qos':              None,
    'account':          None,
    'core_spec':        None,
    'wrapper':          None,
    'reservation':      None,
    'across_nodes':     _validate_node_list,
    'include_nodes':    _validate_node_list,
    'exclude_nodes':    _validate_node_list,
    'share_allocation': _validate_allocation_str,
    'time_limit':       min_int('time_limit', min_val=1),
    'cluster_info':     {
        'node_count':   min_int('cluster_info.node_count', min_val=1, required=False),
        'mem':          min_int('cluster_info.mem', min_val=1, required=False),
        'cpus':         min_int('cluster_info.cpus', min_val=1, required=False)
    },
    'mpirun_opts':      {
        'bind_to': MPIRUN_BIND_OPTS,
        'rank_by': MPIRUN_BIND_OPTS,
        'mca': validate_list,
        'extra': validate_list
    }
}

CONFIG_DEFAULTS = {
    'nodes':            None,
    'min_nodes':        None,
    'chunking':         {
        'size':           '0',
        'node_selection': CONTIGUOUS,
        'extra':          BACKFILL,
    },
    'tasks_per_node':   '1',
    'min_tasks_per_node': None,
    'tasks': None,
    'node_state':       UP,
    'partition':        None,
    'qos':              None,
    'account':          None,
    'wrapper':          None,
    'reservation':      None,
    'share_allocation': True,
    'across_nodes':     [],
    'include_nodes':    [],
    'exclude_nodes':    [],
    'time_limit':       '1',
    'cluster_info':     {
        'node_count': '1',
        'mem':        '1000',
        'cpus':       '4',
    },
    'mpirun_opts':      {
        'mca': [],
        'extra': []
    }
}


def validate_config(config: Dict[str, str]):
    """Validate the scheduler config using the validator dict.

    :param config: The configuration dict to validate. Expected to be the result
        of parsing with the above yaml_config parser."""

    val_config = _validate_config(config)

    # Flex scheduling is when the scheduler picks the nodes, which can't happen if we're using
    # chunking or have a limited set of nodes.
    val_config['flex_scheduled'] = (val_config['chunking']['size'] in (0, None)
                                    and not val_config['across_nodes'])

    return val_config


def _validate_config(config: Dict[str, str],
                    validators: Dict[str, Any] = None,
                    defaults: Dict[str, Any] = None) -> Dict[str, Any]:
    """Validate the scheduler config using the validator dict.

    :param config: The configuration dict to validate. Expected to be the result
        of parsing with the above yaml_config parser.
    :param validators: The validator dictionary, as defined above.
    :param defaults: A dict of defaults for the config keys.
    :raises SchedConfigError: On any errors.
    """

    if validators is None:
        validators = CONFIG_VALIDATORS

    if defaults is None:
        defaults = CONFIG_DEFAULTS

    config = config.copy()
    normalized_config = {}

    for key, validator in validators.items():
        value = None
        if key in config:
            value = config.get(key)
            del config[key]

        if value is None or value == []:
            value = defaults.get(key, None)

        if value is None:
            normalized_config[key] = None

        elif callable(validator):
            try:
                normalized_config[key] = validator(value)

            except ValueError as err:
                raise SchedConfigError("Config value for key '{}' had a validation "
                                       "error.".format(key), err)

        elif isinstance(validator, (tuple, list)):
            if value not in validator:
                raise SchedConfigError(
                    "Config value for key '{}' was expected to be one of '{}'. "
                    "Got '{}'.".format(key, validator, value))
            normalized_config[key] = value
        elif isinstance(validator, dict):
            if value is None:
                value = {}
            normalized_config[key] = _validate_config(
                config=value,
                validators=validator,
                defaults=defaults[key])
        elif validator is None:
            normalized_config[key] = value

        else:
            raise RuntimeError("Invalid validator: '{}'".format(validator))

    return normalized_config


def calc_node_range(sched_config, node_count) -> Tuple[int, int]:
    """Calculate a node range for the job given the min_nodes and nodes, and
    the number of nodes available (for percentages. Returns the calculated min and max.
    The max_nodes may be undefined (None), but the minimum nodes is always at least 1.
    """

    nodes = sched_config['nodes']
    min_nodes = sched_config['min_nodes']
    tasks = sched_config['tasks']

    # If we're not defining the allocation by purely tasks, set a node count of 1.
    if tasks is None and nodes is None:
        nodes = 1

    if isinstance(nodes, float):
        nodes = max(math.ceil(nodes * node_count), 1)

    if min_nodes in (None, 0):
        min_nodes = nodes
    elif isinstance(min_nodes, float):
        min_nodes = max(math.ceil(min_nodes * node_count), 1)

    if min_nodes is None:
        min_nodes = 1

    return min_nodes, nodes
