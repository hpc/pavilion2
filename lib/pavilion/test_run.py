"""Contains the TestRun class, as well as functions for getting
the list of all known test runs."""

# pylint: disable=too-many-lines

import datetime as dt
import grp
import json
import logging
import pprint
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Any

import pavilion.result.common
from pavilion import builder
from pavilion import dir_db
from pavilion import output
from pavilion import result
from pavilion import scriptcomposer
from pavilion import utils
from pavilion.permissions import PermissionsManager
from pavilion.status_file import StatusFile, STATES
from pavilion.test_config import variables
from pavilion.test_config.file_format import TestConfigError


def get_latest_tests(pav_cfg, limit):
    """Returns ID's of latest test given a limit

:param pav_cfg: Pavilion config file
:param int limit: maximum size of list of test ID's
:return: list of test ID's
:rtype: list(int)
"""

    test_dir_list = []
    runs_dir = pav_cfg.working_dir/'test_runs'
    for test_dir in dir_db.select(runs_dir)[0]:
        mtime = test_dir.stat().st_mtime
        try:
            test_id = int(test_dir.name)
        except ValueError:
            continue

        test_dir_list.append((mtime, test_id))

    test_dir_list.sort()
    return [test_id for _, test_id in test_dir_list[-limit:]]


class TestRunError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""


class TestRunNotFoundError(RuntimeError):
    """For when we try to find an existing test, but it doesn't exist."""


# pylint: disable=protected-access
def basic_attr(name, doc):
    """Create a basic attribute for the TestAttribute class. This
    will produce a property object with a getter and setter that
    simply retrieve or set the value in the self._attrs dictionary."""

    prop = property(
        fget=lambda self: self._attrs.get(name, None),
        fset=lambda self, val: self._attrs.__setitem__(name, val),
        doc=doc
    )

    return prop


