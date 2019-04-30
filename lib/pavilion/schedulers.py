from pavilion.test_config.variables import DeferredVariable
from pavilion import scriptcomposer
from pavilion.test_config import format
from yapsy import IPlugin
from functools import wraps
from pathlib import Path
import collections
import logging
import subprocess

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class SchedulerPluginError(RuntimeError):
    pass


_SCHEDULER_PLUGINS = None


def sched_var(func):
    """This decorator marks the given function as a scheduler variable. The
    function must take no arguments (other than self)."""

    # The scheduler plugin class will search for these.
    func.is_sched_var = True
    func.is_deferable = False

    # Wrap the function function so it keeps it's base attributes.
    @wraps(func)
    def _func(self):
        # This is primarily to enforce the fact that these can't take arguments
        return str(func(self))

    return _func


def dfr_sched_var(*sub_keys):
    """This decorator marks the following function as a deferred variable. It
    can optionally be given sub_keys for the variable as positional
    arguments."""

    # The deferred variable class expects a list.
    sub_keys = list(sub_keys)

    # You can use this decorator without arguments. In that case it will
    # still get a first argument that is the function to decorate.
    given_func = None
    if sub_keys and callable(sub_keys[0]):
        given_func = sub_keys[0]
        sub_keys = []

    # This is the actual decorator that will be used.
    def _dfr_var(func):

        # The scheduler plugin class will search for these.
        func.is_sched_var = True
        func.is_deferable = False

        @wraps(func)
        def defer(self):
            # Return a deferred variable if we aren't on a node.
            if not self._in_alloc:
                return DeferredVariable(func.__name__,
                                        var_set='sched',
                                        sub_keys=sub_keys)
            else:
                return str(func(self))
        return defer

    if given_func is not None:
        return _dfr_var(given_func)
    else:
        return _dfr_var


class SchedulerVariables(collections.UserDict):
    """The base scheduler variables class. Each scheduler should have a child
    class of this that contains all the variable functions it provides.

    Usage:
    To add a scheduler variable, create a method and decorate it with
    either '@sched_var' or '@dfr_sched_var()'. The method name will be the
    variable name, and the method will be called to resolve the variable
    value. Methods that start with '_' are ignored.

    Naming Conventions:
        'alloc_*' - Variable names should be prefixed with 'alloc_' if they are
            deferred.
        'test_*' - Variable names prefixed with test denote that the variable
            is specific to a test. These also tend to be deferred.
    """

    def __init__(self, scheduler, test):
        """Initialize the scheduler var dictionary.
        :param SchedulerPlugin scheduler: The scheduler for this set of
        variables.
        :param pavilion.pav_test.PavTest test: The test object for which this
        set of variables is relevant.
        """

        super().__init__(self)

        self._keys = set()

        self.sched = scheduler
        self.test = test

        self.logger = logging.getLogger('{}_vars'.format(scheduler))

        # Find all the scheduler variables and add them as variables.
        for key in self.__dict__.keys():
            # Ignore anything that starts with an underscore
            if key.startswith('_'):
                continue
            obj = getattr(self, key)
            if callable(obj) and hasattr(obj, 'is_sched_var'):
                self._keys.add(key)

    def __getitem__(self, key):
        """As per the dict class."""
        if key not in self._keys:
            raise KeyError("Invalid scheduler variable '{}'".format(key))

        if key not in self.data:
            self.data[key] = getattr(self, key)()

        return self.data[key]

    def keys(self):
        """As per the dict class."""
        # Python 3 expects this to be a generator.
        return (k for k in self._keys)

    def get(self, key, default=None):
        """As per the dict class."""
        if key not in self._keys:
            return default

        return self[key]

    def values(self):
        """As per the dict class."""
        return ((k, self[k]) for k in self._keys)

    def get_data(self):
        """A convenience function for getting data from the scheduler."""
        return self.sched.get_data()

    # Variables
    # The methods that follow are all scheduler variables. They provide bare
    # basic single node functionality that may be good enough in certain
    # situations, namely when your general architecture is such that
    # front-end nodes have less resources than any compute node. Note that
    # they are all non-deferred, so they're safe to use in build scripts,

    @sched_var
    def min_cpus(self):
        """Get a minimum number of cpus we have available on the local
        system. Defaults to 1 on error (and logs the error)."""
        try:
            out, err = subprocess.check_output(['nproc'])
            try:
                return int(out)
            except ValueError:
                LOGGER.warning("nproc result wasn't an int: {}"
                               .format(out))
        except subprocess.CalledProcessError as err:
            LOGGER.warning("Problem calling nproc: {}".format(err))

        return 1

    BYTE_SIZE_UNITS = {
        '': 1,
        'B': 1,
        'kB': 1000,
        'MB': 1000**2,
        'GB': 1000**3,
        'KiB': 1024,
        'MiB': 1024**2,
        'GiB': 1024**3
    }

    @sched_var
    def min_mem(self):
        """Get a minimum amount of memory for the system, in Gibibytes.
        Returns 1 on error (and logs the error)."""
        mem_line = None
        try:
            with Path('/proc/meminfo').open() as meminfo:
                for line in meminfo.readlines():
                    if line.startswith('MemTotal:'):
                        mem_line = line

        except (OSError, IOError) as err:
            LOGGER.warning("Error reading /proc/meminfo: {}".format(err))
            return 1

        if mem_line is None:
            LOGGER.warning("Could not find MemTotal in /proc/meminfo")
            return 1

        parts = mem_line.split()
        try:
            mem_num = int(parts[1])
        except ValueError:
            LOGGER.warning("Could not parse memory size '{}' in /proc/meminfo"
                           .format(parts[1]))
            return 1

        mem_unit = parts[-1]
        if mem_unit not in self.BYTE_SIZE_UNITS:
            LOGGER.warning("Could not parse memory size '{}' in /proc/meminfo,"
                           "unknown unit.".format(mem_line))
            return 1

        return mem_num/self.BYTE_SIZE_UNITS[mem_unit]


