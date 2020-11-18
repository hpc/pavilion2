"""Scheduler plugins give you the ability to (fairly) easily add new scheduling
mechanisms to Pavilion.
"""

# pylint: disable=no-self-use

import datetime
import inspect
import logging
import os
import subprocess
from functools import wraps
from pathlib import Path

from pavilion import scriptcomposer
from pavilion.permissions import PermissionsManager
from pavilion.lockfile import LockFile
from pavilion.status_file import STATES, StatusInfo
from pavilion.test_config import file_format
from pavilion.test_config.variables import DeferredVariable
from pavilion.test_run import TestRun
from pavilion.var_dict import VarDict, var_method, normalize_value
from yapsy import IPlugin

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class SchedulerPluginError(RuntimeError):
    """Raised when scheduler plugins encounter an error."""


_SCHEDULER_PLUGINS = {}


def dfr_var_method(*sub_keys):
    """This decorator marks the following function as a deferred variable. It
    can optionally be given sub_keys for the variable as positional
    arguments.

    :param list(str) sub_keys: The variable sub-keys.
    """

    # The deferred variable class expects a list.
    sub_keys = list(sub_keys)

    # You can use this decorator without arguments. In that case it will
    # still get a first argument that is the function to decorate.
    given_func = None
    if sub_keys and callable(sub_keys[0]):
        given_func = sub_keys[0]

    # This is the actual decorator that will be used.
    def _dfr_var(func):

        # The scheduler plugin class will search for these.
        # pylint: disable=W0212
        func._is_var_method = True
        func._is_deferable = True

        @wraps(func)
        def defer(self):
            """Return a deferred variable if we aren't on a node."""
            if not self.sched.in_alloc:
                return DeferredVariable()
            else:
                value = func(self)
                norm_val = normalize_value(value)
                if norm_val is None:
                    raise ValueError(
                        "Invalid variable value returned by {}: {}."
                        .format(func.__name__, value))
                return norm_val

        return defer

    if given_func is not None:
        return _dfr_var(given_func)
    else:
        return _dfr_var


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

    def __init__(self, scheduler, sched_config):
        """Initialize the scheduler var dictionary.

        :param SchedulerPlugin scheduler: The scheduler for this set of
            variables.
        :param dict sched_config: The test object for
            which this set of variables is relevant.
        """

        super().__init__('sched')

        self.sched = scheduler
        self.sched_config = sched_config

        self._keys = self._find_vars()

        self.logger = logging.getLogger('{}_vars'.format(scheduler))

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

    @property
    def sched_data(self):
        """A convenience function for getting data from the scheduler."""

        if self.sched.available():
            return self.sched.get_data()
        else:
            return {}

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

    @var_method
    def test_cmd(self):
        """The command to prepend to a line to kick it off under the
        scheduler. This is blank by default, but most schedulers will
        want to define something that utilizes relevant scheduler
        parameters."""

        return ''

    @var_method
    def min_cpus(self):
        """Get a minimum number of cpus we have available on the local
        system. Defaults to 1 on error (and logs the error)."""
        try:
            out = subprocess.check_output(['nproc'])
            try:
                return int(out)
            except ValueError:
                LOGGER.warning("nproc result wasn't an int: %s", out)
        except subprocess.CalledProcessError as err:
            LOGGER.warning("Problem calling nproc: %s", err)

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

    @var_method
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
            LOGGER.warning("Error reading /proc/meminfo: %s", err)
            return 1

        if mem_line is None:
            LOGGER.warning("Could not find MemTotal in /proc/meminfo")
            return 1

        parts = mem_line.split()
        try:
            mem_num = int(parts[1])
        except ValueError:
            LOGGER.warning("Could not parse memory size '%s' in /proc/meminfo",
                           parts[1])
            return 1

        mem_unit = parts[-1]
        if mem_unit not in self.BYTE_SIZE_UNITS:
            LOGGER.warning("Could not parse memory size '%s' in /proc/meminfo,"
                           "unknown unit.", mem_line)
            return 1

        return mem_num/self.BYTE_SIZE_UNITS[mem_unit]


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