class TestAttributes:
    """A object for accessing test attributes. TestRuns
    inherit from this, but it can be used by itself to access test
    information with less overhead.

    All attributes should be defined as getters and (optionally) setters.
    Getters should return None if no value is available.
    Getters should all have a docstring.

    **WARNING**

    This object is not thread or any sort of multi-processing safe. It relies
    on the expectation that the test lifecycle should generally mean there's
    only one instance of a test around that might change these values at any
    given time. The upside is that it's so unsafe, problems reveal themselves
    quickly in the unit tests.

    It's safe to set these values in the TestRun __init__, finalize,
    and gather_results.
    """

    serializers = {
        'created': utils.serialize_datetime,
        'finished': utils.serialize_datetime,
        'started': utils.serialize_datetime,
        'suite_path': lambda p: p.as_posix(),
    }

    deserializers = {
        'created': utils.deserialize_datetime,
        'finished': utils.deserialize_datetime,
        'started': utils.deserialize_datetime,
        'suite_path': Path,
    }

    def __init__(self, path: Path, group: str = None, umask: int = None):
        """
        :param path:
        """

        self.path = path
        self.group = group
        self.umask = umask

        self._attrs = {}
        self.load_attributes()

        # Set a logger more specific to this test.
        self.logger = logging.getLogger('pav.TestRun.{}'.format(path.name))

    ATTR_FILE_NAME = 'attributes'

    def save_attributes(self):
        """Save the attributes to file in the test directory."""

        attr_path = self.path/self.ATTR_FILE_NAME

        # Serialize all the values
        attrs = {}
        for key in self.list_attrs():
            val = getattr(self, key)
            if val is None:
                continue

            try:
                attrs[key] = self.serializers.get(key, lambda v: v)(val)
            except ValueError as err:
                self.logger.warning(
                    "Error serializing attribute '%s' value '%s' for test run "
                    "'%s': %s",
                    key, val, self.id, err.args[0])

        with PermissionsManager(attr_path, self.group, self.umask):
            tmp_path = attr_path.with_suffix('.tmp')
            with tmp_path.open('w') as attr_file:
                json.dump(attrs, attr_file)
            tmp_path.rename(attr_path)

    def load_attributes(self):
        """Load the attributes from file."""

        attr_path = self.path/self.ATTR_FILE_NAME

        if not attr_path.exists():
            return

        with attr_path.open() as attr_file:
            try:
                attrs = json.load(attr_file)
            except (json.JSONDecodeError, OSError, ValueError, KeyError) as err:
                raise TestRunError(
                    "Could not load attributes file: \n{}"
                    .format(err.args))

        for key, val in attrs.items():
            deserializer = self.deserializers.get(key, lambda v: v)
            try:
                self._attrs[key] = deserializer(val)
            except ValueError:
                self.logger.warning(
                    "Error deserializing attribute '%s' value '%s' for test "
                    "run '%s': %s",
                    key, val, self.id, err.args[0])

    @staticmethod
    def list_attrs():
        """List the available attributes. This always operates on the
        base RunAttributes class, so it won't contain anything from child
        classes."""

        attrs = []
        for key, val in TestAttributes.__dict__.items():
            if isinstance(val, property):
                attrs.append(key)
        attrs.sort()
        return attrs

    def attr_dict(self, include_empty=True):
        """Return the attributes as a dictionary."""

        attrs = {}
        for key in self.list_attrs():
            val = getattr(self, key)
            if val is not None or include_empty:
                attrs[key] = val

        return attrs

    @classmethod
    def attr_serializer(cls, attr) -> Callable[[Any], Any]:
        """Get the deserializer for this attribute, if any."""

        prop = cls.__dict__[attr]
        if hasattr(prop, 'serializer'):
            return prop.serializer
        else:
            return lambda d: d

    @classmethod
    def attr_deserializer(cls, attr) -> Callable[[Any], Any]:
        """Get the deserializer for this attribute, if any."""

        prop = cls.__dict__[attr]
        if hasattr(prop, 'deserializer'):
            return prop.deserializer
        else:
            return lambda d: d

    @classmethod
    def attr_doc(cls, attr):
        """Return the documentation string for the given attribute."""

        attr_prop = cls.__dict__.get(attr)

        if attr is None:
            return "Unknown attribute."

        return attr_prop.__doc__

    build_only = basic_attr(
        name='build_only',
        doc="Only build this test, never run it.")
    build_name = basic_attr(
        name='build_name',
        doc="The name of the test run's build.")
    complete = basic_attr(
        name='complete',
        doc='Whether the test run considers itself done (regardless of '
            'whether it ran).')
    created = basic_attr(
        name='created',
        doc="When the test was created.")
    finished = basic_attr(
        name='finished',
        doc="The end time for this test run.")
    id = basic_attr(
        name='id',
        doc="The test run id (unique per working_dir at any given time).")
    name = basic_attr(
        name='name',
        doc="The full name of the test.")
    rebuild = basic_attr(
        name='rebuild',
        doc="Whether or not this test will rebuild it's build.")
    result = basic_attr(
        name='result',
        doc="The PASS/FAIL/ERROR result for this test. This is kept here for"
            "fast retrieval.")
    skipped = basic_attr(
        name='skipped',
        doc="Did this test's skip conditions evaluate as 'skipped'?")
    started = basic_attr(
        name='started',
        doc="The start time for this test run.")
    suite_path = basic_attr(
        name='suite_path',
        doc="Path to the suite_file that defined this test run."
    )
    sys_name = basic_attr(
        name='sys_name',
        doc="The system this test was started on.")
    user = basic_attr(
        name='user',
        doc="The user who created this test run.")
    uuid = basic_attr(
        name='uuid',
        doc="A completely unique id for this test run (test id's can rotate).")


