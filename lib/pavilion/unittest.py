"""This module provides a base set of utilities for creating unittests
for Pavilion."""

import copy
import os
import pprint
import tempfile
import time
import inspect
from hashlib import sha1
from pathlib import Path
from collections import abc
from typing import List, Dict, Any, Union, Optional

import pavilion.schedulers
from pavilion import arguments
from pavilion import config
from pavilion import dir_db
from pavilion import log_setup
from pavilion import pavilion_variables
from pavilion import plugins
from pavilion import resolve
from pavilion.output import dbg_print
from pavilion.resolver import TestConfigResolver
from pavilion.sys_vars import base_classes
from pavilion.test_config.file_format import TestConfigLoader
from pavilion.test_run import TestRun
from pavilion.variables import VariableSetManager
from pavilion.micro import set_default
from unittest_ex import TestCaseEx


class PavTestCase(TestCaseEx):
    """A unittest.TestCase with a lot of useful Pavilion features baked in.
All pavilion unittests (in test/tests) should use this as their
base class.

:cvar Path PAV_LIB_DIR: The Path to Pavilion's lib directory (where this
    module resides).
:cvar Path PAV_ROOT_DIR: The Path to Pavilion's root directory (the root of the
    git repo).
:cvar Path TEST_DATA_DIR: The unit test data directory.
:cvar Path PAV_CONFIG_PATH: The path to the configuration used by unit tests.
:cvar dict QUICK_TEST_BASE_CFG: The base configuration for tests generated
    by the ``_quick_test()`` and ``_quick_test_cfg()`` methods.

:ivar yaml_config.ConfigDict pav_cfg: A pavilion config setup properly for
    use by unit tests. Unit tests should **always** use this pav_cfg. If it
    needs to be modified, copy it using copy.deepcopy.
"""

    TEST_URL = ('https://raw.githubusercontent.com/hpc/'
                'pavilion2/2.1.1/README.md')
    TEST_URL2 = ('https://raw.githubusercontent.com/hpc/'
                 'pavilion2/2.1.1/RELEASE.txt')
    TEST_URL_HASH = '0a3ad5bec7c8f6929115d33091e53819ecaca1ae'

    # Working dirs
    WORKING_DIRS = [
        'builds',
        'test_runs',
        'series',
        'users',
        ]

    PAV_ROOT_DIR = Path(__file__).resolve().parents[2]
    PAV_LIB_DIR = PAV_ROOT_DIR / "lib"
    PAV_TEST_DIR = PAV_ROOT_DIR / "test"
    TEST_OUTPUT_DIR = PAV_TEST_DIR / "output"
    TEST_DATA_DIR = PAV_TEST_DIR / "data"
    TEST_DATA_PAV_CONFIG_DIR = TEST_DATA_DIR / "pav_config_dir"
    DEFAULT_PAV_CONFIG_PATH = TEST_DATA_PAV_CONFIG_DIR / 'pavilion.yaml.in'

    DEFAULT_TIMEOUTS = {
        "testrun_wait": 20,
        "testrun_start": 10,
        "testrun_build": 5,
        "testrun_run": 10,
        "testrun_cancel": 1,
        "series_wait": 10,
        "series_start": 10,
        "log_cmd": 5,
        "build_docs": 30,
        "lockfile": 1,
        "result_logger": 10,
        "testset_wait": 10,
        "test_cmd": 3
    }

    DEFAULT_LOCK_LIFETIME = 3


    def __init__(self, *args, make_config_dir: bool = True, make_working_dir: bool = True,
                 make_pav_src: bool = True, write_config: bool = True, setup_spack: bool = True,
                 **kwargs):
        """Make the output directory for the current test suite, and do other initialization
        required by pavilion."""

        super().__init__(*args, **kwargs)

        self.setup_suite_output_dir(make_config_dir, make_working_dir, make_pav_src, write_config,
                                    setup_spack)
        self._get_timeouts()
        self._get_lock_lifetime()

    def _get_timeouts(self) -> None:
        """Get the various timeout values from the environment, if defined. Otherwise, use
        default values."""

        # Allow fine grained control over timeout values via environment variables
        try:
            universal_timeout = int(os.environ.get("PAV_UNITTEST_UNIVERSAL_TIMEOUT"))
        except (ValueError, TypeError):
            universal_timeout = None

        for timeout_type, default_val in self.DEFAULT_TIMEOUTS.items():
            attr_name = f"{timeout_type}_timeout"
            try:
                setattr(self,
                        attr_name,
                        int(os.environ.get(f"PAV_UNITTEST_{timeout_type.upper()}_TIMEOUT")))
            except (ValueError, TypeError):
                if universal_timeout is not None:
                    setattr(self, attr_name, universal_timeout)
                else:
                    setattr(self, attr_name, default_val)

    def _get_lock_lifetime(self) -> None:
        """Get the lock lifetime from the environment, if defined. Otherwise, use
        default values."""

        try:
            self.lock_lifetime = int(os.environ.get("PAV_UNITTEST_LOCK_LIFETIME"))
        except (ValueError, TypeError):
            self.lock_lifetime = self.DEFAULT_LOCK_LIFETIME

    def set_up(self):
        """By default, initialize plugins before every test."""

        _ = self

        os.environ["PAV_CONFIG_DIR"] = self.pav_config_dir.as_posix()
        plugins.initialize_plugins(self.pav_cfg)

    def tear_down(self):
        """Nothing to do by default."""

    def setup_suite_output_dir(self, make_config_dir: bool = True, make_working_dir: bool = True,
                               make_pav_src: bool = True, make_results_dir: bool = True,
                               write_config: bool = True, setup_spack: bool = True) -> None:
        """Make the main Pavilion config directory for the current test suite."""

        self.suite_name = Path(inspect.getfile(self.__class__)).stem
        self.suite_output_dir = self.TEST_OUTPUT_DIR / self.suite_name
        self.pav_config_dir = self.suite_output_dir / "pav_config_dir"
        self.working_dir = self.suite_output_dir / "working_dir"
        self.pav_src_dir = self.pav_config_dir / "pav_src"
        self.results_dir = self.suite_output_dir / "results"

        self.suite_output_dir.mkdir(parents=True, exist_ok=True)

        if make_config_dir:
            self.pav_config_dir.mkdir(parents=True, exist_ok=True)

            if make_pav_src:
                try:
                    self.pav_src_dir.symlink_to(self.PAV_ROOT_DIR)
                except FileExistsError:
                    pass

        if make_working_dir:
            self.working_dir.mkdir(parents=True, exist_ok=True)

        if make_results_dir:
            self.results_dir.mkdir(parents=True, exist_ok=True)

        self.pav_cfg = self.make_pav_config(
                                    write=(make_config_dir and write_config),
                                    setup_spack=setup_spack)

    def make_pav_config(self, setup_spack: bool = True, write: bool = True, **kwargs):
        """Create a pavilion config for the current test suite."""

        # Open the default pav config file (found in
        # test/data/pav_config_dir/pavilion.yaml.in), modify it, and then
        # save the modified file to the suite-specific pav config directory and read it instead.
        with self.DEFAULT_PAV_CONFIG_PATH.open() as cfg_file:
            raw_pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        raw_pav_cfg.working_dir = self.working_dir
        raw_pav_cfg.user_config = False

        if setup_spack:
            raw_pav_cfg.spack_path = (self.PAV_TEST_DIR / "spack").as_posix()

        raw_pav_cfg.working_dir = self.working_dir

        cfg_path = self.pav_config_dir / "pavilion.yaml"

        for key, value in kwargs.items():
            setattr(raw_pav_cfg, key, value)

        if write:
            with cfg_path.open('w') as pav_cfg_file:
                config.PavilionConfigLoader().dump(pav_cfg_file,
                                                raw_pav_cfg)

        config.PAV_CONFIG_DIR = self.pav_config_dir

        pav_cfg = config.find_pavilion_config(target=cfg_path)
        pav_cfg.pav_vars = pavilion_variables.PavVars()

        return pav_cfg

    def link_file(self, path: Union[Path, str], config_dir: Optional[Path] = None,
                  with_name: Optional[str] = None, link_path: Optional[Path] = None) -> None:
        """Link a file from the test data directory into the specified config directory, or into
        the unit test suite's main config directory, if no config directory is provided, using the
        file name specified by with_name. If no name is provided, the linked file retains its
        original name."""

        config_dir = set_default(config_dir, self.pav_config_dir)
        target = Path(path)

        if target.is_absolute() and link_path is None:
            try:
                rel_path = target.relative_to(self.TEST_DATA_PAV_CONFIG_DIR)
            except ValueError:
                raise ValueError(f"Absolute path {target} is not relative to "
                                  "{self.TEST_DATA_PAV_CONFIG_DIR}. Unable to link.")
        else:
            rel_path = target

        target_path = self.TEST_DATA_PAV_CONFIG_DIR / rel_path

        if link_path is None:
            link_path = config_dir / rel_path

            if with_name is not None:
                link_path = link_path.with_name(with_name)

        link_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            link_path.symlink_to(target_path)
        except FileExistsError:
            pass

    def link_files(self, *paths: Union[Path, str], config_dir: Optional[Path] = None) -> None:
        """Link files from the test data directory into the specified config directory, or into
        the unit test suite's main config directory, if no config directory is provided."""

        config_dir = set_default(config_dir, self.pav_config_dir)

        if isinstance(paths, str) or not isinstance(paths, abc.Iterable):
            paths = [paths]

        for path in paths:
            if Path(path).is_absolute():
                targets = Path("/").glob(str(path))
            else:
                targets = self.TEST_DATA_PAV_CONFIG_DIR.glob(str(path))

            for target in targets:
                self.link_file(target, config_dir)

    def _is_softlink_dir(self, path):
        """Verify that a directory contains nothing but softlinks whose files
exist. Directories in a softlink dir should be real directories
though."""

        for base_dir, cdirs, cfiles in os.walk(str(path)):
            base_dir = Path(base_dir)
            for cdir in cdirs:
                self.assert_((base_dir/cdir).is_dir(),
                             "Directory in softlink dir is a softlink (it "
                             "shouldn't be).")

            for file in cfiles:
                file_path = base_dir/file
                self.assertTrue(file_path.is_symlink(),
                                "File in softlink dir '{}' is not a softlink."
                                .format(file_path))

                target_path = file_path.resolve()
                self.assertTrue(target_path.exists(),
                                "Softlink target '{}' for link '{}' does not "
                                "exist."
                                .format(target_path, file_path))

    def _cmp_files(self, a_path, b_path):
        """Compare the contents of two files.

        :param Path a_path:
        :param Path b_path:
        """

        with a_path.open('rb') as a_file, b_path.open('rb') as b_file:
            self.assertEqual(a_file.read(), b_file.read(),
                             "File contents mismatch for {} and {}."
                             .format(a_path, b_path))

    def _cmp_tree(self, path_a, path_b):
        """Compare two directory trees, including the contents of all the
        files."""

        a_walk = list(os.walk(str(path_a)))
        b_walk = list(os.walk(str(path_b)))

        # Make sure these are in the same order.
        a_walk.sort()
        b_walk.sort()

        while a_walk and b_walk:
            a_dir, a_dirs, a_files = a_walk.pop(0)
            b_dir, b_dirs, b_files = b_walk.pop(0)
            a_dir = Path(a_dir)
            b_dir = Path(b_dir)

            self.assertEqual(
                sorted(a_dirs), sorted(b_dirs),
                "Extracted archive subdir mismatch for '{}' {} != {}"
                .format(path_a, a_dirs, b_dirs))

            # Make sure these are in the same order.
            a_files.sort()
            b_files.sort()

            self.assertEqual(a_files, b_files,
                             "Extracted archive file list mismatch. "
                             "{} != {}".format(a_files, b_files))

            for file in a_files:
                # The file names have are been verified as the same.
                a_path = a_dir/file
                b_path = b_dir/file

                # We know the file exists in a, does it in b?
                self.assertTrue(b_path.exists(),
                                "File missing from archive b '{}'".format(b_path))

                self._cmp_files(a_path, b_path)

        self.assertTrue(not a_walk and not b_walk,
                        "Left over directory contents in a or b: {}, {}"
                        .format(a_walk, b_walk))

    @staticmethod
    def get_hash(filename):
        """ Get a sha1 hash of the file at the given path.

        :param Path filename:
        :return: The sha1 hexdigest of the file contents.
        :rtype: str
        """
        with filename.open('rb') as file:
            sha = sha1()
            sha.update(file.read())
            return sha.hexdigest()

    dbg_print = staticmethod(dbg_print)

    QUICK_TEST_BASE_CFG = {
        'cfg_label': 'test',
        'scheduler': 'raw',
        'suite': 'unittest',
        'build': {
            'verbose': 'false',
            'timeout': '30',
        },
        'run': {
            'cmds': [
                'echo "Hello World."'
            ],
            'verbose': 'false',
            'timeout': '300',
        },
        'result_parse': {},
        'result_evaluate': {},
        'schedule': {},
    }

    def _quick_test_cfg(self) -> Dict[str, Any]:
        """Return a pre-populated test config to use with
``self._quick_test``. This can be used as is, or modified for
desired effect.

The default config is: ::

{}
"""

        cfg = copy.deepcopy(self.QUICK_TEST_BASE_CFG)

        loc_sched = (self.TEST_DATA_DIR/'pav_config_dir'/'modes' /
                     'local_sched.yaml')

        if loc_sched.exists():
            with loc_sched.open() as loc_slurm_file:
                sched_cfg = TestConfigLoader().load(loc_slurm_file,
                                                    partial=True)

            cfg['schedule'].update(sched_cfg['schedule'])

        return cfg

    def _load_test(self, name: str, platform: str = 'this', host: str = 'this',
                   modes: List[str] = None,
                   build=True, finalize=True) -> List[TestRun]:
        """Load the named test config from file. Returns a list of the
        resulting configs."""

        if modes is None:
            modes = []

        res = TestConfigResolver(self.pav_cfg, platform=platform, host=host)
        test_cfgs = res.load([name], modes=modes)

        tests = []
        for ptest in test_cfgs:
            test = TestRun(self.pav_cfg, ptest.config, var_man=ptest.var_man)
            test.save()

            if build:
                test.build()

            if finalize:
                fin_sys = base_classes.SysVarDict(unique=True)
                fin_var_man = VariableSetManager()
                fin_var_man.add_var_set('sys', fin_sys)
                scheduler = pavilion.schedulers.get_plugin(test.scheduler)
                fin_sched_vars = scheduler.get_final_vars(test)
                fin_var_man.add_var_set('sched', fin_sched_vars)
                test.finalize(fin_var_man)

            tests.append(test)

        return tests

    __config_lines = pprint.pformat(QUICK_TEST_BASE_CFG).split('\n')
    # Code analysis indicating format isn't found for 'bytes' is a Pycharm bug.
    _quick_test_cfg.__doc__ = _quick_test_cfg.__doc__.format(
        '\n'.join(['    ' + line for line in __config_lines]))
    del __config_lines

    def _quick_test(self, cfg=None, name="quick_test",
                    build=True, finalize=True, test_id=None):
        """Create a test run object to work with.
        The default is a simple hello world test with the raw scheduler.

        :param dict cfg: An optional config dict to create the test from.
        :param str name: The name of the test.
        :param bool build: Build this test, while we're at it.
        :param bool finalize: Finalize this test.
        :rtype: TestRun
        """

        if cfg is None:
            cfg = self._quick_test_cfg()

        cfg = copy.deepcopy(cfg)

        loader = TestConfigLoader()
        cfg = loader.validate(loader.normalize(cfg))

        cfg['name'] = name

        var_man = VariableSetManager()
        var_man.add_var_set('var', cfg['variables'])
        var_man.add_var_set('sys', base_classes.SysVarDict(unique=True, defer=True))
        var_man.add_var_set('pav', self.pav_cfg.pav_vars)

        sched = pavilion.schedulers.get_plugin(cfg.get('scheduler', 'raw'))
        sched_vars = sched.get_initial_vars(cfg.get('schedule', {}))
        var_man.add_var_set('sched', sched_vars)

        var_man.resolve_references()

        cfg = resolve.test_config(cfg, var_man)

        test = TestRun(pav_cfg=self.pav_cfg, config=cfg, var_man=var_man, test_id=test_id)

        if test.skipped:
            # You can't proceed further with a skipped test.
            return test

        test.save()

        if build:
            test.build()
        if finalize:
            fin_sys = base_classes.SysVarDict(unique=True)
            fin_var_man = VariableSetManager()
            fin_var_man.add_var_set('sys', fin_sys)
            fin_sched_vars = sched.get_final_vars(test)
            fin_var_man.add_var_set('sched', fin_sched_vars)
            test.finalize(fin_var_man)

        return test

    def wait_tests(self, working_dir: Path, timeout=5):
        """Wait on all the tests under the given path to complete.

        :param working_dir: The path to a working directory.
        :param timeout: How long to wait before giving up.
        """

        def is_complete(path: Path):
            """Return True if test is complete."""

            return (path/TestRun.COMPLETE_FN).exists()

        runs_dir = working_dir / 'test_runs'
        end_time = time.time() + timeout
        while time.time() < end_time:

            completed = [is_complete(test)
                         for test in dir_db.select(self.pav_cfg, runs_dir).paths]

            if not completed:
                self.fail("No tests started.")

            if all(completed):
                break
            else:
                time.sleep(0.1)
                continue
        else:
            raise TimeoutError(
                "Timed out out after {} seconds. Waiting on tests: {}"
                .format(timeout, [test.name for test in dir_db.select(self.pav_cfg,
                                                            runs_dir).paths
                        if is_complete(test)]))