class SchedulerPlugin(IPlugin.IPlugin):
    """The base scheduler plugin class. Scheduler plugins should inherit from
    this.
    """

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    KICKOFF_SCRIPT_EXT = '.sh'
    """The extension for the kickoff script."""

    VAR_CLASS = SchedulerVariables
    """The scheduler's variable class."""

    def __init__(self, name, description, priority=PRIO_CORE):
        """Scheduler plugin that is expected to be overriden by subclasses.
        The plugin will populate a set of expected 'sched' variables."""

        super().__init__()

        self.logger = logging.getLogger('sched.' + name)
        self.name = name
        self.description = description
        self.priority = priority
        self._data = None
        self.path = inspect.getfile(self.__class__)

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

    def get_vars(self, sched_config):
        """Returns the dictionary of scheduler variables.

        :param dict sched_config: The scheduler config for a given test.
        """

        return self.VAR_CLASS(self, sched_config)

    def schedule_tests(self, pav_cfg, tests):
        """Schedule each of the given tests using this scheduler using a
        separate allocation (if applicable) for each.

        :param pav_cfg: The pavilion config
        :param [pavilion.test_run.TestRun] tests: A list of pavilion tests
            to schedule.
        """

        for test in tests:
            self.schedule_test(pav_cfg, test)

    def run_suite(self, tests):
        """Run each of the given tests using a single allocation. This
        is effectively a placeholder."""

    def lock_concurrency(self, pav_cfg, test):
        """Acquire the concurrency lock for this scheduler, if necessary.

        :param pav_cfg: The pavilion config.
        :param test: A test object
        """

        # For syntax highlighting. These vars may be used when overridden.
        _ = pav_cfg, test, self

        return None

    # A pre-implemented version of lock_concurrency that locks based
    # on the scheduler's 'concurrent' variable. Provides a standard way to
    # do this for schedulers that need it.
    # Just set the following in your scheduler class:
    #   lock_concurrency = SchedulerPlugin._do_lock_concurrency
    def _do_lock_concurrency(self, pav_cfg, test):
        """Acquire the concurrency lock for this scheduler, if necessary.

        :param pav_cfg: The pavilion configuration.
        :param pavilion.pav_config.test.TestRun test: The pavilion test
            to lock concurrency for.
        """

        if test.config[self.name]['concurrent'] in ('false', 'False'):
            return None

        lock_name = '{s.name}_sched.lock'.format(s=self)

        # Most schedulers shouldn't have to do this.
        lock_path = pav_cfg.working_dir/lock_name

        lock = LockFile(
            lock_path,
            group=pav_cfg.shared_group,
            # Expire after 24 hours.
            expires_after=60*60*24,
        )

        test.status.set(STATES.SCHEDULED,
                        "Test is non-concurrent, and waiting on the "
                        "concurrency lock for scheduler {s.name}."
                        .format(s=self))

        lock.lock()

        return lock

    @staticmethod
    def unlock_concurrency(lock):
        """Unlock the concurrency lock, if one exists.

        :param Union(Lockfile, None) lock:
        """

        if lock is not None:
            lock.unlock()

    @staticmethod
    def _now():
        """Convenience method for getting a reasonable current time object."""

        return datetime.datetime.now()

    def available(self):
        """Returns true if this scheduler is available on this host.

        :rtype: bool
        """

        raise NotImplementedError

    def job_status(self, pav_cfg, test) -> StatusInfo:
        """Get the job state from the scheduler, and map it to one of the
        on of the following states: SCHEDULED, SCHED_ERROR, SCHED_CANCELLED.
        This may also simply re-fetch the latest state from the state file,
        and return that if necessary.

        :param pav_cfg: The pavilion configuration.
        :param pavilion.test_run.TestRun test: The test we're checking on.
        :return: A StatusInfo object representing the status.
        """

        raise NotImplementedError

    def schedule_test(self, pav_cfg, test_obj):
        """Create the test script and schedule the job.

        :param pav_cfg: The pavilion cfg.
        :param pavilion.test_run.TestRun test_obj: The pavilion test to
            start.
        """

        kick_off_path = self._create_kickoff_script(pav_cfg, test_obj)

        try:
            test_obj.job_id = self._schedule(test_obj, kick_off_path)

            test_obj.status.set(test_obj.status.STATES.SCHEDULED,
                                "Test {} has job ID {}."
                                .format(self.name, test_obj.job_id))
        except Exception:
            # If this fails, consider this test done.
            test_obj.set_run_complete()
            raise

    def _schedule(self, test_obj, kickoff_path):
        """Run the kickoff script at script path with this scheduler.

        :param pavilion.test_config.TestRun test_obj: The test to schedule.
        :param Path kickoff_path: Path to the submission script.
        :return str: Job ID number.
        """

        raise NotImplementedError

    def _kickoff_script_path(self, test):
        path = (test.path/'kickoff')
        return path.with_suffix(self.KICKOFF_SCRIPT_EXT)

    def _create_kickoff_script(self, pav_cfg, test_obj: TestRun):
        """Function to accept a list of lines and generate a script that is
        then submitted to the scheduler.

        :param pavilion.test_config.TestRun test_obj:
        """

        header = self._get_kickoff_script_header(test_obj)

        script = scriptcomposer.ScriptComposer(header=header)
        script.comment("Redirect all output to kickoff.log")
        script.command("exec >{} 2>&1"
                       .format(test_obj.path/'kickoff.log'))

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

        # Run the test via pavilion
        script.command('pav _run {t.id}'.format(t=test_obj))

        path = self._kickoff_script_path(test_obj)
        with PermissionsManager(path, test_obj.group, test_obj.umask):
            script.write(path)

        return path

    def _get_kickoff_script_header(self, test):
        # Unused in the base class
        del test

        return scriptcomposer.ScriptHeader()

    @staticmethod
    def _add_schedule_script_body(script, test):
        """Add the script body to the given script object. This default
        simply adds a comment and the test run command."""

        script.comment("Within the allocation, run the command.")
        script.command(test.run_cmd())

    def cancel_job(self, test):
        """Tell the scheduler to cancel the given test, if it can. This should
        simply try it's best for the test given, and note in the test status
        (with a SCHED_ERROR) if there were problems. Update the test status to
        SCHED_CANCELLED if it succeeds.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: A status info object describing the state. If we actually
            cancel the job the test status will be set to SCHED_CANCELLED.
            This should return SCHED_ERROR when something goes wrong.
        :rtype: StatusInfo
        """

        job_id = test.job_id
        if job_id is None:
            test.set_run_complete()
            return test.status.set(STATES.SCHED_CANCELLED,
                                   "Job was never started.")

        return self._cancel_job(test)

    def _cancel_job(self, test):
        """Override in scheduler plugins to handle cancelling a job.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: Whether we're confident the job was canceled, and an
            explanation.
        :rtype: StatusInfo
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
                LOGGER.warning(
                    "Scheduler plugin %s ignored due to priority", name)
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