class TestRun(TestAttributes):
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

    :ivar int ~.id: The test id.
    :ivar dict config: The test's configuration.
    :ivar Path test.path: The path to the test's test_run directory.
    :ivar Path suite_path: The path to the test suite file that this test came
        from. May be None for artificially generated tests.
    :ivar dict results: The test results. Set None if results haven't been
        gathered.
    :ivar TestBuilder builder: The test builder object, with information on the
        test's build.
    :ivar Path build_origin_path: The path to the symlink to the original
        build directory. For bookkeeping.
    :ivar StatusFile status: The status object for this test.
    :ivar TestRunOptions opt: Test run options defined by OPTIONS_DEFAULTS
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
    :param pavilion.build_tracker.MultiBuildTracker build_tracker: Tracker for
        watching and managing the status of multiple builds.
    :param variables.VariableSetManager var_man: The variable set manager for
        this test.
    :param bool build_only: Only build this test run, do not run it.
    :param bool rebuild: After determining the build name, deprecate it and
        select a new, non-deprecated build.
    :param int _id: The test id of an existing test. (You should be using
        TestRun.load)."""

        # Just about every method needs this
        self._pav_cfg = pav_cfg
        self.scheduler = config['scheduler']

        # Create the tests directory if it doesn't already exist.
        tests_path = pav_cfg.working_dir/'test_runs'

        self.config = config

        group, umask = self.get_permissions(pav_cfg, config)

        self._validate_config()

        # Get an id for the test, if we weren't given one.
        if _id is None:
            id_tmp, run_path = dir_db.create_id_dir(tests_path, group, umask)
            super().__init__(
                path=run_path,
                group=group, umask=umask)

            # Set basic attributes
            self.id = id_tmp  # pylint: disable=invalid-name
            self.build_only = build_only
            self.complete = False
            self.created = dt.datetime.now()
            self.name = self.make_name(config)
            self.rebuild = rebuild
            self.suite_path = Path(config.get('suite_path', '.'))
            self.user = utils.get_login()
            self.uuid = str(uuid.uuid4())
        else:
            # Load the test info from the given id path.
            super().__init__(
                path=dir_db.make_id_path(tests_path, _id),
                group=group, umask=umask)
            self.load_attributes()

        self.test_version = config.get('test_version')

        if not self.path.is_dir():
            raise TestRunNotFoundError(
                "No test with id '{}' could be found.".format(self.id))

        # Mark the run to build locally.
        self.build_local = config.get('build', {}) \
                                 .get('on_nodes', 'false').lower() != 'true'

        self._variables_path = self.path / 'variables'

        if _id is None:
            with PermissionsManager(self.path, self.group, self.umask):
                self._save_config()
                if var_man is None:
                    var_man = variables.VariableSetManager()
                self.var_man = var_man
                self.var_man.save(self._variables_path)

            self.sys_name = self.var_man.get('sys_name', '<unknown>')
        else:
            try:
                self.var_man = variables.VariableSetManager.load(
                    self._variables_path)
            except RuntimeError as err:
                raise TestRunError(*err.args)

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

        self.run_log = self.path/'run.log'
        self.build_log = self.path/'build.log'
        self.results_log = self.path/'results.log'
        self.results_path = self.path/'results.json'
        self.build_origin_path = self.path/'build_origin'
        self.build_timeout_file = config.get('build', {}).get('timeout_file')

        # Use run.log as the default run timeout file
        self.timeout_file = self.run_log
        run_timeout_file = config.get('run', {}).get('timeout_file')
        if run_timeout_file is not None:
            self.timeout_file = self.path/run_timeout_file

        build_config = self.config.get('build', {})

        self.build_script_path = self.path/'build.sh'  # type: Path
        self.build_path = self.path/'build'
        if _id is None:
            self._write_script(
                'build',
                path=self.build_script_path,
                config=build_config)

        try:
            self.builder = builder.TestBuilder(
                pav_cfg=pav_cfg,
                test=self,
                mb_tracker=build_tracker,
                build_name=self.build_name
            )
            self.build_name = self.builder.name
        except builder.TestBuilderError as err:
            raise TestRunError(
                "Could not create builder for test {s.name} (run {s.id}): {err}"
                .format(s=self, err=err)
            )

        run_config = self.config.get('run', {})
        self.run_tmpl_path = self.path/'run.tmpl'
        self.run_script_path = self.path/'run.sh'

        if _id is None:
            self._write_script(
                'run',
                path=self.run_tmpl_path,
                config=run_config)

        if _id is None:
            self.save_attributes()
            self.status.set(STATES.CREATED, "Test directory setup complete.")

        self._results = None

        self.skipped = self._get_skipped()  # eval skip.

    def _validate_config(self):
        """Validate test configs, specifically those that are spack related."""

        spack_path = self._pav_cfg.get('spack_path', None)
        spack_enable = self.spack_enabled()
        if spack_enable and spack_path is None:
            raise TestRunError("Spack cannot be enabled without 'spack_path' "
                               "being defined in the pavilion config.")

    @classmethod
    def load(cls, pav_cfg, test_id):
        """Load an old TestRun object given a test id.

        :param pav_cfg: The pavilion config
        :param int test_id: The test's id number.
        :rtype: TestRun
        """

        path = dir_db.make_id_path(pav_cfg.working_dir / 'test_runs', test_id)

        if not path.is_dir():
            raise TestRunError("Test directory for test id {} does not exist "
                               "at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        return TestRun(pav_cfg, config, _id=test_id)

    def _finalize(self):
        """Resolve any remaining deferred variables, and generate the final
        run script.

        DO NOT USE THIS DIRECTLY - Use the resolver finalize method, which
            will call this.
        """

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
                with PermissionsManager(file_path, self.group, self.umask), \
                        file_path.open('w') as file_:

                    for line in contents:
                        file_.write("{}\n".format(line))

        if not self.skipped:
            self.skipped = self._get_skipped()

        self.save_attributes()

        self._write_script(
            'run',
            self.run_script_path,
            self.config['run'],
        )

    @staticmethod
    def get_permissions(pav_cfg, config) -> (str, int):
        """Get the permissions to use on file creation, either from the
        pav_cfg or test config it that overrides.
        :returns: A tuple of the group and umask.
        """

        # If a test access group was given, make sure it exists and the
        # current user is a member.
        group = config.get('group', pav_cfg['shared_group'])
        if group is not None:
            try:
                group_data = grp.getgrnam(group)
                user = utils.get_login()
                if group != user and user not in group_data.gr_mem:
                    raise TestConfigError(
                        "Test specified group '{}', but the current user '{}' "
                        "is not a member of that group."
                        .format(group, user))
            except KeyError as err:
                raise TestConfigError(
                    "Test specified group '{}', but that group does not "
                    "exist on this system. {}"
                    .format(group, err))

        umask = config.get('umask')
        if umask is None:
            umask = pav_cfg['umask']
        if umask is not None:
            try:
                umask = int(umask, 8)
            except ValueError:
                raise RuntimeError(
                    "Invalid umask. This should have been enforced by the "
                    "by the config format.")
        else:
            umask = 0o077

        return group, umask

    @staticmethod
    def make_name(config):
        """Create the name for the build given the configuration values."""

        name_parts = [
            config.get('suite', '<unknown>'),
            config.get('name', '<unnamed>'),
        ]
        subtitle = config.get('subtitle')
        # Don't add undefined or empty subtitles.
        if subtitle:
            name_parts.append(subtitle)

        return '.'.join(name_parts)

    def run_cmd(self):
        """Construct a shell command that would cause pavilion to run this
        test."""

        pav_path = self._pav_cfg.pav_root/'bin'/'pav'

        return '{} run {}'.format(pav_path, self.id)

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = self.path/'config'

        # make lock
        tmp_path = config_path.with_suffix('.tmp')

        try:
            with PermissionsManager(config_path, self.group, self.umask), \
                    tmp_path.open('w') as json_file:
                output.json_dump(self.config, json_file)
                try:
                    config_path.unlink()
                except OSError:
                    pass
                tmp_path.rename(config_path)
        except (OSError, IOError) as err:
            raise TestRunError(
                "Could not save TestRun ({}) config at {}: {}"
                .format(self.name, self.path, err))
        except TypeError as err:
            raise TestRunError(
                "Invalid type in config for ({}): {}"
                .format(self.name, err))

    @classmethod
    def _load_config(cls, test_path):
        """Load a saved test configuration."""
        config_path = test_path/'config'

        if not config_path.is_file():
            raise TestRunError("Could not find config file for test at {}."
                               .format(test_path))

        try:
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

    def spack_enabled(self):
        """Check if spack is being used by this test run."""

        spack_build = self.config.get('build', {}).get('spack', {})
        spack_run = self.config.get('run', {}).get('spack', {})
        return (spack_build.get('install', [])
                or spack_build.get('load', [])
                or spack_run.get('load', []))

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
            build_result = True
        else:
            with PermissionsManager(self.build_path, self.group, self.umask):
                self.builder.fail_path.rename(self.build_path)
                for file in utils.flat_walk(self.build_path):
                    file.chmod(file.stat().st_mode | 0o200)
                build_result = False

        self.build_log.symlink_to(self.build_path/'pav_build_log')
        return build_result

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

            self.started = dt.datetime.now()

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
                    if self.timeout_file.exists():
                        timeout_file = self.timeout_file
                    else:
                        timeout_file = self.run_log

                    try:
                        out_stat = timeout_file.stat()
                        quiet_time = time.time() - out_stat.st_mtime
                    except OSError:
                        pass

                    # Has the output file changed recently?
                    if self.run_timeout < quiet_time:
                        # Give up on the build, and call it a failure.
                        proc.kill()
                        msg = ("Run timed out after {} seconds"
                               .format(self.run_timeout))
                        self.status.set(STATES.RUN_TIMEOUT, msg)
                        self.finished = dt.datetime.now()
                        self.save_attributes()
                        raise TimeoutError(msg)
                    else:
                        # Only wait a max of run_silent_timeout next 'wait'
                        timeout = timeout - quiet_time

        self.finished = dt.datetime.now()
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
        complete_path = self.path/self.COMPLETE_FN
        complete_tmp_path = complete_path.with_suffix('.tmp')
        with PermissionsManager(complete_tmp_path, self.group, self.umask), \
                complete_tmp_path.open('w') as run_complete:
            json.dump(
                {'complete': dt.datetime.now().isoformat()},
                run_complete)
        complete_tmp_path.rename(complete_path)

        self.complete = True
        self.save_attributes()

    def check_run_complete(self):
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
            if self.check_run_complete() is not None:
                return

            time.sleep(self.WAIT_INTERVAL)

            if timeout is not None and time.time() > timeout:
                raise TimeoutError("Timed out waiting for test '{}' to "
                                   "complete".format(self.id))

    def gather_results(self, run_result, regather=False, log_file=None):
        """Process and log the results of the test, including the default set
