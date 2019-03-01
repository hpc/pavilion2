import collections
from pavilion.variables import VariableSetManager
from yapsy import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class SchedulerPluginError(RuntimeError):
    pass

_SCHEDULER_PLUGINS = None
_LOADED_PLUGINS = None
_SCHEDULER_VARIABLES = None

SCHEDULER_VARS = {
    'scheduler_plugin': 'The scheduler plugin being used to fetch values.',
    'num_nodes': 'The node count for this test.',
    'procs_per_node': 'Min procs per node for this test.',
    'mem_per_node': 'Min memory '
}

class SchedVarDict(collections.UserDict):

    def __init__(self, sched_plugin=None):

        global _SCHEDULER_VARIABLES
        global _SCHEDULER_VARS
        if _SCHEDULER_VARIABLES is not None:
            raise SchedulerPluginError(
                 "Dictionary of scheduler variables can't be generated twice.")
        super().__init__({})
        _SCHEDULER_VARIABLES = self

        if sched_plugin is None:
            raise SchedulerPluginError("A scheduler must be provided.")
        else:
            _SCHEDULER_VARIABLES['scheduler_plugin'] = sched_plugin

    def __getitem__(self, key):

        if key in self.SCHEDULER_VARS:
            if key not in self.data:
                self.data[key] = \
                               self.data['scheduler_plugin'].getattr(self, key)
            return self.data[key]
        else:
            raise KeyError("Scheduler var '{}' not available for scheduler '{}'"
                           .format(key, self.__class__.__name__))

    def _reset(self):
        LOGGER.warning("Resetting the plugins.  This functionality exists " +\
                        "only for use by unittests.")
        _reset_plugins()
        self.data = {}


def _reset_plugins():
    global _SCHEDULER_PLUGINS

    if _SCHEDULER_PLUGINS is not None:
        for key in list(_SCHEDULER_PLUGINS.keys()):
            remove_system_plugins(key)

def add_scheduler_plugin(scheduler_plugin):
    global _SCHEDULER_PLUGINS
    name = scheduler_plugin.name

    if _LOADED_PLUGINS is None:
        _LOADED_PLUGINS = {}

    if name not in _LOADED_PLUGINS:
        _LOADED_PLUGINS[name] = scheduler_plugin
    elif scheduler_plugin.priority > _LOADED_PLUGINS[name].priority:
        _LOADED_PLUGINS[name] = scheduler_plugin
        LOGGER.warning("Scheduler plugin {} replaced due to priority".format(
                        name))
    elif priority < _LOADED_PLUGINS[name].priority:
        LOGGER.warning("Scheduler plugin {} ignored due to priority".format(
                        name))
    elif priority == _LOADED_PLUGINS[name].priority:
        raise SchedulerPluginError("Two plugins for the same system plugin "
                                "have the same priority {}, {}."
                                .format(scheduler_plugin,
                                        _LOADED_PLUGINS[name]))

def remove_scheduler_plugin(scheduler_plugin):
    global _SCHEDULER_PLUGINS
    name = scheduler_plugin.name

    if name in _SCHEDULER_PLUGINS:
        del _SCHEDULER_PLUGINS[name]

def get_scheduler_plugin(name):
    global _LOADED_PLUGINS

    if _LOADED_PLUGINS is None:
        raise SchedulerPluginError(
                               "Trying to get plugins before they are loaded.")

    if name not in _LOADED_PLUGINS:
        raise SchedulerPluginError("Module not found: '{}'".format(name))

    return _LOADED_PLUGINS[name]

class SchedulerPlugin(IPlugin.IPlugin):

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, name, priority=PRIO_DEFAULT):
        """Scheduler plugin that is expected to be overriden by subclasses.
        The plugin will populate a set of expected 'sched' variables."""

        super().__init__()

        self.logger = logging.getLogger('sched.' + name)
        self.name = name
        self.priority = priority
        self.values = {}
        for var in _SCHEDULER_VARS:
            self.values[var] = None

