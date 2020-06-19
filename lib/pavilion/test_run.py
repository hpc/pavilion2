"""Contains the TestRun class, as well as functions for getting
the list of all known test runs."""

# pylint: disable=too-many-lines

import datetime
import grp
import json
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import pavilion.output
from pavilion import builder
from pavilion import lockfile
from pavilion import result
from pavilion import scriptcomposer
from pavilion import utils
from pavilion.status_file import StatusFile, STATES
from pavilion.test_config import variables, resolver
from pavilion.test_config.file_format import TestConfigError
from pavilion.permissions import PermissionsManager


def get_latest_tests(pav_cfg, limit):
    """Returns ID's of latest test given a limit

:param pav_cfg: Pavilion config file
:param int limit: maximum size of list of test ID's
:return: list of test ID's
:rtype: list(int)
"""

    test_dir_list = []
    top_dir = pav_cfg.working_dir/'test_runs'
    for child in top_dir.iterdir():
        mtime = child.stat().st_mtime
        test_dir_list.append((mtime, child.name))

    test_dir_list.sort()
    last_tests = test_dir_list[-limit:]
    tests_only = [int(i[1]) for i in last_tests]

    return tests_only


class TestRunError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""


class TestRunNotFoundError(RuntimeError):
    """For when we try to find an existing test, but it doesn't exist."""


