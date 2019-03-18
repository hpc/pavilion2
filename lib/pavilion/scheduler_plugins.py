import collections
from pavilion.variables import VariableSetManager
from yapsy import IPlugin
import logging

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

    # Suggested scheduler variables.
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
    """
    :cvar NAME: The name of this plugin, and it's corresponding config section.
    """

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, priority=PRIO_DEFAULT):
        """Scheduler plugin that is expected to be overriden by subclasses.
        The plugin will populate a set of expected 'sched' variables."""

        super().__init__()

        self.conf = None
        self.logger = logging.getLogger('sched.' + name)
        self.name = name
        self.priority = priority
        self.values = {}
        for var in _SCHEDULER_VARS:
            self.values[var] = None

    def _check_request(self, *args, **kwargs):
        """Function intended to be overridden for the particular schedulers."""
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

        config = test_obj.config[self.name]

        kick_off_path = self._write_kick_off_script(test_obj.path, test_obj.run_cmd(), **config)

        test_obj.job_id = self.submit_job(kick_off_path)

        test_obj.status.set(test_obj.status.STATES.SCHEDULED,
                            "Test {} has job ID {}.".format(self.name, test_obj.job_id))

    def _write_kick_off_script(self, test_path, run_cmd, **kwargs):
        """Function to accept a list of lines and generate a script that is
           then submitted to the scheduler.
        """
        raise NotImplemented

    def resolve_request(self, request):
        """Function to resolve the request for resources against the available
           resources.  This should always be run inside of an allocation."""
        if name not in self.values and name != 'scheduler_plugin':
            raise SchedulerPluginError("'{}' not a resolvable request."
                                       .format(name))

        request_min = 1
        request_max = 1
        # Parse the request format
        if '-' in request:
            request_split = request.split('-')
            request_min = request_split[0]
            request_max = request_split[1]

        # Use scheduler-specific method of determining available resources.
        # Number of nodes is based on the SLURM_JOB_NUM_NODES environment
        # variable, which is populated by Slurm when inside of an allocation.
        if name == 'num_nodes':
            request_avail = self._get_num_nodes()
        elif name == 'procs_per_node':
            request_avail = self._get_min_ppn()
        elif name == 'mem_per_node':
            request_avail = self._get_mem_per_node()

        # The value should only be none if the environment variable was not
        # defined.
        if request_avail is None:
            raise SchedulerPluginError(
                           "Resolving requests for '{}' requires an allocation"
                           .format(name))

        # Determine if the request can be met and return the appropriate value.
        if request_avail < request_min:
            raise SchedulerPluginError(
                 "Available {} '{}' is less than minimum requested nodes '{}'."
                 .format(name, request_avail, request_min))
        elif request_avail < request_max:
            return request_avail
        else:
            return request_max

    def _get_num_nodes(self):
        """Scheduler-specific method of determining the number of nodes
           available from inside of an allocation."""
        raise NotImplemented

    def _get_node_list(self):
        """Scheduler-specific method of determining a list of all nodes in an
           allocation from inside of the allocation."""
        raise NotImplemented

    def _get_min_ppn(self, node_list=None):
        """Scheduler-specific method of determining the greatest number of
           processors common to all nodes in an allocation from inside of that
           allocation."""
        raise NotImplemented

    def _get_tot_procs(self, node_list=None):
        """Scheduler-specific method of determining the total number of
           processes that can run in an allocation from inside of that
           allocation."""
        raise NotImplemented

    def _get_mem_per_node(self, node_list=None):
        """Scheduler-specific method of determining the maximum amount of
           free memory common across all nodes in an allocation from inside
           that allocation."""

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
