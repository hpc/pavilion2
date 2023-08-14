"""Contains the TestRun class, as well as functions for getting
the list of all known test runs."""

# pylint: disable=too-many-lines
import copy
import json
import logging
import pprint
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import TextIO, Union, Dict
import yc_yaml as yaml

from pavilion.config import PavConfig
from pavilion import builder
from pavilion import dir_db
from pavilion import errors
from pavilion import output
from pavilion import result
from pavilion import scriptcomposer
from pavilion import utils
from pavilion import create_files
from pavilion import resolve
from pavilion.build_tracker import BuildTracker, MultiBuildTracker
from pavilion.deferred import DeferredVariable
from pavilion.errors import TestRunError, TestRunNotFoundError, TestConfigError, ResultError, \
    VariableError
from pavilion.jobs import Job
from pavilion.variables import VariableSetManager
from pavilion.status_file import TestStatusFile, STATES
from pavilion.test_config.file_format import NO_WORKING_DIR
from pavilion.test_config.utils import parse_timeout
from pavilion.types import ID_Pair
from .test_attrs import TestAttributes


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

    :ivar int ~.id: The test id number.
    :ivar str ~.full_id: The full test id number, including the config label. This
        may also be a string path to the test itself.
    :ivar str cfg_label: The config label for the configuration directory that
        defined this test. This is ephemeral, and may change between Pavilion
        invocations based on available configurations.
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

    RUN_DIR = 'test_runs'

    NO_LABEL = '_none'

    STATUS_FN = 'status'
    """File that tracks the tests's status."""

    CANCEL_FN = 'cancel'
    """File that indicates that the test was cancelled."""

    JOB_FN = 'job'
    """Link to the test's scheduler job."""

    BUILD_TEMPLATE_DIR = 'templates'
    """Directory that holds build templates."""

    def __init__(self, pav_cfg: PavConfig, config, var_man=None,
                 _id=None, rebuild=False, build_only=False):
        """Create an new TestRun object. If loading an existing test
    instance, use the ``TestRun.from_id()`` method.

    :param pav_cfg: The pavilion configuration.
    :param dict config: The test configuration dictionary.
    :param bool build_only: Only build this test run, do not run it.
    :param bool rebuild: After determining the build name, deprecate it and
        select a new, non-deprecated build.
    :param int _id: The test id of an existing test. (You should be using
        TestRun.load)."""

        self.saved = False

        new_test = _id is None

        # Just about every method needs this
        self._pav_cfg = pav_cfg
        self.scheduler = config['scheduler']

        # Get the working dir specific to where this test came from.
        if config.get('working_dir', NO_WORKING_DIR) == NO_WORKING_DIR:
            self.working_dir = Path(self._pav_cfg['working_dir'])
        else:
            self.working_dir = Path(config['working_dir'])

        tests_path = self.working_dir/self.RUN_DIR

        self.config = config
        self._validate_config()

        # Get an id for the test, if we weren't given one.
        if new_test:
            # These will be set by save() or on load.
            try:
                id_tmp, run_path = dir_db.create_id_dir(tests_path)
            except (OSError, TimeoutError) as err:
                raise TestRunError("Could not create test id directory at '{}'"
                                   .format(tests_path), err)
            super().__init__(path=run_path, load=False)
            self._variables_path = self.path / 'variables'
            self.var_man = None
            self.status = None
            self.builder = None
            self.build_name = None

            # Set basic attributes
            self.id = id_tmp  # pylint: disable=invalid-name
            self.build_only = build_only
            self._complete = False
            self.created = time.time()
            self.name = self.make_name(config)
            self.rebuild = rebuild
            self.cfg_label = config.get('cfg_label', self.NO_LABEL)
            suite_path = config.get('suite_path')
            if suite_path == '<no_suite>' or suite_path is None:
                self.suite_path = Path('..')
            else:
                self.suite_path = Path(suite_path)
            self.user = utils.get_login()
            self.uuid = str(uuid.uuid4())

            if var_man is None:
                var_man = VariableSetManager()
            self.var_man = var_man
        else:
            # Load the test info from the given id path.
            super().__init__(path=dir_db.make_id_path(tests_path, _id))
            if not self.path.is_dir():
                raise TestRunNotFoundError(
                    "No test with id '{}' could be found.".format(self.id))

            self._variables_path = self.path / 'variables'
            self.status = TestStatusFile(self.path / self.STATUS_FN)
            self.suite_path = self.suite_path

            try:
                self.var_man = VariableSetManager.load(self._variables_path)
            except VariableError as err:
                raise TestRunError("Error loading variable set for test {}".format(self.id),
                                   err)

        self.sys_name = self.var_man.get('sys_name', '<unknown>')

        self.test_version = config.get('test_version')

        # Mark the run to build locally.
        self.build_local = config.get('build', {}) \
                                 .get('on_nodes', 'false').lower() != 'true'

        run_timeout = config.get('run', {}).get('timeout', '300')
        try:
            self.run_timeout = parse_timeout(run_timeout)
        except ValueError:
            raise TestRunError("Invalid run timeout value '{}' for test {}"
                               .format(run_timeout, self.name))

        self.run_log = self.path/'run.log'
        self.build_log = self.path/'build.log'
        self.results_log = self.path/'results.log'
        self.build_origin_path = self.path/'build_origin'

        # Use run.log as the default run timeout file
        self.timeout_file = self.run_log
        run_timeout_file = config.get('run', {}).get('timeout_file')
        if run_timeout_file is not None:
            self.timeout_file = self.path/run_timeout_file

        self.permute_vars = self._get_permute_vars()

        self.build_script_path = self.path/'build.sh'  # type: Path
        self.build_path = self.path/'build'

        self.run_tmpl_path = self.path/'run.tmpl'
        self.run_script_path = self.path/'run.sh'

        if not new_test:
            self.builder = self._make_builder()

        # This will be set by the scheduler
        self._job = None

        self._results = None

        self.skip_reasons = self._evaluate_skip_conditions()
        self.skipped = len(self.skip_reasons) != 0

    @property
    def id_pair(self) -> ID_Pair:
        """Returns an ID_pair (a tuple of the working dir and test id)."""
        return ID_Pair((self.working_dir, self.id))

    @property
    def series(self) -> Union[str, None]:
        """Return the series id that this test belongs to. Returns None if it doesn't
        belong to any series."""

        series_path = self.path/'series'
        if series_path.exists():
            series = series_path.resolve().name
            try:
                series = int(series)
            except ValueError:
                return None
            return 's{}'.format(series)
        else:
            return None

    def save(self):
        """Save the test configuration to file and create the builder. This
        essentially separates out a filesystem operations from creating a test,
        with the exception of creating the initial id directory. This
        should generally only be called once, after we create the test and
        make sure we actually want it."""

        if self.skipped:
            raise RuntimeError("Skipped tests should never be saved.")

        deferred_errors = self.var_man.get('sched.errors')
        if deferred_errors is not None:
            raise TestRunError("Errors were found when creating test {}.\n{}"
                               .format(self.name, deferred_errors))

        self._save_config()
        self.var_man.save(self._variables_path)
        # Setup the initial status file.
        self.status = TestStatusFile(self.path / self.STATUS_FN)
        self.status.set(STATES.CREATED,
                        "Test directory and status file created.")

        self._write_script(
            'build',
            path=self.build_script_path,
            config=self.config.get('build', {}),
            module_wrappers=self.config.get('module_wrappers', {}))

        self.builder = self._make_builder()
        self.build_name = self.builder.name

        self._write_script(
            'run',
            path=self.run_tmpl_path,
            config=self.config.get('run', {}),
            module_wrappers=self.config.get('module_wrappers', {}))

        self.save_attributes()
        self.status.set(STATES.CREATED, "Test directory setup complete.")

        self.saved = True

    def _make_builder(self):

        spack_config = (self.config.get('spack_config', {}) if self.spack_enabled()
                        else None)
        if self.suite_path != Path('..') and self.suite_path is not None:
            download_dest = self.suite_path.parents[1] / 'test_src'
        else:
            download_dest = None

        templates = self._create_build_templates()

        try:
            test_builder = builder.TestBuilder(
                pav_cfg=self._pav_cfg,
                config=self.config.get('build', {}),
                script=self.build_script_path,
                spack_config=spack_config,
                status=self.status,
                download_dest=download_dest,
                working_dir=self.working_dir,
                templates=templates,
                build_name=self.build_name,
            )
        except errors.TestBuilderError as err:
            raise TestRunError(
                "Could not create builder for test {s.name} (run {s.id}): {err}"
                .format(s=self, err=err)
            )

        return test_builder

    def _create_build_templates(self) -> Dict[Path, Path]:
        """Generate templated files for the builder to use."""

        templates = self.config.get('build', {}).get('templates', {})
        tmpl_dir = self.path/self.BUILD_TEMPLATE_DIR
        if templates:
            if not tmpl_dir.exists():
                try:
                    tmpl_dir.mkdir(exist_ok=True)
                except OSError as err:
                    raise TestRunError("Could not create build template directory", err)

        tmpl_paths = {}
        for tmpl_src, tmpl_dest in templates.items():
            if not (tmpl_dir/tmpl_dest).exists():
                try:
                    tmpl = create_files.resolve_template(self._pav_cfg, tmpl_src, self.var_man)
                    create_files.create_file(tmpl_dest, tmpl_dir, tmpl, newlines='')
                except TestConfigError as err:
                    raise TestRunError("Error resolving Build template files", err)
            tmpl_paths[tmpl_dir/tmpl_dest] = tmpl_dest

        return tmpl_paths

    def _validate_config(self):
        """Validate test configs, specifically those that are spack related."""

        spack_path = self._pav_cfg.get('spack_path')
        spack_enable = self.spack_enabled()
        if spack_enable and spack_path is None:
            raise TestRunError("Spack cannot be enabled without 'spack_path' "
                               "being defined in the pavilion config.")

    @classmethod
    def parse_raw_id(cls, pav_cfg, raw_test_id: str) -> ID_Pair:
        """Parse a raw test run id and return the label, working_dir, and id
        for that test. The test run need not exist, but the label must."""

        parts = raw_test_id.split('.', 1)
        if not parts:
            raise TestRunNotFoundError("Blank test run id given")
        elif len(parts) == 1:
            cfg_label = 'main'
            test_id = parts[0]
        else:
            cfg_label, test_id = parts

        try:
            test_id = int(test_id)
        except ValueError:
            raise TestRunNotFoundError("Invalid test id with label '{}': '{}'"
                                       .format(cfg_label, test_id))

        if cfg_label not in pav_cfg.configs:
            raise TestRunNotFoundError(
                "Invalid test label: '{}', label not found. Valid labels are {}"
                .format(cfg_label, tuple(pav_cfg.configs.keys())))

        working_dir = pav_cfg.configs[cfg_label]['working_dir']

        return ID_Pair((working_dir, test_id))

    @classmethod
    def load_from_raw_id(cls, pav_cfg, raw_test_id: str) -> 'TestRun':
        """Load a test given a raw test id string, in the form
        [label].test_id. The optional label will allow us to look up the config
        path for the test."""

        working_dir, test_id = cls.parse_raw_id(pav_cfg, raw_test_id)

        return cls.load(pav_cfg, working_dir, test_id)

    @classmethod
    def load(cls, pav_cfg, working_dir: Path, test_id: int) -> 'TestRun':
        """Load an old TestRun object given a test id.

        :param pav_cfg: The pavilion config
        :param working_dir: The working directory where this test run lives.
        :param int test_id: The test's id number.
        :rtype: TestRun
        """

        path = dir_db.make_id_path(working_dir / cls.RUN_DIR, test_id)

        if not path.is_dir():
            raise TestRunError("Test directory for test id {} does not exist "
                               "at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        test_run = TestRun(pav_cfg, config, _id=test_id)
        test_run.saved = True
        # Force the completion check to ensure that ._complete is populated.

        return test_run

    def finalize(self, new_vars: VariableSetManager):
        """Resolve any remaining deferred variables, and generate the final
        run script.

        DO NOT USE THIS DIRECTLY - Use the resolver finalize method, which
            will call this.
        """

        self.var_man.undefer(new_vars)
        self.config = resolve.deferred(self.config, self.var_man)

        if not self.saved:
            raise RuntimeError("You must call the 'test.save()' method before "
                               "you can finalize a test. Test: {}".format(self.full_id))

        self._save_config()
        # Save our newly updated variables.
        self.var_man.save(self._variables_path)

        for file, contents in self.config['run'].get('create_files', {}).items():
            try:
                create_files.create_file(file, self.build_path, contents)
            except TestConfigError as err:
                raise TestRunError("Test run '{}' Could not create build script."
                                   .format(self.full_id), err)

        for tmpl_src, tmpl_dest in self.config['run'].get('templates', {}).items():
            try:
                tmpl = create_files.resolve_template(self._pav_cfg, tmpl_src, self.var_man)
                create_files.create_file(tmpl_dest, self.build_path, tmpl, newlines='')
            except TestConfigError as err:
                raise TestRunError("Test run '{}' could not create run script."
                                   .format(self.full_id, err))

        self.save_attributes()

        self._write_script(
            'run',
            self.run_script_path,
            self.config['run'],
            self.config.get('module_wrappers', {})
        )

    @staticmethod
    def make_name(config):
        """Create the name for the test run given the configuration values."""

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

        return '{} run {}'.format(pav_path, self.full_id)

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = self.path/'config'

        # make lock
        tmp_path = config_path.with_suffix('.tmp')

        # De-normalize variable values. YAML doesn't support None as a dictionary key.
        config = copy.deepcopy(self.config)
        variables = config.get('variables', {})
        for var_key in variables:
            new_list = []
            for item in variables[var_key]:
                if None in item:
                    new_list.append(item[None])
                else:
                    # Yaml doesn't know what to do with our SubVarDict objects.
                    # At this point though, they can be fully resolved into normal
                    # dictionaries.
                    new_list.append(dict(item))
            config['variables'][var_key] = new_list

        try:
            with tmp_path.open('w') as config_file:

                yaml.dump(config, config_file)
        except (OSError, IOError) as err:
            raise TestRunError(
                "Could not save TestRun ({}) config at {}"
                .format(self.name, self.path), err)
        except TypeError as err:
            raise TestRunError(
                "Invalid type in config for ({})"
                .format(self.name), err)

        try:
            config_path.unlink()
        except (OSError, FileNotFoundError):
            pass

        start = time.time()
        while time.time() - start < 100:
            try:
                tmp_path.rename(config_path)
                break
            except FileNotFoundError:
                continue

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
                config = yaml.load(config_file)
        except TypeError as err:
            raise TestRunError("Bad config values for config '{}'"
                               .format(config_path), err)
        except (IOError, OSError) as err:
            raise TestRunError("Error reading config file '{}'"
                               .format(config_path), err)

        # Re-normalize variable values.
        variables = config.get('variables', {})
        for var_key in variables:
            new_list = []
            for item in variables[var_key]:
                if isinstance(item, str):
                    new_list.append({None: item})
                else:
                    new_list.append(item)
            variables[var_key] = new_list

        return config

    def spack_enabled(self):
        """Check if spack is being used by this test run."""

        spack_build = self.config.get('build', {}).get('spack', {})
        spack_run = self.config.get('run', {}).get('spack', {})
        return bool(spack_build.get('install', [])
                    or spack_build.get('load', [])
                    or spack_run.get('load', []))

    def build(self, cancel_event=None, tracker: BuildTracker = None):
        """Build the test using its builder object and symlink copy it to
        it's final location. The build tracker will have the latest
        information on any encountered errors.

        :param threading.Event cancel_event: Event to tell builds when to die.
        :param tracker: A build tracker for tracking multi-threaded builds.

        :returns: True if build successful
        """

        if tracker is None:
            mb_tracker = MultiBuildTracker()
            tracker = mb_tracker.register(self)

        if not self.saved:
            raise RuntimeError("The .save() method must be called before you "
                               "can build test '{}'".format(self.full_id))

        if self.build_origin_path.exists():
            raise RuntimeError(
                "Whatever called build() is calling it for a second time. "
                "This should never happen for a given test run ({s.id})."
                .format(s=self))

        if cancel_event is None:
            cancel_event = threading.Event()

        if self.builder.build(self.full_id, tracker=tracker,
                              cancel_event=cancel_event):
            # Create the build origin path, to make tracking a test's build
            # a bit easier.
            self.build_origin_path.symlink_to(self.builder.path)

            # Make a file with the test id of the building test.
            built_by_path = self.build_origin_path / '.built_by'
            try:
                if not built_by_path.exists():
                    with built_by_path.open('w') as built_by:
                        built_by.write(str(self.full_id))
                    built_by_path.chmod(0o440)
            except OSError as err:
                tracker.warn("Could not create built_by file: {}".format(err.args),
                             state=self.status.states.WARNING)

            try:
                self.builder.copy_build(self.build_path)
            except errors.TestBuilderError as err:
                tracker.fail("Error copying build: {}".format(err.args[0]))
                cancel_event.set()
            build_success = True

        else:
            try:
                self.builder.fail_path.rename(self.build_path)
            except OSError as err:
                tracker.error("Could not move failed build: {}".format(err))

            for file in utils.flat_walk(self.build_path):
                try:
                    file.chmod(file.stat().st_mode | 0o220)
                except FileNotFoundError:
                    # Builds can have symlinks that point to non-existent files.
                    pass
            build_success = False

        self.build_log.symlink_to(self.build_path/'pav_build_log')

        if build_success:
            self.status.set(STATES.BUILD_DONE, "Build is complete.")

        if self.build_only or not build_success:
            self.set_run_complete()

        return build_success

    RUN_WAIT_MAX = 1
    # The maximum wait time before checking things like test cancellation

    def run(self):
        """Run the test.

        :rtype: bool
        :returns: The return code of the test command.
        :raises TimeoutError: When the run times out.
        :raises TestRunError: We don't actually raise this, but might in the
            future.
        """

        # Don't even try to run a cancelled test.
        if self.cancelled:
            return

        if not self.saved:
            raise RuntimeError("You must call the .save() method before running "
                               "test {}".format(self.full_id))

        if self.build_only:
            self.status.set(
                STATES.RUN_ERROR,
                "Tried to run a 'build_only' test object.")
            return False

        self.status.set(STATES.PREPPING_RUN,
                        "Converting run template into run script.")

        with self.run_log.open('wb') as run_log:
            self.status.set(STATES.RUNNING,
                            "Starting the run script.")

            self.started = time.time()

            # Set the working directory to the build path, if there is one.
            run_wd = None
            if self.build_path is not None:
                run_wd = self.build_path.as_posix()

            # Run scripts take the test id as a first argument.
            cmd = [self.run_script_path.as_posix(), self.full_id]
            proc = subprocess.Popen(cmd,
                                    cwd=run_wd,
                                    stdout=run_log,
                                    stderr=subprocess.STDOUT)

            self.status.set(STATES.RUNNING,
                            "Currently running.")

            # Run the test, but timeout if it doesn't produce any output every
            # self._run_timeout seconds
            if self.run_timeout is None or self.run_timeout > self.RUN_WAIT_MAX:
                timeout = self.RUN_WAIT_MAX
            else:
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
                    if self.run_timeout is not None:
                        if self.run_timeout < quiet_time:
                            # Give up on the build, and call it a failure.
                            proc.kill()
                            msg = ("Run timed out after {} seconds"
                                   .format(self.run_timeout))
                            self.status.set(STATES.RUN_TIMEOUT, msg)
                            self.finished = time.time()
                            self.save_attributes()
                            raise TimeoutError(msg)
                        elif self.cancelled:
                            proc.kill()
                            self.status.set(
                                STATES.SCHED_CANCELLED,
                                "Test cancelled mid-run.")
                            self.finished = time.time()
                            self.save_attributes()
                            self.set_run_complete()
                        else:
                            # Only wait a max of run_silent_timeout next 'wait'
                            timeout = max(self.run_timeout - quiet_time,
                                          self.RUN_WAIT_MAX)

        self.finished = time.time()
        self.save_attributes()

        if ret == 0:
            if not self.status.has_state(STATES.CANCELLED):
                self.status.set(STATES.RUN_DONE,
                                "Test run has completed.")

        return ret

    def set_run_complete(self):
        """Write a file in the test directory that indicates that the test
    has completed a run, one way or another. This should only be called
    when we're sure their won't be any more status changes."""

        if self.complete:
            return

        if not self.saved:
            raise RuntimeError("You must call the .save() method before run {} "
                               "can be marked complete.".format(self.full_id))

        # Write the current time to the file. We don't actually use the contents
        # of the file, but it's nice to have another record of when this was
        # run.
        complete_path = self.path/self.COMPLETE_FN
        complete_tmp_path = complete_path.with_suffix('.tmp')
        with complete_tmp_path.open('w') as run_complete:
            json.dump(
                {'complete': time.time()},
                run_complete)
        complete_tmp_path.rename(complete_path)

        self._complete = True

    def cancel(self, reason: str):
        """Set the cancel file for this test, and denote in its status that it was
        cancelled."""

        if self.cancelled or self.complete:
            # Already cancelled.
            return

        # There is a race condition here that at worst results in multiple status
        # entries.
        self.status.set(STATES.CANCELLED, reason)

        cancel_file = self.path/self.CANCEL_FN
        cancel_file.touch()

    @property
    def cancelled(self):
        """Return true if the test is cancelled, false otherwise."""

        return (self.path/self.CANCEL_FN).exists()

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
            if self.complete:
                return

            time.sleep(self.WAIT_INTERVAL)

            if timeout is not None and time.time() > timeout:
                raise TimeoutError("Timed out waiting for test '{}' to "
                                   "complete".format(self.full_id))

    def gather_results(self, run_result: int, regather: bool = False,
                       log_file: TextIO = None):
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
                .format(s=self))

        parser_configs = self.config['result_parse']

        result_log = utils.IndentedLog()

        result_log("Gathering base results.")
        results = result.base_results(self)

        results['return_value'] = run_result

        result_log("Base results:")
        result_log.indent(pprint.pformat(results))

        if not regather:
            self.status.set(STATES.RESULTS,
                            "Parsing {} result types."
                            .format(len(parser_configs)))

        try:
            result.parse_results(self._pav_cfg, self, results, base_log=result_log)
        except ResultError as err:
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
        except ResultError as err:
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
        result.remove_temp_results(results, result_log)

        self._results = results

        if log_file is not None:
            result_log.save(log_file)

        return results

    def save_results(self, results):
        """Save the results to the test specific results file and the general
        pavilion results file.

        :param dict results: The results dictionary.
        """

        if not self.saved:
            raise RuntimeError("You must call the .save() method before saving "
                               "results for test {}".format(self.full_id))

        results_tmp_path = self.results_path.with_suffix('.tmp')
        with results_tmp_path.open('w') as results_file:
            json.dump(results, results_file)
        try:
            self.results_path.unlink()
        except OSError:
            pass
        results_tmp_path.rename(self.results_path)

        self._results = results
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
    def job(self):
        """The job id of this test (saved to a ``jobid`` file). This should
be set by the scheduler plugin as soon as it's known."""

        if self._job is None:
            job_path = self.path/self.JOB_FN
            if job_path.exists():
                self._job = Job(job_path)
            else:
                return None

        return self._job

    @job.setter
    def job(self, job: Job):

        job_path = self.path/self.JOB_FN

        if job_path.exists():
            raise RuntimeError("Jobs should only ever be set once per test run, when "
                               "that test is scheduled.")

        try:
            job_path.symlink_to(job.path.resolve())
        except OSError as err:
            self._add_warning("Could not create job link: {}".format(err))

        self._job = job

    @property
    def complete_time(self):
        """Returns the completion time from the completion file."""

        if not self.complete:
            return None

        run_complete_path = self.path/self.COMPLETE_FN

        try:
            with run_complete_path.open() as complete_file:
                data = json.load(complete_file)
                return data.get('complete')
        except (OSError, ValueError, json.JSONDecodeError) as err:
            self._add_warning(
                "Failed to read run complete file for at {}: {}"
                .format(run_complete_path.as_posix(), err))
            return None

    def _write_script(self, stype: str, path: Path, config: dict, module_wrappers: dict):
        """Write a build or run script or template. The formats for each are
            mostly identical.
        :param stype: The type of script (run or build).
        :param path: Path to the template file to write.
        :param config: Configuration dictionary for the script file.
        :param module_wrappers: The module wrappers definition.
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
                module = module.strip()
                if module:
                    script.module_change(module, self.var_man, module_wrappers)

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

            script.comment("Initialize spack db.")
            script.command("spack find")

            if install_packages:
                script.newline()
                script.comment('Install spack packages.')
                for package in install_packages:
                    script.command('spack add {} || exit 1'.format(package))

                script.command('spack install -v --fail-fast || exit 1'
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
            if utils.str_bool(self.config.get(stype, {}).get('autoexit')):
                script.command("set -e -o pipefail")
            for line in config.get('cmds', []):
                if line is None:
                    line = ''
                for split_line in line.split('\n'):
                    script.command(split_line)
        else:
            script.comment('No commands given for this script.')

        script.write(path)

    def __repr__(self):
        return "TestRun({s.name}-{s.full_id})".format(s=self)

    def _get_permute_vars(self):
        """Return the permute var values in a dictionary."""

        var_names = self.config.get('permute_on', [])
        if var_names:
            var_dict = self.var_man.as_dict()
            return {
                key: var_dict.get(key) for key in var_names
            }
        else:
            return {}

    def skip(self, reason: str):
        """Set the test as skipped with the given reason, and save the test
        attributes."""
        self.skipped = True
        self.skip_reasons.append(reason)
        self.save_attributes()

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
            if DeferredVariable.was_deferred(key):
                raise TestRunError(
                    "Skip conditions cannot contain deferred variables. Error "
                    "with skip condition that uses variable '{}'".format(key))

            for val in not_if[key]:
                if not val.endswith('$'):
                    val = val + '$'
                if bool(re.match(val, key)):
                    message = ("Skipping due to not_if match for key '{}' "
                               "with '{}'"
                               .format(key, val))
                    match_list.append(message)

        for key in only_if:
            match = False

            for val in only_if[key]:

                # We have to assume a match if one of the values is deferred.
                if DeferredVariable.was_deferred(key):
                    raise TestRunError(
                        "Skip conditions cannot contain deferred variables. Error "
                        "with skip condition that uses variable '{}'".format(key))

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

    def abort_skipped(self) -> bool:
        """Delete the test's directory. Pretending it never existed.

        ;returns: Whether cleanup was successful."""

        if not self.skipped:
            raise RuntimeError(
                "You should only abort tests that were skipped.")

        try:
            shutil.rmtree(self.path.as_posix())
        except OSError:
            return False

        return True
