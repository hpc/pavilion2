"""Functions and definitions relating to scheduler configuration in tests."""

from typing import Any, Dict, Union
from pavilion import utils

import yaml_config as yc

SCHEDULE_CONFIG = yc.KeyedElem(
    'schedule',
    help_text="This section describes how to schedule a test. Note that some "
              "options won't be available for all schedulers, in which case "
              "they will be ignored. Scheduler specific sub-sections, such as "
              "'slurm', include additional options specific to that scheduler.",
    elements=[
        yc.StrElem(
            'num_nodes',
            default='1',
            help_text="The number of nodes to acquire to scheduler the job as "
                      "whole. This may be a number, a percentage, "
                      "or the keyword 'all'. In all cases, this limit is applied "
                      "after chunking, so 'all' when the chunk_size is 1000 will be "
                      "1000 nodes. A single node is both the default and "
                      "minimum selection."),
        yc.StrElem(
            'min_nodes',
            help_text="The minimum number of nodes to allocate. When chunking is "
                      "used, this does nothing as we always schedule the max "
                      "nodes if we can. For schedulers that can't use chunking, "
                      "this will be used (on schedulers that support it) to give "
                      "the scheduler a reasonable minimum. Uses the same format "
                      "as num_nodes."),
        yc.StrElem(
            'node_state',
            help_text="Filter nodes based on their current state. Options are "
                      "'up' (default) or 'available'. 'Up' counts/includes only nodes "
                      "in allocations that are usable regardless of current allocation "
                      "status. Available nodes are up, and also not currently "
                      "allocated."),
        yc.StrElem(
            'chunk_node_selection',
            default='contiguous',
            help_text="Determines how Pavilion chooses nodes. Selections of a "
                      "given type attempt to create independent allocations "
                      "so jobs may run simultaneously.\n"
                      " 'contiguous' - Try to use adjacent nodes. \n"
                      " 'random' - Randomly select nodes. \n"
                      " 'distributed' - Choose approximately every nth node.\n"
                      " 'rand_dist' - Randomly select from nth group of "
                      "nodes.\n"),
        yc.StrElem(
            'chunk_size',
            help_text="Divide the allocation into chunks of at most this "
                      "size. A variable 'sched.chunks' will hold a list of "
                      "these chunks that can be permuted over in the test "
                      "config. No values or 0 sets the chunk size to include "
                      "all nodes."),
        yc.StrElem(
            'chunk_extra',
            help_text="What to do with extra nodes that don't fit in a chunk.\n"
                      "Options are:\n"
                      " 'keep' - Just put the extras in a chunk of their own, "
                      "regardless of how many there are.\n"
                      " 'discard' - Don't use the extras.\n"
                      " 'distribute' - Distribute the extras amongst other "
                      "chunks, effectively increasing the chunk size.\n"
                      " 'auto (default) - If distributing won't increase chunk "
                      "size by more than 10%, then do that. Otherwise, "
                      "'keep' them."),
        yc.StrElem(
            'share_allocation',
            default='True',
            help_text="If true, share the allocation with other tests in the same "
                      "chunk. The allocation will have a number of nodes equal to "
                      "the test that needs the most. Tests started with "
                      "{{sched.run_cmd}} will start with the right number of nodes."
                      "Tests are run one at a time within the allocation. This is "
                      "great for large tests over a many/all nodes, especially on "
                      "large systems where node setup/cleanup takes a while."),
        yc.StrElem(
            'tasks_per_node',
            default='1',
            help_text="The number of tasks to start per node. This can be"
                      "an integer, the keyword 'all' or 'min', or a percentage."
                      "The 'all' keyword will create a "
                      "number of tasks equal to the number of CPUs across all "
                      "nodes. Min will create a number of tasks per node equal "
                      "to the CPUs for the node with the least CPUs in the "
                      "selected partition. A percentage will create a task "
                      "for that percentage of the 'min', rounded down."),
        yc.StrElem(
            'partition',
            default='standard',
            help_text="The partition to run the test on."),
        yc.StrElem(
            'qos',
            help_text="The QOS to use when creating an allocation."),
        yc.StrElem(
            'account',
            help_text="The account to use when creating an allocation."),
        yc.StrElem(
            'reservation',
            help_text="The reservation to use when creating an allocation."),
        yc.StrElem(
            'time_limit',
            default='1',
            help_text="The job time limit in hours. It is assumed that this is used to "
                      "increase time the time limit beyond the cluster default. "
                      "Tests that share an allocation share the largest given time "
                      "limit."),
        yc.StrElem(
            'include_nodes',
            help_text="Nodes to always include in every allocation on which this test "
                      "runs. This nodes will be added to each chunk, which means none "
                      "of the chunks may run simultaneously. The format is a comma"
                      "separated list of nodes, with ranges specified in brackets. IE"
                      "node00[5-9] denotes node005, node006, up to node009. When "
                      "chunking isn't available, the nodes will simply be included "
                      "via the scheduler."),
        yc.StrElem(
            'exclude_nodes',
            help_text="Nodes to exclude. These nodes won't be available for node "
                      "selection when chunking, and will be excluded via the "
                      "scheduler if chunking is unavailable."),
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
        )
    ],
)


