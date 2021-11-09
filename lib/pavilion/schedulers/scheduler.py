"""Scheduler plugins give you the ability to (fairly) easily add new scheduling
mechanisms to Pavilion.
"""

import inspect
import os
import time
from pathlib import Path
from typing import List, Union, Dict, NewType, Tuple, Type

import yaml_config as yc
from pavilion.jobs import JobError, JobInfo
from pavilion.scriptcomposer import ScriptHeader, ScriptComposer
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.test_run import TestRun
from yapsy import IPlugin
from . import node_selection
from .config import validate_config, SchedConfigError, ScheduleConfig
from .types import NodeList, NodeSet
from .vars import SchedulerVariables

_SCHEDULER_PLUGINS = {}


class SchedulerPluginError(RuntimeError):
    """Raised when scheduler plugins encounter an error."""


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

    def get_lines(self) -> List[str]:
        """Returns all the header lines needed for the kickoff script."""

        lines = super().get_lines()

        lines.extend(self._kickoff_lines())

        return lines

    def _kickoff_lines(self) -> List[str]:
        """Override and use included information to write a kickoff script header
        for this kickoff script."""

        _ = self

        return []


TimeStamp = NewType('TimeStamp', float)
JobStatusDict = NewType('JobStatusDict', Dict['str', Tuple[TimeStamp, TestStatusInfo]])


class SchedulerPlugin(IPlugin.IPlugin):
    """The base scheduler plugin class. Scheduler plugins should inherit from
    this.
    """

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    SCHED_DATA_FN = 'sched_data.txt'
    """This file holds scheduler data for a test, so that it doesn't have to be
    regenerated."""

    KICKOFF_FN = None
    """If the kickoff script requires a special filename, set it here."""

    VAR_CLASS = SchedulerVariables  # type: Type[SchedulerVariables]
    """The scheduler's variable class."""

    KICKOFF_SCRIPT_HEADER_CLASS = KickoffScriptHeader
    """The class to use when generating headers for kickoff scripts."""

    NODE_SELECTION = {
        'contiguous': node_selection.contiguous,
        'random': node_selection.random,
        'rand_dist': node_selection.rand_dist,
        'distributed': node_selection.distributed,
    }

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

    # These need to be overridden by plugin classes. See the Advanced/Basic classes
    # for additional methods to add for a plugin.

    def _available(self) -> bool:
        """Return true if this scheduler is available on this system,
        false otherwise."""

        raise NotImplementedError("You must add a method to determine if the"
                                  "scheduler is available on this system.")

    def _job_status(self, pav_cfg, job_info: JobInfo) -> Union[TestStatusInfo, None]:
        """Override this to provide job status information given a job_info dict.
        The format of the job_info is scheduler dependent, and produced in the
        kickoff method. This can, optionally, set the job status for all jobs it can
        at once in the _job_statuses dict, which would greatly reduce the number of
        calls to the scheduler. It will only be called if a status hasn't been
        recently cached.

        It should return a TestStatusInfo object with one of these states:

        - SCHEDULED - The job is still waiting for an allocation.
        - SCHED_ERROR - The job is dead because of some error.
        - SCHED_CANCELLED - The job was cancelled.
        - SCHED_WINDUP - Returned if the scheduler says the job is running or
            prepping to run. It's ok to return this if the test is actually running,
            it will be replaced with any newer state from the test status file.

        Lastly, this may return None when we can't determine the test state at all.
        This typically happens when job id's don't stick around after a test
        finishes, so we don't have any information on it. This isn't an error - more
        like a shrug.
        """

        raise NotImplementedError

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Do your best to cancel the given job.

        :returns: None, or a message stating why the job couldn't be cancelled.
        """

        raise NotImplementedError("Must be implemented in the plugin class.")

    # These are all overridden by the Basic/Advanced classes, and don't need to be
    # defined by most plugins.

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

    # The remaining methods are shared by all plugins.

    def get_initial_vars(self, raw_sched_config: dict) -> SchedulerVariables:
        """Queries the scheduler to auto-detect its current state, and returns the
        dictionary of scheduler variables for that test given its config.

        :param raw_sched_config: The raw scheduler config for a given test.
        :returns: A tuple of the scheduler variables object and the node_list_id,
            which should be saved as part of the test config.
        """

        try:
            sched_config = validate_config(raw_sched_config)
        except SchedConfigError as err:
            raise SchedulerPluginError(
                "Error validating 'schedule' config section:\n{}".format(err.args[0]))

        if sched_config['nodes'] is None:
            raise SchedulerPluginError(
                "You must specify a value for schedule.nodes")

        return self._get_initial_vars(sched_config)

    def available(self) -> bool:
        """Returns true if this scheduler is available on this host."""

        if self._is_available is not None:
            return self._is_available

        else:
            return self._available()

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

        try:
            job_info = test.job.info
        except JobError:
            job_info = None

        if job_info is None:
            return TestStatusInfo(
                STATES.SCHED_ERROR, "Could job's scheduler info.")

        if test.job.name in self._job_statuses:
            timestamp, status = self._job_statuses[test.job.name]
            if time.time() < timestamp + self.JOB_STATUS_TIMEOUT:
                return status

        status = self._job_status(pav_cfg, job_info)

        if status is not None:
            self._job_statuses[test.job.name] = time.time(), status

        if status is None:
            # We could not determine the test status, so check if it still thinks it's
            # scheduled.
            last_status = test.status.current()
            if last_status.state == STATES.SCHEDULED:
                # If it still thinks its scheduled, that's an error.
                test.set_run_complete()
                return test.status.set(
                    STATES.SCHED_ERROR,
                    "Could not find a record of the job {} being scheduled. (It "
                    "effectively disappeared).".format(job_info))
            else:
                return last_status

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
                test.set_run_complete()
                return test.status.add_status(status)

        return status

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

        _ = self

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

    @staticmethod
    def _add_schedule_script_body(script, test):
        """Add the script body to the given script object. This default
        simply adds a comment and the test run command."""

        script.comment("Within the allocation, run the command.")
        script.command(test.run_cmd())

    def activate(self):
        """Add this plugin to the scheduler plugin list."""

        name = self.name

        if name not in _SCHEDULER_PLUGINS:
            _SCHEDULER_PLUGINS[name] = self
            conf = self.get_conf()
            if conf is not None:
                ScheduleConfig.add_subsection(self.get_conf())
        else:
            ex_plugin = _SCHEDULER_PLUGINS[name]
            if ex_plugin.priority > self.priority:
                pass
            elif ex_plugin.priority == self.priority:
                raise SchedulerPluginError(
                    "Two plugins for the same system plugin have the same "
                    "priority {}, {}.".format(self, _SCHEDULER_PLUGINS[name]))
            else:
                ScheduleConfig.remove_subsection(self.name)
                _SCHEDULER_PLUGINS[name] = self
                ScheduleConfig.add_subsection(self.get_conf())

    def deactivate(self):
        """Remove this plugin from the scheduler plugin list."""
        name = self.name

        if name in _SCHEDULER_PLUGINS:
            ScheduleConfig.remove_subsection(self.name)
            del _SCHEDULER_PLUGINS[name]


def __reset():
    """This exists for testing purposes only."""

    if _SCHEDULER_PLUGINS is not None:
        for plugin in list(_SCHEDULER_PLUGINS.values()):
            plugin.deactivate()