def __reset():
    """This exists for testing purposes only."""

    global _SCHEDULER_PLUGINS

    if _SCHEDULER_PLUGINS is not None:
        for plugin in list(_SCHEDULER_PLUGINS.values()):
            plugin.deactivate()


def get_scheduler_plugin(name):
    """Return a scheduler plugin
    :param str name: The name of the scheduler plugin.
    :rtype: SchedulerPlugin
    """
    global _SCHEDULER_PLUGINS

    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("No scheduler plugins loaded.")

    if name not in _SCHEDULER_PLUGINS:
        print(_SCHEDULER_PLUGINS)
        raise SchedulerPluginError(
            "Scheduler plugin not found: '{}'".format(name))

    return _SCHEDULER_PLUGINS[name]


def list_scheduler_plugins():
    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("Scheduler Plugins aren't loaded.")

    return list(_SCHEDULER_PLUGINS.keys())


class SchedulerPlugin(IPlugin.IPlugin):
    """The base scheduler plugin class. Scheduler plugins should inherit from
    this.
    :cvar KICKOFF_SCRIPT_EXT: The extension for the kickoff script.
    :cvar SchedVarMeta META_VAR_CLASS: The class containing methods used
        to extract
    """

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    KICKOFF_SCRIPT_EXT = '.sh'

    VAR_CLASS = None

    def __init__(self, name, priority=PRIO_DEFAULT):
        """Scheduler plugin that is expected to be overriden by subclasses.
        The plugin will populate a set of expected 'sched' variables."""

        super().__init__()

        self.logger = logging.getLogger('sched.' + name)
        self.name = name
        self.priority = priority
        self._data = None

        if self.VAR_CLASS is None:
            raise SchedulerPluginError("You must set the Var class for"
                                       "each plugin type.")

    def _filter_nodes(self, *args, **kwargs):
        """Filter the system nodes down to just those we can use. This
        should check to make sure the nodes available are compatible with
        the test. The arguments for this function will vary by scheduler.
        :returns: A list of compatible node names.
        :rtype: list
        """
        raise NotImplementedError

    @property
    def in_alloc(self):
        """Determines whether we're on a scheduled node."""

        return self._in_alloc()

    def _in_alloc(self):
        """The plugin specific implementation of 'in_alloc'."""

        raise NotImplementedError

    def get_conf(self):
        """Return the configuration object suitable for adding to the test
        configuration."""

        raise NotImplementedError

    def get_data(self, refresh=False):
        """Get data relevant to this scheduler. This is a wrapper method; child
        classes should override _get_data instead. This simply ensures we only
        gather the data once.
        :returns: A dictionary of gathered scheduler data.
        :rtype: dict
        """

        if self._data is None or refresh:
            self._data = self._get_data()

        return self._data

    def _get_data(self):
        """Child classes should override this and use it as a way to gather
        broad amounts of data about the scheduling system. The resulting
        data structure is generally expected to be a dictionary, though that's
        entirely up to the scheduler plugin.
        :rtype: dict

        """
        raise NotImplementedError

    def get_vars(self, test):
        """Returns the dictionary of scheduler variables."""

        return self.VAR_CLASS(self, test)

    def run_tests(self, tests):
        """Run each of the given tests using this scheduler, each scheduled
        using a separate allocation.
        :param list[pavilion.pav_test.PavTest] tests: A list of pavilion tests
            to run.
        """

        for test in tests:
            self.schedule_test(test)

    def run_suite(self, tests):
        """Run each of the given tests using a single allocation."""

        raise Exception("This has not yet been implemented.")

    def schedule(self, script_path, output_path):
        """Run the script at at script path with this scheduler. This base
        version simply runs the script directly.
           :param Path script_path: - Path to the submission script.
           :param Path output_path: - Path to where to direct the output.
           :return str - Job ID number.
        """

        # Run the submit job script. We don't want to wait for it to finish,
        # just redirect the output to a reasonable place.
        output_file = output_path.open('w')
        proc = subprocess.Popen([str(script_path)],
                                stdout=output_file,
                                stderr=output_file)
        return proc.pid

    # Job status constants to be used across all schedulers. Scheduler plugins
    # should translate the scheduler's states into these four.

    # The job is currently executing
    JOB_RUNNING = 'RUNNING'
    # The job is scheduled (but not yet running).
    JOB_SCHEDULED = 'SCHEDULED'
    # The job is complete (and successful)
    JOB_COMPLETE = 'COMPLETE'
    # The job has failed to complete
    JOB_FAILED = 'FAILED'
    # There was an error with the scheduler plugin or pavilion itself.
    JOB_ERROR = 'ERROR'

    def check_job(self, pav_cfg, id_):
        """Function to check the status of a job.
            :param pav_cfg: The pavilion configuration.
            :param str id_: The id of the job, the format of which is scheduler
            specific.
            :return str - One of the self.JOB_* constants
        """
        raise NotImplemented

    def schedule_test(self, test_obj):
        """Function.
        :param pavilion.pav_test.PavTest test_obj: The pavilion test to start.
        """

        kick_off_path = self._create_schedule_script(test_obj)

        test_obj.job_id = self.schedule(kick_off_path)

        test_obj.status.set(test_obj.status.STATES.SCHEDULED,
                            "Test {} has job ID {}."
                            .format(self.name, test_obj.job_id))

    def _create_schedule_script(self, test):
        """Function to accept a list of lines and generate a script that is
           then submitted to the scheduler.
        """

        header = self._get_schedule_script_header(test)

        path = test.path/'run_test.{}'.format(self.KICKOFF_SCRIPT_EXT)

        script = scriptcomposer.ScriptComposer(
            header=header,
            details=scriptcomposer.ScriptDetails(
                path=path
            ),
        )

        script.newline()

        script.write()

        return script.details.path

    def _get_schedule_script_header(self, test):
        return scriptcomposer.ScriptHeader()

    @staticmethod
    def _add_schedule_script_body(script, test):
        """Add the script body to the given script object. This default
        simply adds a comment and the test run command."""

        script.comment("Within the allocation, run the command.")
        script.command(test.run_cmd())

    def activate(self):
        """Add this plugin to the scheduler plugin list."""

        global _SCHEDULER_PLUGINS
        name = self.name

        if _SCHEDULER_PLUGINS is None:
            _SCHEDULER_PLUGINS = {}

        if name not in _SCHEDULER_PLUGINS:
            _SCHEDULER_PLUGINS[name] = self
            format.TestConfigLoader.add_subsection(self.get_conf())
        else:
            ex_plugin = _SCHEDULER_PLUGINS[name]
            if ex_plugin.priority > self.priority:
                LOGGER.warning(
                    "Scheduler plugin {} ignored due to priority"
                    .format(name))
            elif ex_plugin.priority == self.priority:
                raise SchedulerPluginError(
                    "Two plugins for the same system plugin have the same "
                    "priority {}, {}.".format(self, _SCHEDULER_PLUGINS[name]))
            else:
                _SCHEDULER_PLUGINS[name] = self

    def deactivate(self):
        """Remove this plugin from the scheduler plugin list."""
        global _SCHEDULER_PLUGINS
        name = self.name

        if name in _SCHEDULER_PLUGINS:
            format.TestConfigLoader.remove_subsection(name)
            del _SCHEDULER_PLUGINS[name]