class SchedConfigError(ValueError):
    """Raised when there's a problem with the scheduler configuration."""


def int_greater_than(name, min_val, required=True):
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

    return validator


def validate_num_nodes(val) -> Union[float, int]:
    """Parse and check the num_nodes (or min_nodes) value. A float value
    represents a percentage of nodes, ints are an exact node count. None denotes
    that no value was given."""

    if val is None:
        pass
    elif val == 'all':
        val = 1.0
    elif val.endswith('%'):
        try:
            val = float(val[:-1])/100.0
        except ValueError:
            raise SchedConfigError(
                "Invalid percent value in num_nodes. Got '{}'."
                .format(val))
    else:
        try:
            val = int(val)
        except ValueError:
            raise SchedConfigError(
                "Invalid value in num_nodes. Got '{}'.".format(val))

    return val


def validate_tasks_per_node(val) -> Union[int, float]:
    """This accepts a positive integer, a percentage, or the keywords 'all' and
    'min'. All translates to 100%, and min to an integer 0."""

    val = val.strip()

    if val == 'all':
        return 1.0
    if val == 'min':
        return 0

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

    if val < 0:
        raise SchedConfigError("tasks_per_node must be more than 0, got '{}'"
                               .format(val))


CONTIGUOUS = 'contiguous'
RANDOM = 'random'
DISTRIBUTED = 'distributed'
RAND_DIST = 'rand_dist'
NODE_SELECT_OPTIONS = (CONTIGUOUS, RANDOM, DISTRIBUTED, RAND_DIST)

DISCARD = 'discard'
BACKFILL = 'backfill'
NODE_EXTRA_OPTIONS = (DISCARD, BACKFILL)

# This is a dictionary of key -> callback/val_list/dict/None pairs. A callback will be
# called to perform a type conversion on each entry, and to validate those values.
# A tuple will trigger a check to ensure the value is one of the items.
# None - no normalization will occur - the value will be a string or None.
# A dict will cause the items within to be validated in the same way.
CONFIG_NORMALIZE = {
    'num_nodes': validate_num_nodes,
    'min_nodes': validate_num_nodes,
    'chunk_node_selection': NODE_SELECT_OPTIONS,
    'chunk_size': int_greater_than('chunk_size', min_val=0),
    'chunk_extra': NODE_EXTRA_OPTIONS,
    'tasks_per_node': validate_tasks_per_node,
    'partition': None,
    'qos': None,
    'account': None,
    'reservation': None,
    'share_allocation': utils.str_bool,
    'time_limit': int_greater_than('time_limit', min_val=1),
    'cluster_info': {
        'node_count': int_greater_than('cluster_info.node_count',
                                       min_val=1, required=False),
        'mem': int_greater_than('cluster_info.mem', min_val=1, required=False),
        'cpus': int_greater_than('cluster_info.cpus', min_val=1, required=False)
    }
}


def validate_config(config: Dict[str, str],
                    validators: Dict[str, Any] = None) -> Dict[str, Any]:
    """Validate the scheduler config using the validator dict.

    :param config: The configuration dict to validate. Expected to be the result
        of parsing with the above yaml_config parser.
    :param validators: The validator dictionary, as defined above.
    :raises SchedConfigError: On any errors.
    """

    if validators is None:
        validators = CONFIG_NORMALIZE

    config = config.copy()
    normalized_config = {}

    for key, validator in validators:
        if key in config:
            value = config.get(key)
            del config[key]
        else:
            value = None

        if callable(validator):
            normalized_config[key] = validator(value)

        elif isinstance(validator, (tuple, list)):
            if value not in validator:
                raise SchedConfigError(
                    "Config value for key '{}' was expected to be one of '{}'. "
                    "Got '{}'.".format(key, validator, value))
            normalized_config[key] = value

        elif validator is None:
            normalized_config[key] = value

        else:
            raise RuntimeError("Invalid validator: '{}'".format(validator))

    return normalized_config