of result keys.

:param int run_result: The return code of the test run.
:param bool regather: Gather results without performing any changes to the
    test itself.
:param IO[str] log_file: The file to save result logs to.
"""
        if self.finished is None:
            raise RuntimeError(
                "test.gather_results can't be run unless the test was run"
                "(or an attempt was made to run it. "
                "This occurred for test {s.name}, #{s.id}"
                .format(s=self)
            )

        parser_configs = self.config['result_parse']

        result_log = utils.IndentedLog(log_file)

        result_log("Gathering base results.")
        results = result.base_results(self)

        results['return_value'] = run_result

        result_log("Base results:")
        result_log.indent = 1
        result_log(pprint.pformat(results))

        if not regather:
            self.status.set(STATES.RESULTS,
                            "Parsing {} result types."
                            .format(len(parser_configs)))

        try:
            result.parse_results(self, results, log=result_log)
        except pavilion.result.common.ResultError as err:
            results['result'] = self.ERROR
            results['pav_result_errors'].append(
                "Error parsing results: {}".format(err.args[0]))
            if not regather:
                self.status.set(STATES.RESULTS_ERROR,
                                results['pav_result_errors'][-1])

        if not regather:
            self.status.set(STATES.RESULTS,
                            "Performing {} result evaluations."
                            .format(len(self.config['result_evaluate'])))
        try:
            result.evaluate_results(
                results,
                self.config['result_evaluate'],
                result_log
            )
        except pavilion.result.common.ResultError as err:
            results['result'] = self.ERROR
            results['pav_result_errors'].append(err.args[0])
            if not regather:
                self.status.set(STATES.RESULTS_ERROR,
                                results['pav_result_errors'][-1])

        if results['result'] is True:
            results['result'] = self.PASS
        elif results['result'] is False:
            results['result'] = self.FAIL
        else:
            results['pav_result_errors'].append(
                "The value for the 'result' key in the results must be a "
                "boolean. Got '{}' instead".format(results['result']))
            results['result'] = self.ERROR

        result_log("Set final result key to: '{}'".format(results['result']))
        result_log("See results.json for the final result json.")

        result_log("Removing temporary values.")
        result_log.indent = 1
        result.remove_temp_results(results, result_log)

        self._results = results

        return results

    def save_results(self, results):
        """Save the results to the test specific results file and the general
        pavilion results file.

        :param dict results: The results dictionary.
        """

        results_tmp_path = self.results_path.with_suffix('.tmp')
        with PermissionsManager(results_tmp_path, self.group, self.umask), \
                results_tmp_path.open('w') as results_file:
            json.dump(results, results_file)
        try:
            self.results_path.unlink()
        except OSError:
            pass
        results_tmp_path.rename(self.results_path)

        self.result = results.get('result')
        self.save_attributes()

        result_logger = logging.getLogger('common_results')
        if self._pav_cfg.get('flatten_results') and results.get('per_file'):
            # Flatten 'per_file' results into separate result records.
            base = results.copy()
            del base['per_file']

            for per_file, values in results['per_file'].items():
                per_result = base.copy()
                per_result['file'] = per_file
                per_result.update(values)

                result_logger.info(output.json_dumps(per_result))
        else:
            result_logger.info(output.json_dumps(results))

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
        if self.results_path.exists() and (
                self._results is None or self._results['result'] is None):
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
            with PermissionsManager(path, self.group, self.umask), \
                    path.open('w') as job_id_file:
                job_id_file.write(job_id)
        except (IOError, OSError) as err:
            self.logger.error("Could not write jobid file '%s': %s",
                              path, err)

        self._job_id = job_id

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

        if self.spack_enabled():
            spack_commands = config.get('spack', {})
            install_packages = spack_commands.get('install', [])
            load_packages = spack_commands.get('load', [])

            script.newline()
            script.comment('Source spack setup script.')
            script.command('source {}/share/spack/setup-env.sh'
                           .format(self._pav_cfg.get('spack_path')))
            script.newline()
            script.command('spack env deactivate &>/dev/null')
            script.comment('Activate spack environment.')
            script.command('spack env activate -d .')
            script.command('if [ -z $SPACK_ENV ]; then exit 1; fi')

            if install_packages:
                script.newline()
                script.comment('Install spack packages.')
                for package in install_packages:
                    script.command('spack install -v --fail-fast {} || exit 1'
                                   .format(package))

            if load_packages:
                script.newline()
                script.comment('Load spack packages.')
                for package in load_packages:
                    script.command('spack load {} || exit 1'
                                   .format(package))

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

    def __repr__(self):
        return "TestRun({s.name}-{s.id})".format(s=self)

    def _get_skipped(self):
        """Kicks off assessing if current test is skipped."""

        if self.skipped:
            return True

        skip_reason_list = self._evaluate_skip_conditions()
        matches = " ".join(skip_reason_list)

        if len(skip_reason_list) == 0:
            return False
        else:
            self.set_skipped(matches)
            return True

    def set_skipped(self, reason: str):
        """Set the test as skipped (and complete).
        :param reason: Why the test is being skipped.
        """

        self.status.set(STATES.SKIPPED, reason)
        self.skipped = True
        self.set_run_complete()

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
            if variables.DeferredVariable.was_deferred(key):
                continue

            for val in not_if[key]:
                # Also skip deferred values.
                if variables.DeferredVariable.was_deferred(val):
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

            if variables.DeferredVariable.was_deferred(key):
                continue

            for val in only_if[key]:

                # We have to assume a match if one of the values is deferred.
                if variables.DeferredVariable.was_deferred(val):
                    match = True
                    break

                if not val.endswith('$'):
                    val = val + '$'
                if bool(re.match(val, key)):
                    match = True

            if match is False:
                message = ("Skipping because only_if key '{}' failed to match "
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