class TestRun:
    """The central pavilion test object. Handle saving, monitoring and running
    tests.

    **Test LifeCycle**
    1. Test Object is Created -- ``TestRun.__init__``

       1. Test id and directory (``working_dir/test_runs/0000001``) are created.
       2. Most test information files (config, status, etc) are created.
       3. Build script is created.
       4. Build hash is generated.
       5. Run script dry run generation is performed.

    2. Test is built. -- ``test.build()``
    3. Test is finalized. -- ``test.finalize()``

       1. Variables and config go through final resolution.
       2. Final run script is generated.
    4. Test is run. -- ``test.run()``
    5. Results are gathered. -- ``test.gather_results()``

    :ivar int id: The test id.
    :ivar dict config: The test's configuration.
    :ivar Path test.path: The path to the test's test_run directory.
    :ivar dict results: The test results. Set None if results haven't been
        gathered.
    :ivar TestBuilder builder: The test builder object, with information on the
        test's build.
    :ivar Path build_origin_path: The path to the symlink to the original
        build directory. For bookkeeping.
    :ivar StatusFile status: The status object for this test.
    :ivar TestRunOptions opt: Test run options defined by OPTIONS_DEFAULTS
    :cvar OPTIONS_DEFAULTS: A dictionary of defaults for additional options
        for the test run. Values given to Pavilion are expected to be the
        same type as the default value.
    """

    logger = logging.getLogger('pav.TestRun')

    JOB_ID_FN = 'job_id'
    COMPLETE_FN = 'RUN_COMPLETE'

    def __init__(self, pav_cfg, config,
                 build_tracker=None, var_man=None, _id=None,
                 rebuild=False, build_only=False):
        """Create an new TestRun object. If loading an existing test
    instance, use the ``TestRun.from_id()`` method.

:param pav_cfg: The pavilion configuration.
:param dict config: The test configuration dictionary.
:param builder.MultiBuildTracker build_tracker: Tracker for watching
    and managing the status of multiple builds.
:param variables.VariableSetManager var_man: The variable set manager for this
    test.
:param bool build_only: Only build this test run, do not run it.
:param bool rebuild: After determining the build name, deprecate it and select
    a new, non-deprecated build.
:param int _id: The test id of an existing test. (You should be using
    TestRun.load).
"""

        # Just about every method needs this
        self._pav_cfg = pav_cfg

        self.load_ok = True

        self.scheduler = config['scheduler']

        # Create the tests directory if it doesn't already exist.
        tests_path = pav_cfg.working_dir/'test_runs'

        self.config = config

        self.id = None  # pylint: disable=invalid-name

        # Get the test version information
        self.test_version = config.get('test_version')
        self.min_pav_version = config.get('min_pav_version')

        self._attrs = {}

        # Mark the run to build locally.
        self.build_local = config.get('build', {}) \
                                 .get('on_nodes', 'false').lower() != 'true'

        # If a test access group was given, make sure it exists and the
        # current user is a member.
        self.group = config.get('group')
        if self.group is not None:
            try:
                group_data = grp.getgrnam(self.group)
                user = utils.get_login()
                if self.group != user and user not in group_data.gr_mem:
                    raise TestConfigError(
                        "Test specified group '{}', but the current user '{}' "
                        "is not a member of that group."
                        .format(self.group, user))
            except KeyError as err:
                raise TestConfigError(
                    "Test specified group '{}', but that group does not "
                    "exist on this system. {}"
                    .format(self.group, err))

        self.umask = config.get('umask')
        if self.umask is not None:
            try:
                self.umask = int(self.umask, 8)
            except ValueError:
                raise RuntimeError(
                    "Invalid umask. This should have been enforced by the "
                    "by the config format.")

        self.build_only = build_only
        self.rebuild = rebuild

        # Get an id for the test, if we weren't given one.
        if _id is None:
            self.id, self.path = self.create_id_dir(tests_path)
            with PermissionsManager(self.path, self.group, self.umask):
                self._save_config()
                if var_man is None:
                    var_man = variables.VariableSetManager()
                self.var_man = var_man
                self._variables_path = self.path / 'variables'
                self.var_man.save(self._variables_path)

            self.save_attributes()
        else:
            self.id = _id
            self.path = utils.make_id_path(tests_path, self.id)
            self._variables_path = self.path / 'variables'
            if not self.path.is_dir():
                raise TestRunNotFoundError(
                    "No test with id '{}' could be found.".format(self.id))
            try:
                self.var_man = variables.VariableSetManager.load(
                    self._variables_path
                )
            except RuntimeError as err:
                raise TestRunError(*err.args)

            self.load_attributes()

        name_parts = [
            self.config.get('suite', '<unknown>'),
            self.config.get('name', '<unnamed>'),
        ]
        subtitle = self.config.get('subtitle')
        # Don't add undefined or empty subtitles.
        if subtitle:
            name_parts.append(subtitle)

        self.name = '.'.join(name_parts)

        # Set a logger more specific to this test.
        self.logger = logging.getLogger('pav.TestRun.{}'.format(self.id))

        # This will be set by the scheduler
        self._job_id = None

        with PermissionsManager(self.path/'status', self.group, self.umask):
            # Setup the initial status file.
            self.status = StatusFile(self.path/'status')
            if _id is None:
                self.status.set(STATES.CREATED,
                                "Test directory and status file created.")

        self.run_timeout = self.parse_timeout(
            'run', config.get('run', {}).get('timeout'))
        self.build_timeout = self.parse_timeout(
            'build', config.get('build', {}).get('timeout'))

        self._attributes = {}

        self.build_name = None
        self.run_log = self.path/'run.log'
        self.results_path = self.path/'results.json'
        self.build_origin_path = self.path/'build_origin'

        build_config = self.config.get('build', {})

        # make sure build source_download_name is not set without
        # source_location
        try:
            if build_config['source_download_name'] is not None:
                if build_config['source_location'] is None:
                    msg = "Test could not be built. Need 'source_location'."
                    self.status.set(STATES.BUILD_ERROR,
                                    "'source_download_name is set without a "
                                    "'source_location'")
                    raise TestConfigError(msg)
        except KeyError:
            # this is mostly for unit tests that create test configs without a
            # build section at all
            pass

        self.build_script_path = self.path/'build.sh'  # type: Path
        self.build_path = self.path/'build'
        if _id is None:
            self._write_script(
                'build',
                path=self.build_script_path,
                config=build_config)

        build_name = None
        self._build_name_fn = self.path / 'build_name'
        if _id is not None:
            build_name = self._load_build_name()

        try:
            self.builder = builder.TestBuilder(
                pav_cfg=pav_cfg,
                test=self,
                mb_tracker=build_tracker,
                build_name=build_name
            )
        except builder.TestBuilderError as err:
            raise TestRunError(
                "Could not create builder for test {s.name} (run {s.id}): {err}"
                .format(s=self, err=err)
            )

        self.save_build_name()

        run_config = self.config.get('run', {})
        self.run_tmpl_path = self.path/'run.tmpl'
        self.run_script_path = self.path/'run.sh'

        if _id is None:
            self._write_script(
                'run',
                path=self.run_tmpl_path,
                config=run_config)

        if _id is None:
            self.status.set(STATES.CREATED, "Test directory setup complete.")

        self._results = None
        self._created = None

        self.skipped = self._get_skipped()

    @classmethod
    def load(cls, pav_cfg, test_id):
        """Load an old TestRun object given a test id.

        :param pav_cfg: The pavilion config
        :param int test_id: The test's id number.
        :rtype: TestRun
        """

        path = utils.make_id_path(pav_cfg.working_dir/'test_runs', test_id)

        if not path.is_dir():
            raise TestRunError("Test directory for test id {} does not exist "
                               "at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        return TestRun(pav_cfg, config, _id=test_id)

    def finalize(self, var_man):
        """Resolve any remaining deferred variables, and generate the final
        run script."""

        self.var_man.undefer(new_vars=var_man)

        self.config = resolver.TestConfigResolver.resolve_deferred(
            self.config, self.var_man)
        self._save_config()
        # Save our newly updated variables.
        self.var_man.save(self._variables_path)

        # Create files specified via run config key.
        files_to_create = self.config['run'].get('create_files', [])
        if files_to_create:
            for file, contents in files_to_create.items():
                file_path = Path(self.build_path / file)
                # Prevent files from being written outside build directory.
                if not utils.dir_contains(file_path, self.build_path):
                    raise TestRunError("'create_file: {}': file path"
                                       " outside build context."
                                       .format(file_path))
                # Prevent files from overwriting existing directories.
                if file_path.is_dir():
                    raise TestRunError("'create_file: {}' clashes with"
                                       " existing directory in build dir."
                                       .format(file_path))
                # Create file parent directory(ies).
                dirname = file_path.parent
                (self.build_path / dirname).mkdir(parents=True, exist_ok=True)

                # Don't try to overwrite a symlink without removing it first.
                if file_path.is_symlink():
                    file_path.unlink()

                # Write file.
                with file_path.open('w') as file_:
                    for line in contents:
                        file_.write("{}\n".format(line))

        if not self.skipped:
            self.skipped = self._get_skipped()

        self._write_script(
            'run',
            self.run_script_path,
            self.config['run'],
        )

    def run_cmd(self):
        """Construct a shell command that would cause pavilion to run this
        test."""

        pav_path = self._pav_cfg.pav_root/'bin'/'pav'

        return '{} run {}'.format(pav_path, self.id)

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = self.path/'config'

        # make lock
        lock_path = self.path/'config.lockfile'
        config_lock = lockfile.LockFile(
            lock_path,
            group=self._pav_cfg.shared_group)

        try:
            config_lock.lock()
            with config_path.open('w') as json_file:
                pavilion.output.json_dump(self.config, json_file)
        except (OSError, IOError) as err:
            raise TestRunError(
                "Could not save TestRun ({}) config at {}: {}"
                .format(self.name, self.path, err))
        except TypeError as err:
            raise TestRunError(
                "Invalid type in config for ({}): {}"
                .format(self.name, err))
        finally:
            config_lock.unlock()

    @classmethod
    def _load_config(cls, test_path):
        """Load a saved test configuration."""
        config_path = test_path/'config'

        # make lock
        lock_path = test_path/'config.lockfile'
        config_lock = lockfile.LockFile(lock_path)

        if not config_path.is_file():
            raise TestRunError("Could not find config file for test at {}."
                               .format(test_path))

        try:
            config_lock.lock()
            with config_path.open('r') as config_file:
                # Because only string keys are allowed in test configs,
                # this is a reasonable way to load them.
                return json.load(config_file)
        except TypeError as err:
            raise TestRunError("Bad config values for config '{}': {}"
                               .format(config_path, err))
        except (IOError, OSError) as err:
            raise TestRunError("Error reading config file '{}': {}"
                               .format(config_path, err))
        finally:
            config_lock.unlock()

    def build(self, cancel_event=None):
        """Build the test using its builder object and symlink copy it to
        it's final location. The build tracker will have the latest
        information on any encountered errors.

        :param threading.Event cancel_event: Event to tell builds when to die.

        :returns: True if build successful
        """

        if self.build_origin_path.exists():
            raise RuntimeError(
                "Whatever called build() is calling it for a second time."
                "This should never happen for a given test run ({s.id})."
                .format(s=self))

        if cancel_event is None:
            cancel_event = threading.Event()

        if self.builder.build(cancel_event=cancel_event):
            # Create the build origin path, to make tracking a test's build
            # a bit easier.
            with PermissionsManager(self.build_origin_path, self.group,
                                    self.umask):
                self.build_origin_path.symlink_to(self.builder.path)

            with PermissionsManager(self.build_path, self.group, self.umask):
                if not self.builder.copy_build(self.build_path):
                    cancel_event.set()
        else:
            self.builder.fail_path.rename(self.build_path)
            return False

    def save_build_name(self):
        """Save the builder's build name to the build name file for the test."""

        try:
            with PermissionsManager(self._build_name_fn, self.group,
                                    self.umask), \
                    self._build_name_fn.open('w') as build_name_file:
                build_name_file.write(self.builder.name)
        except OSError as err:
            raise TestRunError(
                "Could not save build name to build name file at '{}': {}"
                .format(self._build_name_fn, err)
            )

    def _load_build_name(self):
        """Load the build name from the build name file."""

        try:
            with self._build_name_fn.open() as build_name_file:
                return build_name_file.read()
        except OSError as err:
            raise TestRunError(
                "All existing test runs must have a readable 'build_name' "
                "file, but test run {s.id} did not: {err}"
                .format(s=self, err=err))

    def run(self):
        """Run the test.

        :rtype: bool
        :returns: The return code of the test command.
        :raises TimeoutError: When the run times out.
        :raises TestRunError: We don't actually raise this, but might in the
            future.
        """

        if self.build_only:
            self.status.set(
                STATES.RUN_ERROR,
                "Tried to run a 'build_only' test object.")
            return False

        self.status.set(STATES.PREPPING_RUN,
                        "Converting run template into run script.")

        with PermissionsManager(self.path, self.group, self.umask), \
                self.run_log.open('wb') as run_log:
            self.status.set(STATES.RUNNING,
                            "Starting the run script.")

            self.started = datetime.datetime.now()

            # Set the working directory to the build path, if there is one.
            run_wd = None
            if self.build_path is not None:
                run_wd = self.build_path.as_posix()

            # Run scripts take the test id as a first argument.
            cmd = [self.run_script_path.as_posix(), str(self.id)]
            proc = subprocess.Popen(cmd,
                                    cwd=run_wd,
                                    stdout=run_log,
                                    stderr=subprocess.STDOUT)

            self.status.set(STATES.RUNNING,
                            "Currently running.")

            # Run the test, but timeout if it doesn't produce any output every
            # self._run_timeout seconds
            timeout = self.run_timeout
            ret = None
            while ret is None:
                try:
                    ret = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    out_stat = self.run_log.stat()
                    quiet_time = time.time() - out_stat.st_mtime
                    # Has the output file changed recently?
                    if self.run_timeout < quiet_time:
                        # Give up on the build, and call it a failure.
                        proc.kill()
                        msg = ("Run timed out after {} seconds"
                               .format(self.run_timeout))
                        self.status.set(STATES.RUN_TIMEOUT, msg)
                        self.finished = datetime.datetime.now()
                        self.save_attributes()
                        raise TimeoutError(msg)
                    else:
                        # Only wait a max of run_silent_timeout next 'wait'
                        timeout = timeout - quiet_time

        self.finished = datetime.datetime.now()
        self.save_attributes()

        self.status.set(STATES.RUN_DONE,
                        "Test run has completed.")

        return ret

    def set_run_complete(self):
        """Write a file in the test directory that indicates that the test
    has completed a run, one way or another. This should only be called
    when we're sure their won't be any more status changes."""

        # Write the current time to the file. We don't actually use the contents
        # of the file, but it's nice to have another record of when this was
        # run.
        with (self.path/self.COMPLETE_FN).open('w') as run_complete, \
                PermissionsManager(self.path/self.COMPLETE_FN,
                                   self.group, self.umask):
            json.dump({
                'complete': datetime.datetime.now().isoformat(),
            }, run_complete)

    @property
    def complete(self):
        """Return the complete time from the run complete file, or None
        if the test was never marked as complete."""

        run_complete_path = self.path/self.COMPLETE_FN

        if run_complete_path.exists():
            try:
                with run_complete_path.open() as complete_file:
                    data = json.load(complete_file)
                    return data.get('complete')
            except (OSError, ValueError, json.JSONDecodeError) as err:
                self.logger.warning(
                    "Failed to read run complete file for at %s: %s",
                    run_complete_path.as_posix(), err)
                return None
        else:
            return None

    ATTR_FILE_NAME = 'attributes'

    def save_attributes(self):
        """Save the attributes to file in the test directory."""

        attr_path = self.path/self.ATTR_FILE_NAME

        with PermissionsManager(attr_path, self.group, self.umask), \
                attr_path.open('w') as attr_file:
            json.dump(self._attrs, attr_file)

    def load_attributes(self):
        """Load the attributes from file."""

        attr_path = self.path/self.ATTR_FILE_NAME

        if attr_path.exists():
            with attr_path.open() as attr_file:
                try:
                    self._attrs = json.load(attr_file)
                except (json.JSONDecodeError, OSError, ValueError, KeyError)\
                        as err:
                    raise TestRunError(
                        "Could not load attributes file: \n{}"
                        .format(err.args)
                    )

    OPTIONS_DEFAULTS = {
        'build_only': False,
        'rebuild': False,
    }

    @property
    def finished(self):
        """The end time for this test run."""
        value = self._attrs.get('finished')
        if value is not None:
            value = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        return value

    @finished.setter
    def finished(self, value: datetime.datetime):
        value = value.isoformat(" ")
        self._attrs['finished'] = value

    @property
    def started(self):
        """The start time for this test run."""
        value = self._attrs.get('started')
        if value is not None:
            value = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        return value

    @started.setter
    def started(self, value):
        value = value.isoformat(" ")
        self._attrs['started'] = value

    @property
    def build_only(self):
        """Only build this test, never run it."""
        return self._attrs.get('build_only')

    @build_only.setter
    def build_only(self, value):
        self._attrs['build_only'] = value

    @property
    def rebuild(self):
        """Whether or not this test will rebuild it's build."""
        return self._attrs.get('rebuild')

    @rebuild.setter
    def rebuild(self, value):
        self._attrs['rebuild'] = value

    WAIT_INTERVAL = 0.5

    def wait(self, timeout=None):
        """Wait for the test run to be complete. This works across hosts, as
        it simply checks for files in the run directory.

        :param Union(None,float) timeout: How long to wait in seconds. If
            this is None, wait forever.
        :raises TimeoutError: if the timeout expires.
        """

        if timeout is not None:
            timeout = time.time() + timeout

        while 1:
            if self.complete is not None:
                return

            time.sleep(self.WAIT_INTERVAL)

            if timeout is not None and time.time() > timeout:
                raise TimeoutError("Timed out waiting for test '{}' to "
                                   "complete".format(self.id))

    def gather_results(self, run_result, regather=False):
        """Process and log the results of the test, including the default set
of result keys.

:param int run_result: The return code of the test run.
:param bool regather: Gather results without performing any changes to the
    test itself.
"""

        if self.finished is None:
            raise RuntimeError(
                "test.gather_results can't be run unless the test was run"
                "(or an attempt was made to run it. "
                "This occurred for test {s.name}, #{s.id}"
                .format(s=self)
            )

        parser_configs = self.config['results']['parse']

        results = result.base_results(self)

        results['return_value'] = run_result

        if not regather:
            self.status.set(STATES.RESULTS,
                            "Parsing {} result types."
                            .format(len(parser_configs)))

        try:
            result.parse_results(self, results)
        except result.ResultError as err:
            results['result'] = self.ERROR
            results['pav_result_errors'].append(
                "Error parsing results: {}".format(err.args[0]))
            if not regather:
                self.status.set(STATES.RESULTS_ERROR,
                                results['pav_result_errors'][-1])

            return results

        if not regather:
            self.status.set(STATES.RESULTS,
                            "Performing {} result evaluations."
                            .format(len(self.config['results']['evaluate'])))
        try:
            result.evaluate_results(
                results,
                self.config['results']['evaluate'])
        except result.ResultError as err:
            results['result'] = self.ERROR
            results['pav_result_errors'].append(err.args[0])
            results['result'] = self.ERROR
            if not regather:
                self.status.set(STATES.RESULTS_ERROR,
                                results['pav_result_errors'][-1])
            return results

        if results['result'] is True:
            results['result'] = self.PASS
        elif results['result'] is False:
            results['result'] = self.FAIL
        else:
            results['result'] = self.ERROR
            results['pav_result_errors'].append(
                "The value for the 'result' key in the results must be a "
                "boolean. Got '{}' instead".format(results['result']))
            return results

        self._results = results

        return results

    def save_results(self, results):
        """Save the results to the results file.

:param dict results: The results dictionary.
"""

        with self.results_path.open('w') as results_file, \
                PermissionsManager(self.results_path, self.group, self.umask):
            json.dump(results, results_file)

    def load_results(self):
        """Load results from the results file.

:returns A dict of results, or None if the results file doesn't exist.
:rtype: dict
"""

        if self.results_path.exists():
            with self.results_path.open() as results_file:
                return json.load(results_file)
        else:
            return None

    PASS = 'PASS'
    FAIL = 'FAIL'
    ERROR = 'ERROR'

    @property
    def results(self):
        """The test results. Returns a dictionary of basic information
        if the test has no results."""
        if self._results is None and self.results_path.exists():
            with self.results_path.open() as results_file:
                self._results = json.load(results_file)

        if self._results is None:
            return {
                'name': self.name,
                'sys_name': self.var_man['sys_name'],
                'created': self.created,
                'id': self.id,
                'result': None,
            }
        else:
            return self._results

    @property
    def created(self):
        """When this test run was created (the creation time of the test run
        directory)."""
        if self._created is None:
            timestamp = self.path.stat().st_mtime
            self._created = datetime.datetime.fromtimestamp(timestamp)\
                                    .isoformat(" ")

        return self._created

    @property
    def is_built(self):
        """Whether the build for this test exists.

:returns: True if the build exists (or the test doesn't have a build),
          False otherwise.
:rtype: bool
"""

        if self.build_path.resolve().exists():
            return True
        else:
            return False

    @property
    def job_id(self):
        """The job id of this test (saved to a ``jobid`` file). This should
be set by the scheduler plugin as soon as it's known."""

        path = self.path/self.JOB_ID_FN

        if self._job_id is not None:
            return self._job_id

        try:
            with path.open() as job_id_file:
                self._job_id = job_id_file.read()
        except FileNotFoundError:
            return None
        except (OSError, IOError) as err:
            self.logger.error("Could not read jobid file '%s': %s",
                              path, err)
            return None

        return self._job_id

    @job_id.setter
    def job_id(self, job_id):

        path = self.path/self.JOB_ID_FN

        try:
            with path.open('w') as job_id_file:
                job_id_file.write(job_id)
        except (IOError, OSError) as err:
            self.logger.error("Could not write jobid file '%s': %s",
                              path, err)

        self._job_id = job_id

    @property
    def timestamp(self):
        """Return the unix timestamp for this test, based on the last
modified date for the test directory."""
        return self.path.stat().st_mtime

    def _write_script(self, stype, path, config):
        """Write a build or run script or template. The formats for each are
            mostly identical.
        :param str stype: The type of script (run or build).
        :param Path path: Path to the template file to write.
        :param dict config: Configuration dictionary for the script file.
        :return:
        """

        script = scriptcomposer.ScriptComposer()

        verbose = config.get('verbose', 'false').lower() == 'true'

        if verbose:
            script.comment('# Echoing all commands to log.')
            script.command('set -v')
            script.newline()

        pav_lib_bash = self._pav_cfg.pav_root/'bin'/'pav-lib.bash'

        # If we include this directly, it breaks build hashing.
        script.comment('The first (and only) argument of the build script is '
                       'the test id.')
        script.env_change({
            'TEST_ID': '${1:-0}',   # Default to test id 0 if one isn't given.
            'PAV_CONFIG_FILE': self._pav_cfg['pav_cfg_file']
        })
        script.command('source {}'.format(pav_lib_bash))

        if config.get('preamble', []):
            script.newline()
            script.comment('Preamble commands')
            for cmd in config['preamble']:
                script.command(cmd)

        if stype == 'build' and not self.build_local:
            script.comment('To be built in an allocation.')

        modules = config.get('modules', [])
        if modules:
            script.newline()
            script.comment('Perform module related changes to the environment.')

            for module in config.get('modules', []):
                script.module_change(module, self.var_man)

        env = config.get('env', {})
        if env:
            script.newline()
            script.comment("Making any environment changes needed.")
            script.env_change(config.get('env', {}))

        if verbose:
            script.newline()
            script.comment('List all the module modules for posterity')
            script.command("module -t list")
            script.newline()
            script.comment('Output the environment for posterity')
            script.command("declare -p")

        script.newline()
        cmds = config.get('cmds', [])
        if cmds:
            script.comment("Perform the sequence of test commands.")
            for line in config.get('cmds', []):
                for split_line in line.split('\n'):
                    script.command(split_line)
        else:
            script.comment('No commands given for this script.')

        with PermissionsManager(path, self.group, self.umask):
            script.write(path)

    @staticmethod
    def create_id_dir(id_dir):
        """In the given directory, create the lowest numbered (positive integer)
directory that doesn't already exist.

:param Path id_dir: Path to the directory that contains these 'id'
    directories
:returns: The id and path to the created directory.
:rtype: list(int, Path)
:raises OSError: on directory creation failure.
:raises TimeoutError: If we couldn't get the lock in time.
"""

        lockfile_path = id_dir/'.lockfile'
        with lockfile.LockFile(lockfile_path, timeout=1):
            ids = list(os.listdir(str(id_dir)))
            # Only return the test directories that could be integers.
            ids = [id_ for id_ in ids if id_.isdigit()]
            ids = [id_ for id_ in ids if (id_dir/id_).is_dir()]
            ids = [int(id_) for id_ in ids]
            ids.sort()

            # Find the first unused id.
            id_ = 1
            while id_ in ids:
                id_ += 1

            path = utils.make_id_path(id_dir, id_)
            path.mkdir()

        return id_, path

    def __repr__(self):
        return "TestRun({s.name}-{s.id})".format(s=self)

    def _get_skipped(self):
        skip_reason_list = self._evaluate_skip_conditions()
        matches = " ".join(skip_reason_list)

        if len(skip_reason_list) == 0:
            return False
        else:
            self.status.set(STATES.SKIPPED, matches)
            self.set_run_complete()
            return True

    def _evaluate_skip_conditions(self):
        """Match grabs conditional keys from the config. It checks for
        matches and depending on the results will skip or continue a test.
        :return The match list after being populated
        :rtype list[str]"""

        match_list = []
        only_if = self.config.get('only_if', {})
        not_if = self.config.get('not_if', {})

        for key in not_if:
            # Skip any keys that were deferred.
            if resolver.TestConfigResolver.was_deferred(key):
                continue

            for val in not_if[key]:
                # Also skip deferred values.
                if resolver.TestConfigResolver.was_deferred(val):
                    continue

                if not val.endswith('$'):
                    val = val + '$'
                if bool(re.match(val, key)):
                    message = ("Skipping due to not_if match for key '{}' "
                               "with '{}'"
                               .format(key, val))
                    match_list.append(message)

        for key in only_if:
            match = False

            if resolver.TestConfigResolver.was_deferred(key):
                continue

            for val in only_if[key]:

                # We have to assume a match if one of the values is deferred.
                if resolver.TestConfigResolver.was_deferred(val):
                    match = True
                    break

                if not val.endswith('$'):
                    val = val + '$'
                if bool(re.match(val, key)):
                    match = True

            if match is False:
                message = ("Skipping because only_if key '{}' failed to match"
                           "any of '{}'"
                           .format(key, only_if[key]))
                match_list.append(message)

        return match_list  # returns list, can be empty.

    @staticmethod
    def parse_timeout(section, value):
        """Parse the timeout value from either the run or build section
        into an int (or none).
        :param str section: The config section the value came from.
        :param Union[str,None] value: The value to parse.
        """
        if value is None:
            return None
        if value.strip().isdigit():
            return int(value)

        raise TestRunError(
            "Invalid value for {} timeout. Must be a positive int."
            .format(section)
        )