#    def _get(self, var):
#        raise NotImplemented
#
#    def get(self, var):
#        global _SCHEDULER_VARS
#
#        if var not in _SCHEDULER_VARS:
#            raise SchedulerPluginError("Requested variable {}".format(var)+\
#                              " not in the expected list of variables.")
#
#        if self.values[var] is None:
#            val = self._get(var)
#
#            ge_set = ['num_nodes', 'down_nodes', 'unused_nodes', 'busy_nodes',
#                       'maint_nodes', 'other_nodes', 'chunk_size']
#            if var in ge_set and val < 0:
#                raise SchedulerPluginError("Value for '{}' ".format(var) +\
#                                            "must be greater than or equal " +\
#                                            "to zero.  Received '{}'.".format(
#                                            val))
#            if var == 'procs_per_node' and val <= 0:
#                raise SchedulerPluginError("Value for 'procs_per_node' " +\
#                                            "must be greater than zero.  " +\
#                                            "Received '{}'.".format(val))
#
#            self.values[var] = val
#
#        return self.values[var]
#
#    def set(self, var, val):
#        global _SCHEDULER_VARS
#
#        if var not in _SCHEDULER_VARS:
#            raise SchedulerPluginError("Specified variable {}".format(var)+\
#                                    " not in the expected list of variables.")
#
#        if var in ['down_nodes', 'unused_nodes', 'busy_nodes', 'maint_nodes',
#                    'other_nodes']:
#            raise SchedulerPluginError("Attempting to set a variable that" + \
#                                        " is not meant to be set by the " + \
#                                        "user.  Variable: {}.".format(var))
#
#        if self.values[var] is not None:
#            logger.warning("Replacing value for {} from ".format(var) + \
#                            "{} to {}.".format(self.values[var], val))
#
#        self.values[var] = val

    def check_request(self, patition, state, min_nodes, max_nodes,
                       min_ppn, max_ppn, req_type):
        """Function intended to be overridden for the particular schedulers.
           :param str partition - Name of the desired partition.
           :param str state - State of the desired partition.
           :param int min_nodes - Minimum number of nodes requested.
           :param int,str max_nodes - Maximum number of nodes requested.
                                      Can be 'all'.
           :param int min_ppn - Minimum number of processors per node requested
           :param int,str max_ppn - Maximum number of processors per node
                                    requested.  Can be 'all'.
           :param str req_type - Type of request.  Options include 'immediate'
                                 and 'wait'.  Specifies whether the request
                                 must be available immediately or if the job
                                 can be queued for later.
           :return tuple(int, int) - Tuple containing the number of nodes that
                                      can be used and the number of processors
                                      per node that can be used.
        """
        raise NotImplemented

    def get_script_headers(self, partition=None, reservation=None, qos=None,
                            account=None, num_nodes=None, ppn=None,
                            time_limit=None):
        """Function to take a series of resource requests and return the list
           of lines used to specify this request in a submissions script.
           :param str partition - Name of the partition.
           :param str reservation - Name of the reservation.
           :param str qos - Name of the qos to use.
           :param str account - Name of the account to use.
           :param int nodes - Number of nodes.
           :param int ppn - Number of processors per node.
           :param time time - Time requested.
           :return list(str) - List of lines to go at the beginning of a
                               submissions script to request the variables.
        """
        raise NotImplemented

    def submit_job(self, path):
        """Function to submit a job to a scheduler and return the job ID
           number.
           :param str path - Path to the submission script.
           :return str - Job ID number.
        """
        raise NotImplemented

    def check_job(self, id, key):
        """Function to check the status of a job.
           :param str id - ID number of the job as returned by submit_job().
           :param str key - Optional parameter to request a specific value
                            from the scheduler job information.
           :return str - Status of the job matching the provided job ID.
                         If the key is empty or requesting the state of the
                         job, the return values should be 'pending', 'running',
                         'finished', or 'failed'.
        """
        raise NotImplemented

    def check_reservation(self, res_name):
        """Function to check that a reservation is valid.
           :param str res_name - Reservation to check for validity.
           :raises SchedulerPluginError - If the reservation is not valid.
        """
        raise NotImplemented

    def check_partition(self, partition):
        """Function to check that a partition is valid.
           :param str partition - Partition to check for validity.
           :raises SchedulerPluginError - If the partition is not valid.
        """
        raise NotImplemented

    def kick_off(self, test_obj):
        """Function to accept a test object and kick off a build."""
        raise NotImplemented

    def _kick_off(self, partition=None, reservation=None, qos=None,
                  account=None, num_nodes=1, ppn=1, time_limit=None,
                  line_list=None):
        """Function to accept a list of lines and generate a script that is
           then submitted to the scheduler.
        """
        raise NotImplemented

    def resolve_request(self, request):
        """Function to resolve the request for resources against the available
           resources.  This should always be run inside of an allocation."""
        raise NotImplemented

    def activate(self):
        """Add this plugin to the system plugin list."""
        add_scheduler_plugin(self)

    def deactivate(self):
        """Remove this plugin from the system plugin list."""
        remove_scheduler_plugin(self)

    def __reset():
        """Remove this plugin and its changes."""
        self.values = None
        self.deactivate()
