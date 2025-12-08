"""
Pavilion has to take a bunch of raw Suite/Test configurations, incorporate
various Pavilion variables, resolve test inheritance and permutations,
and finally produce a bunch of TestRun objects. These steps, and more,
are all handled by the TestConfigResolver
"""

# pylint: disable=too-many-lines

import copy
import io
import logging
import math
import multiprocessing as mp
import os
import pprint
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, IO, Dict, Tuple, NewType, Union, Any, Iterator, TextIO, Optional, Iterable

import similarity
import yc_yaml
import yaml_config as yc
from pavilion.config import PavConfig
from pavilion.enums import Verbose
from pavilion import output, variables
from pavilion import pavilion_variables
from pavilion import resolve
from pavilion import schedulers
from pavilion import sys_vars
from pavilion.errors import SystemPluginError
from pavilion.errors import VariableError, TestConfigError, PavilionError, SchedulerPluginError
from pavilion.pavilion_variables import PavVars
from pavilion.test_config import file_format
from pavilion.test_config.file_format import (TEST_NAME_RE,
                                             KEY_NAME_RE)
from pavilion.test_config.file_format import TestConfigLoader, TestSuiteLoader
from pavilion.utils import union_dictionary, recursive_update
from pavilion.micro import first, listmap, listfilter
from pavilion.path_utils import append_to_path, exists
from yaml_config import RequiredError, YamlConfigLoader

from .proto_test import RawProtoTest, ProtoTest
from .request import TestRequest

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)

TEST_VERS_RE = re.compile(r'^\d+(\.\d+){0,2}$')

TestConfig = Dict[str, Any]


class ConfigInfo:
    def __init__(self, name: str, type: str, path: Path, label: Optional[str] = None,
        from_suite: bool = False):

        self.name = name
        self.type = type
        self.label = label
        self.path = path
        self.from_suite = from_suite


class TestOptions:
    """Test options from the command line or series configs."""

    def __init__(self,
                 platform: str,
                 host: str,
                 modes: Optional[List[str]] = None,
                 overrides: Optional[TestConfig] = None,
                 conditions: Optional[Dict] = None):
        self.platform = platform
        self.host = host
        self.modes = modes or []
        self.overrides = overrides or {}
        self.conditions = conditions or {}


class TestConfigResolver:
    """Converts raw test configurations into their final, fully resolved
    form."""

    CONFIG_TYPES = ("platform", "host", "mode")

    def __init__(self,
                 pav_cfg: PavConfig,
                 platform: Optional[str] = None,
                 host: Optional[str] = None,
                 outfile: Optional[TextIO] = None,
                 verbosity: int = Verbose.QUIET):
        """Initialize the resolver.

        :param platform: The platform to configure tests for.
        :param host: The host to configure tests for.
        :param outfile: The file to print output to.
        :param verbosity: Determines the format of the output. (See enums.Verbose)
        """

        self.pav_cfg = pav_cfg

        self._outfile = io.StringIO() if outfile is None else outfile
        self._verbosity = verbosity
        self._loader = TestConfigLoader()
        self._suite_loader = TestSuiteLoader()
        self.errors = []

        self._base_var_man = variables.VariableSetManager()
        try:
            self._base_var_man.add_var_set(
                'sys', sys_vars.get_vars(defer=True)
            )
        except SystemPluginError as err:
            raise TestConfigError(
                "Error in system variables"
                .format(prior_error=err)
            )

        self._base_var_man.add_var_set(
            'pav', pavilion_variables.PavVars()
        )

        self._host = self._base_var_man['sys.sys_name'] if host is None else host
        if platform is None:
            self._platform = self._base_var_man['sys.platform']
        else:
            self._platform = platform

        # This may throw an exception. It's expected to be caught by the caller.
        self._base_config = self._load_base_config(self._platform, self._host)

        # Raw loaded test suites
        self._suites: Dict[Dict] = {}

    @staticmethod
    def _get_config_dirname(cfg_type: str, use_suites_dir: bool = False) -> str:
        """Returns the canonical config directory name for a given config type."""

        dirname = cfg_type.lower()

        if cfg_type == "suite" and not use_suites_dir:
            return "tests"

        if dirname[-1] != 's':
            dirname += 's'

        return dirname

    @staticmethod
    def _get_config_fname(cfg_type: str) -> str:
        """Given a config type, returns the name of the file in the suite directory corresponding to
        that type."""

        fname = cfg_type.lower()

        if fname in ("host", "mode", "platform"):
            fname += 's'

        return f"{fname}.yaml"

    @property
    def config_paths(self) -> Iterator[Path]:
        """Return an iterator over all config paths."""
        return self.pav_cfg.config_paths

    @property
    def suites_dirs(self) -> Iterator[Path]:
        """Return an iterator over all suites directories."""
        return self.pav_cfg.suites_dirs

    @property
    def config_labels(self) -> Iterator[str]:
        """Return an iterator over all config labels."""
        return self.pav_cfg.configs.keys()

    def _get_test_config_path(self,
                              cfg_name: str,
                              cfg_type: str) -> Tuple[Optional[str], Optional[Path]]:
        """Given a config name and type, find the path to that config, if it exists,
        excluding configs in the suites directory. If no such config exists,
        return None."""

        cfg_dir = self._get_config_dirname(cfg_type)
        paths = map(append_to_path(f"{cfg_dir}/{cfg_name}.yaml"), self.config_paths)

        pairs = zip(self.config_labels, paths)
        pairs = listfilter(lambda p: p[1].exists(), pairs)

        if len(pairs) > 1:
            raise TestConfigError(f"Could not unambiguously find config with name {cfg_name}: "
                                  f"Found {len(pairs)} in the following locations: "
                                  f"{listmap(lambda p: p[1], pairs)}.")
        elif len(pairs) == 0:
            return None, None
        else:
            return pairs[0]

    def _get_suite_path(self, suite_name: str) -> Tuple[Optional[str], Optional[Path]]:
        """Get the path to the suite with the given name, if it exists, along with its corresponding
        config label. Returns None if no suite is found."""

        suite_paths = listmap(append_to_path(f"{suite_name}.yaml"), self.suites_dirs)
        suite_paths.extend(map(append_to_path(f"{suite_name}"), self.suites_dirs))

        pairs = zip(list(self.config_labels) * 2, suite_paths)
        pairs = listfilter(lambda p: p[1].exists(), pairs)

        if len(pairs) > 1:
            raise TestConfigError(f"Could not unambiguously find suite with name {suite_name}: "
                                  f"Found {len(pairs)} in the following locations: "
                                  f"{listmap(lambda p: p[1], pairs)}.")
        elif len(pairs) == 0:
            return None, None
        else:
            return pairs[0]

    def _config_path_from_suite(self, suite_name: Optional[str],
                                cfg_type: str) -> Tuple[Optional[str], Optional[Path]]:
        """Given a suite name, return the path to the config file of the specified type, if one
        exists, along with its corresponding config label. If the file does not exist in any known
        suites directory, returns None."""

        if suite_name is None:
            return None, None

        label, suite_path = self._get_suite_path(suite_name)

        if suite_path is None:
            return None, None

        cfg_fname = self._get_config_fname(cfg_type)

        if suite_path.is_dir():
            cfg_path = suite_path / cfg_fname
        elif cfg_type == "suite":
            cfg_path = suite_path
        else:
            return None, None

        if cfg_path.exists():
            return label, cfg_path

        return None, None

    def find_config(self, cfg_type: str, cfg_name: str, suite_name: str = None) -> ConfigInfo:
        """Search all of the known configuration directories for a config of the
        given type and name, and report whether it was found in the suites directory.

        :param str conf_type: 'host', 'platform', 'mode', or 'test/suite'
        :param str conf_name: The name of the config (without a file extension).
        :return: A tuple of the path to that config, if it exists, and a boolean
            indicating whether it was found in the suites directory (True) or not (False).
        """

        cfg_path = None

        if suite_name is not None:
            label, cfg_path = self._config_path_from_suite(suite_name, cfg_type)

        if cfg_path is not None:
            from_suite = True
        else:
            label, cfg_path = self._get_test_config_path(cfg_name, cfg_type)
            from_suite = False

        return ConfigInfo(cfg_name, cfg_type, cfg_path, label, from_suite)

    def find_similar_configs(self, conf_type: str, conf_name: str) -> List[str]:
        """Find configs with a name similar to the one specified."""

        # TODO: modify this for new suites directory
        # It will need to search inside suites config files to find names of modes, hosts, etc.

        conf_dir = self._get_config_dirname(conf_type)

        for label, config in self.pav_cfg.configs.items():
            type_path = config['path'] / conf_type

            names = []

            if type_path is not None and type_path.exists():
                for file in type_path.iterdir():
                    if file.name.endswith('.yaml') and not file.is_dir():
                        names.append(file.name[:-5])

        return similarity.find_matches(conf_name, names)

    def find_all_tests(self):
        """Find all the tests within known config directories.

    :return: Returns a dictionary of suite names to an info dict.
    :rtype: dict(dict)

    The returned data structure looks like: ::

        suite_name -> {
            'path': Path to the suite file.
            'label': Config dir label.
            'err': Error loading suite file.
            'supersedes': [superseded_suite_files]
            'tests': name -> {
                    'conf': The full test config (inheritance resolved),
                    'summary': Test summary string,
                    'doc': Test doc string,
            }
    """

        suites = {}

        for label, name, path in self.pav_cfg.suite_info:
            if name not in suites:
                suites[name] = {
                    'path': path,
                    'label': label,
                    'err': '',
                    'tests': {},
                    'supersedes': [],
                }
            else:
                suites[name]['supersedes'].append(path)

            try:
                # It's ok if the tests aren't completely validated. They
                # may have been written to require a real host/mode file.
                with path.open('r') as suite_file:
                    try:
                        suite_cfg = self._suite_loader.load(suite_file, partial=True)
                    except (TypeError,
                            KeyError,
                            ValueError,
                            yc_yaml.YAMLError) as err:
                        suites[name]['err'] = err
                        continue
            except FileNotFoundError as err:
                # This can happen in the case of a broken symlink
                suites[name]["err"] = err

            base = self._loader.load_empty()

            try:
                suite_cfgs = self.resolve_inheritance(
                    suite_cfg=suite_cfg,
                    suite_path=path)
            except Exception as err:  # pylint: disable=W0703
                suites[name]['err'] = err
                continue

            def default(val, dval):
                """Return the dval if val is None."""

                return dval if val is None else val

            for test_name, conf in suite_cfgs.items():
                suites[name]['tests'][test_name] = {
                    'conf': conf,
                    'maintainer': default(
                        conf['maintainer']['name'], ''),
                    'email': default(conf['maintainer']['email'], ''),
                    'summary': default(conf.get('summary', ''), ''),
                    'doc': default(conf.get('doc', ''), ''),
                }
        return suites

    def find_all_configs(self, conf_type: str):
        """ Find all configs (host/modes) within known config directories.

    :return: Returns a dictionary of suite names to an info dict.
    :rtype: dict(dict)

    The returned data structure looks like: ::

        config_name -> {
            'path': Path to the suite file.
            'config': Full config file, loaded as a dict.
            'status': Nothing if successful, 'Loading the config failes.'
                      if TectConfigError.
            'error': Detailed error if applicable.
            }

        """

        conf_dir = self._get_config_dirname(conf_type)

        configs = {}
        for config in self.pav_cfg.configs.values():
            path = config['path'] / conf_dir

            if not (path.exists() and path.is_dir()):
                continue

            for file in os.listdir(path.as_posix()):

                file = path / file
                if file.suffix == '.yaml' and file.is_file():
                    name = file.stem
                    configs[name] = {}

                    full_path = file
                    try:
                        with file.open() as config_file:
                            config = self._loader.load(config_file)
                        configs[name]['path'] = full_path
                        configs[name]['config'] = config
                        configs[name]['status'] = ''
                        configs[name]['error'] = ''
                    except (TestConfigError, TypeError) as err:
                        configs[name]['path'] = full_path
                        configs[name]['config'] = ''
                        configs[name]['status'] = ('Loading the config failed.'
                                                   ' For more info run \'pav '
                                                   'show {} --err\'.'
                                                   .format(conf_type))
                        configs[name]['error'] = err

        return configs

    PROGRESS_PERIOD = 0.5

    def load_iter(self,
                  tests: List[str],
                  modes: Optional[List[str]] = None,
                  overrides: Optional[TestConfig] = None,
                  conditions: Optional[Dict] = None,
                  batch_size: Optional[int] = None) -> Iterator[List[ProtoTest]]:
        """Load and fully resolve the requested tests. This returns an iterator
        of ProtoTest objects, which can be used to create the final test objects.
        Test resolution is delayed as long as possible, to keep in sync with system
        scheduler state changes.

        Errors encountered are not fatal, but are stored in the internal `.errors`
        attribute.

        :param tests: A list of test names to load.
        :param modes: A list of modes to load.
        :param overrides: A dict of key:value pairs to apply as overrides.
        :param conditions: A dict containing the only_if and not_if conditions.
        :param batch_size: The maximum number of tests to return at once. Tests
            may end up queued internally while holding scheduler information that's
            no longer valid if the number of permutations exceeds the batch size.
        """

        # Clear all existing errors
        self.errors = []

        batch_size = 2**32 if batch_size is None else batch_size

        options = TestOptions(platform=self._platform,
                              host=self._host,
                              modes=modes,
                              overrides=overrides,
                              conditions=conditions)

        requests = [TestRequest(req) for req in tests]

        raw_tests = []

        for request in requests:
            # Convert each request into a list of RawProtoTest objects.
            try:
                raw_tests.extend(self._load_raw_configs(request, options))
            except TestConfigError as err:
                err.request = request
                self.errors.append(err)

        raw_tests.reverse()
        raw_tests_empty = not raw_tests

        # Tests that are resolved and ready to return.
        resolved_tests = []
        # Test that are ready to resolve. Note that these may be multiplied out.
        ready_to_resolve = []
        while raw_tests:
            # Number of tests this will resolve too after repeats
            ready_count = 0

            # Get permutations from raw tests until we've hit our batch limit.
            while len(resolved_tests) + ready_count < batch_size and raw_tests:

                raw_test = raw_tests.pop()

                # Resolve all configuration permutations.
                try:
                    permutations = raw_test.resolve_permutations()
                except TestConfigError as err:
                    self.errors.append(err)
                    break

                if not permutations:
                    continue

                batch_remain = batch_size - len(resolved_tests) - ready_count - len(permutations)
                ready_count += len(permutations)
                raw_test.count -= 1
                while raw_test.count and batch_remain > 0:
                    raw_test.count -= 1
                    batch_remain -= len(permutations)
                    ready_count += len(permutations)
                    for ptest in permutations:
                        ptest.count += 1

                if raw_test.count:
                    raw_tests.append(raw_test)

                ready_to_resolve.extend(permutations)

            # Now resolve all the string syntax and variables those tests at once.
            new_resolved_tests = []
            for ptest in self._resolve_escapes(ready_to_resolve):
                # Perform last minute health checks
                try:
                    ptest.check_result_format()
                    new_resolved_tests.append(ptest)
                except TestConfigError as err:
                    self.errors.append(err)

            resolved_tests.extend(new_resolved_tests)
            ready_to_resolve = []

            # Finally, return batches of the resolved tests.
            while len(resolved_tests) >= batch_size:
                yield resolved_tests[:batch_size]
                resolved_tests = resolved_tests[batch_size:]

        yield resolved_tests

        # Checking for requests that did not match any permutations
        for request in requests:
            if not request.request_matched and not request.has_error and not raw_tests_empty:
                # Grab all the tests generated by the current request
                if request.seen_subtitles:
                    self.errors.append(TestConfigError(
                        "Test request '{}' tried to match permutation '{}', "
                        "but no matches were found.\n"
                        "Available permutations: \n{}"
                        .format(request.request, request.permutation,
                                '\n'.join([' - {}'.format(sub)
                                           for sub in request.seen_subtitles]))))
                else:
                    self.errors.append(TestConfigError(
                        "Test request '{}' tried to match permutation '{}', "
                        "but that test doesn't have permutations at all.\n"
                        "Is `permute_on` set for that test?"
                        .format(request.request, request.permutation)))

    def load(self,
             tests: List[str],
             modes: Optional[List[str]] = None,
             overrides: Optional[TestConfig] = None,
             conditions: Optional[Dict] = None,
             throw_errors: bool = True) -> List[ProtoTest]:
        """As per ``load_iter`` except just return a list of all generated tests
        without any batching. This method is entirely meant for testing -
        the primary code should always use the iterator.

        :param throw_errors: Throw the first error in `self.errors`.
        """

        all_tests = []
        for batch in self.load_iter(
                tests=tests,
                modes=modes,
                conditions=conditions,
                overrides=overrides,
                batch_size=None):
            all_tests.extend(batch)

        if self.errors and throw_errors:
            raise self.errors[0]

        return all_tests

    def _resolve_escapes(self, ptests: ProtoTest) -> List[ProtoTest]:
        """Resolve string escapes and variable references in parallel for the given tests."""

        complete = 0
        test_count = len(ptests)

        if not ptests:
            return []
        elif len(ptests) == 1:
            try:
                ptests[0].resolve()
            except TestConfigError as err:
                self.errors.append(err)
        else:
            async_results = []
            proc_count = min(self.pav_cfg['max_cpu'], len(ptests))
            with mp.Pool(processes=proc_count) as pool:
                for ptest in ptests:
                    aresult = pool.apply_async(ptest.resolve)
                    async_results.append((aresult, ptest))

                while async_results:
                    not_ready = []
                    for aresult, ptest in list(async_results):
                        if aresult.ready():
                            try:
                                # Update the local copy of the proto_test config with the one
                                # process in the external process.
                                ptest.update_config(aresult.get())
                            except TestConfigError as err:
                                self.errors.append(err)
                                ptests.remove(ptest)
                            except Exception as err:  # pylint: disable=broad-except
                                self.errors.append(TestConfigError("Unexpected error loading tests",
                                                                   ptest.request, err))
                                ptests.remove(ptest)

                            if self._verbosity == Verbose.DYNAMIC:
                                complete += 1
                                progress = test_count - complete
                                progress = 1 - progress/test_count
                                output.fprint(self._outfile,
                                              "Resolving Test Configs: {:.0%}".format(progress),
                                              end='\r')
                        else:
                            not_ready.append((aresult, ptest))
                    async_results = not_ready

                    if async_results:
                        try:
                            async_results[0][0].wait(0.5)
                        except TimeoutError:
                            pass

        if self._verbosity == Verbose.DYNAMIC:
            output.fprint(self._outfile, '')
        elif self._verbosity != Verbose.QUIET:
            output.fprint(self._outfile, 'Resolved {} test configs.'.format(len(ptests)))

        # Filter out tests whose subtitle wasn't requested.
        resolved_tests = [ptest for ptest in ptests
                          if ptest.request.matches_test_permutation(ptest.config.get('subtitle'))]

        multiplied_tests = []
        # Multiply out tests according to the requested count.
        while resolved_tests:
            remaining = []
            for ptest in list(resolved_tests):
                if ptest.count == 1:
                    multiplied_tests.append(ptest)
                else:
                    multiplied_tests.append(ptest.copy())
                    ptest.count -= 1
                    remaining.append(ptest)
            resolved_tests = remaining

        return multiplied_tests

    @classmethod
    def config_from_overrides(cls, overrides: List[str]) -> TestConfig:
        """Parse a list of override strings and convert them into a test config."""

        cfg = {}

        for ovr in overrides:
            ovr_dict = cls.override_to_dict(ovr)

            try:
                recursive_update(cfg, ovr_dict)
            except ValueError as err:
                raise TestConfigError("Error parsing override {ovr}.")

        return TestConfigLoader().normalize(cfg)

    @staticmethod
    def override_to_dict(override: str) -> Dict[str, str]:
        """Convert a single overrides string (e.g. 'schedule.nodes=1') into a dictionary."""

        if '=' not in override:
            raise ValueError(
                f"Invalid override value {override}. Must be in the form: "
                "<key>=<value>. Ex. -c run.modules=['gcc'] ")

        key, value = override.split('=', 1)
        key = key.strip()

        if not key:
            raise ValueError("Override '{}' given a blank key.".format(override))

        key = key.split('.')

        for part in key:
            if ' ' in part:
                raise ValueError("Override '{}' has whitespace in its key.".format(override))
            if not part:
                raise ValueError("Override '{}' has an empty key part.".format(override))

        ovr_dict = {}
        sub_cfg = ovr_dict

        for part in key[:-1]:
            sub_cfg[part] = {}
            sub_cfg = sub_cfg.get(part)

        sub_cfg[key[-1]] = value

        return ovr_dict

    @staticmethod
    def _safe_load_config(cfg: ConfigInfo, loader: yc.YamlConfigLoader) -> TestConfig:
        """Given a path to a config, load the config, and raise an appropriate
        error if it can't be loaded"""

        path = cfg.path
        cfg_type = cfg.type

        try:
            with path.open() as cfg_file:
                raw_cfg = loader.load_raw(cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open {} config '{}'"
                                  .format(cfg_type, path), prior_error=err)
        except ValueError as err:
            raise TestConfigError(
                "{} config '{}' has invalid value."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except KeyError as err:
            raise TestConfigError(
                "{} config '{}' has an invalid key."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "{} config '{}' has a YAML Error"
                .format(cfg_type.capitalize(), path), prior_error=err)
        except TypeError as err:
            raise TestConfigError(
                "Structural issue with {} config '{}'"
                .format(cfg_type, path), prior_error=err)

        return raw_cfg

    def _load_raw_config(self,
                         cfg_info: ConfigInfo,
                         loader: yc.YamlConfigLoader) -> TestConfig:
        """Given a path to a config file and a loader, attempt to load the config, handle errors
        appropriately."""

        raw_cfg = self._safe_load_config(cfg_info, loader)

        if cfg_info.from_suite and cfg_info.type != "suite":
            raw_cfg = raw_cfg.get(cfg_info.name)

        if raw_cfg is None:
            raise TestConfigError(
                f"Could not find {cfg_info.type} config with name {cfg_info.name}"
                f" in file {cfg_info.path}.")

        return raw_cfg

    def _load_raw_configs(self, request: TestRequest, options: TestOptions) -> List[RawProtoTest]:
        """Get a list of raw test configs given a host, list of modes,
        and a list of tests. Each of these configs will be lightly modified with
        a few extra variables about their name, suite, and suite_file, as well
        as guaranteeing that they have 'variables' and 'permutations' sections.

        :param request: A test request to load tests for.
        :param options: A set of test options, including modes and overrides.
        :return: A list of RawProtoTests.
        """

        added_tests = []
        matched_suites = self._load_suite_tests(request)
        if not matched_suites:
            self.errors.append(TestConfigError(
                "Could not find a test suite that matches '{}'.\n"
                "See 'pav show suites' for a list of available test suites."
                .format(request.suite),
                request=request))

        for suite_name, suite_tests in matched_suites.items():
            for test_name in suite_tests:
                if request.matches_test_name(test_name):
                    added_tests.append(suite_tests[test_name])

        if not added_tests:
            if len(matched_suites) == 1:
                self.errors.append(TestConfigError(
                    "Could not find any test that matches '{}.{}'.\n"
                    "Tests for suite '{}' are:\n - {}\n"
                    .format(
                        request.suite,
                        request.test,
                        request.suite,
                        "\n - ".join(suite_tests.keys())),
                    request=request))
            else:
                self.errors.append(TestConfigError(
                    "Could not find any test that matches '{}.{}'.\n"
                    "See 'pav show tests' for a list of tests across all suites."
                    .format(request.suite, request.test),
                    request=request))
            return []

        test_configs = []
        for raw_test in added_tests:
            raw_test = self._apply_test_options(raw_test, options, request)
            if raw_test is None:
                continue

            # Now that we've applied all general transforms to the config, make it into a ProtoTest.
            try:
                rproto_test = RawProtoTest(request, raw_test, self._base_var_man)
            except TestConfigError as err:
                err.request = request
                self.errors.append(err)
                continue

            # Make sure all the variables in the test config are consistent in structure.
            try:
                rproto_test.check_variable_consistency()
            except TestConfigError as err:
                err.request = request
                self.errors.append(err)
                continue

            test_configs.append(rproto_test)

        return test_configs

    def apply_aux_configs(self, test_cfg: TestConfig, options: TestOptions) -> TestConfig:
        """Apply the sequence of auxiliary configs to the test config."""

        suite_name = test_cfg.get("suite")

        aux_cfgs = self._load_aux_configs(options, suite_name)

        for cfg_info, cfg in aux_cfgs:
            try:
                test_cfg = self._loader.merge(test_cfg, cfg)
            except (KeyError, ValueError) as err:
                if cfg_info.type == "overrides":
                    msg = "Error merging overrides configuration."
                else:
                    msg = (f"Error merging {cfg_info.type} configuration for {cfg_info.type} "
                           "'{cfg_info.name}'")
                raise TestConfigError(msg)

            if cfg_info.type == "mode":
                test_cfg = resolve.cmd_inheritance(test_cfg)

        return test_cfg

    def _load_aux_configs(self,
                          options: TestOptions,
                          suite_name: Optional[str] = None) -> Tuple[str, TestConfig]:
        """Load platform, host, and mode configs, and construct the override configs,
        returning them in the order in which they will be applied."""

        configs = []

        aux_paths = self._get_aux_config_paths(options, suite_name)

        for cfg_info in aux_paths:
            if cfg_info.from_suite:
                loader = self._suite_loader
            else:
                loader = self._loader

            raw_cfg = self._load_raw_config(cfg_info, loader)

            try:
                cfg = self._loader.normalize(
                                    raw_cfg,
                                    root_name=f"the top level of the {cfg_info.type} file.")
            except (KeyError, ValueError) as err:
                raise TestConfigError(
                    f"Error loading {cfg_info.type} config '{cfg_info.name}' from file "
                    f"'{cfg_info.path}'.")

            configs.append((cfg_info, cfg))

        if options.overrides is not None:
            overrides = self._loader.normalize(options.overrides)

            cfg_info = ConfigInfo(
                                name=None,
                                type="overrides",
                                label=None,
                                path=None,
                                from_suite=False)

            configs.append((cfg_info, overrides))

            return configs

    def _get_aux_config_paths(self,
                              options: TestOptions,
                              suite_name: Optional[str] = None) -> List[ConfigInfo]:
        """Get a list of auxiliary config paths in the order in which they will be applied."""

        cfg_names = {"platform": options.platform, "host": options.host}

        paths = []

        for cfg_type in ("platform", "host"):
            # If a config exists in both the suite directory and the config-type specific
            # directory, we'll just stack them, with the config from the suite directory taking
            # higher precedence.
            label, path = self._get_test_config_path(cfg_names.get(cfg_type), cfg_type)

            if path is not None:
                paths.append(ConfigInfo(
                                    name=cfg_names.get(cfg_type),
                                    type=cfg_type,
                                    label=label,
                                    path=path,
                                    from_suite=False))

            label, path = self._config_path_from_suite(suite_name, cfg_type)

            if path is not None:
                paths.append(ConfigInfo(
                                    name=cfg_names.get(cfg_type),
                                    type=cfg_type,
                                    label=label,
                                    path=path,
                                    from_suite=True))

        for mode in options.modes:
            global_mode_label, global_mode_path = self._get_test_config_path(mode, "mode")
            suite_mode_label, suite_mode_path = self._config_path_from_suite(mode, "mode")

            if suite_mode_path is not None:
                if global_mode_path is not None:
                    raise TestConfigError(f"Found multiple mode files with name {mode} in the "
                                          "following locations: "
                                          f"{[global_mode_path, suite_mode_path]}")
                else:
                    path = suite_mode_path
                    label = suite_mode_label
                    from_suite = True
            else:
                if global_mode_path is None:
                    similar = self.find_similar_configs("mode", mode)

                    if len(similar) > 0:
                        raise TestConfigError(
                            "Could not find mode config {}.yaml.\n"
                            "Did you mean one of these? {}"
                            .format(mode, ', '.join(similar)))
                    else:
                        raise TestConfigError(
                            "Could not find mode config file '{}.yaml' in any of the "
                            "Pavilion config directories.\n"
                            "Run `pav show mode` to get a list of available mode files."
                            .format(mode))
                else:
                    path = global_mode_path
                    label = global_mode_label
                    from_suite = False

            paths.append(ConfigInfo(
                    name=mode,
                    type="mode",
                    label=label,
                    path=path,
                    from_suite=from_suite))

        return paths

    def _apply_test_options(self,
                            raw_test: TestConfig,
                            options: TestOptions,
                            request: TestRequest) -> Optional[Dict]:

        test_cfg = copy.deepcopy(raw_test)

        test_cfg['modes'] = options.modes
        suite_name = test_cfg['suite']

        # Apply any additional conditions.
        if options.conditions:
            test_cfg['only_if'] = union_dictionary(
                test_cfg['only_if'], options.conditions['only_if']
            )
            test_cfg['not_if'] = union_dictionary(
                test_cfg['not_if'], options.conditions['not_if']
            )

        # Apply downstream configs.
        try:
            test_cfg = self.apply_aux_configs(test_cfg, options)
        except TestConfigError as err:
            err.request = request
            self.errors.append(err)
            return None

        # Save the overrides as part of the test config
        test_cfg['overrides'] = options.overrides

        # Result evaluations can be added to all tests at the root pavilion config level.
        result_evals = test_cfg['result_evaluate']
        for key, const in self.pav_cfg.default_results.items():
            if key in result_evals:
                # Don't override any that are already there.
                continue

            test_cfg['result_evaluate'][key] = '"{}"'.format(const)

        return self._validate(test_cfg)

    def _validate(self, test_cfg: Dict) -> Dict:
        """Return the finalized, validated copy of the test config."""

        suite_path = test_cfg['suite_path']
        test_name = test_cfg['name']

        try:
            test_cfg = self._loader.validate(test_cfg)
        except RequiredError as err:
            raise TestConfigError(
                "Test {} in suite {} has a missing key."
                .format(test_name, suite_path), prior_error=err)
        except ValueError as err:
            raise TestConfigError(
                "Test {} in suite {} has an invalid value."
                .format(test_name, suite_path), prior_error=err)
        except KeyError as err:
            raise TestConfigError(
                "Test {} in suite {} has an invalid key."
                .format(test_name, suite_path), prior_error=err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "Test {} in suite {} has a YAML Error"
                .format(test_name, suite_path), prior_error=err)
        except TypeError as err:
            raise TestConfigError(
                "Structural issue with test {} in suite {}"
                .format(test_name, suite_path), prior_error=err)

        try:
            self.check_version_compatibility(test_cfg)
        except TestConfigError as err:
            raise TestConfigError(
                "Test '{}' in suite '{}' has incompatibility issues."
                .format(test_name, suite_path), prior_error=err)

        return test_cfg

    def _load_base_config(self, platform: str, host: str) -> TestConfig:
        """Load the base configuration for the given host.  This is done once and saved."""

        # Get the base, empty config, then apply the host config on top of it.
        base_config = self._loader.load_empty()
        options = TestOptions(platform=platform, host=host)

        return self.apply_aux_configs(base_config, options)

    def _load_suite_tests(self, request: TestRequest) -> Dict[str, Dict]:
        """Load the suite config, with standard info applied to """

        # Look for matching suites from amongst all test suites.
        suite_matches = []
        for label, name, path in self.pav_cfg.suite_info:
            if request.matches_suite_name(name):
                suite_matches.append((label, name, path))

        matching_suites = {}
        for label, suite_name, path in suite_matches:
            if name in self._suites:
                # We've already loaded it.
                matching_suites[name] = self._suites[name]
                continue

            # We still use this because it preserves config order.
            cfg_info = self.find_config("suite", suite_name, suite_name)

            if cfg_info.from_suite:
                loader = self._suite_loader
            else:
                loader = self._loader

            try:
                raw_suite_cfg = self._load_raw_config(cfg_info, loader)
            except TestConfigError as err:
                err.request = request
                self.errors.append(err)
                continue

            # Make sure each test has a dict as contents.
            for test_name, raw_test in raw_suite_cfg.items():
                if raw_test is None:
                    raw_suite_cfg[test_name] = {}

            suite_tests = self.resolve_inheritance(raw_suite_cfg, cfg_info.path)

            # Perform essential transformations to each test config.
            for test_cfg_name, test_cfg in list(suite_tests.items()):

                # Basic information that all test configs should have.
                test_cfg['name'] = test_cfg_name
                test_cfg['cfg_label'] = cfg_info.label
                working_dir = self.pav_cfg['configs'][cfg_info.label]['working_dir']
                test_cfg['working_dir'] = working_dir.as_posix()
                test_cfg['suite'] = suite_name
                test_cfg['host'] = self._host
                test_cfg['platform'] = self._platform

                if cfg_info.from_suite:
                    test_cfg['suite_path'] = cfg_info.path.parent.as_posix()
                else:
                    test_cfg['suite_path'] = cfg_info.path.as_posix()

            self._suites[suite_name] = suite_tests
            matching_suites[suite_name] = suite_tests

        return matching_suites

    def _reset_schedulers(self):
        """Reset the cache on all scheduler plugins."""

        _ = self

        for sched_name in schedulers.list_plugins():
            sched = schedulers.get_plugin(sched_name)
            sched.refresh()

    def verify_version_range(self, comp_versions):
        """Validate a version range value."""

        if comp_versions.count('-') > 1:
            raise TestConfigError(
                "Invalid compatible_pav_versions value ('{}'). Not a valid "
                "range.".format(comp_versions))

        min_str = comp_versions.split('-')[0]
        max_str = comp_versions.split('-')[-1]

        min_version = self.verify_version(min_str, comp_versions)
        max_version = self.verify_version(max_str, comp_versions)

        return min_version, max_version

    def verify_version(self, version_str, comp_versions):
        """Ensures version was provided in the correct format, and returns the
        version as a list of digits."""

        _ = self

        if TEST_VERS_RE.match(version_str) is not None:
            version = version_str.split(".")
            return [int(i) for i in version]
        else:
            raise TestConfigError(
                "Invalid compatible_pav_versions value '{}' in '{}'. "
                "Compatible versions must be of form X, X.X, or X.X.X ."
                .format(version_str, comp_versions))

    def check_version_compatibility(self, test_cfg):
        """Returns a bool on if the test is compatible with the current version
        of pavilion."""

        version = PavVars()['version']
        version = [int(i) for i in version.split(".")]
        comp_versions = test_cfg.get('compatible_pav_versions')

        # If no version is provided we assume compatibility
        if not comp_versions:
            return True

        min_version, max_version = self.verify_version_range(comp_versions)

        # Trim pavilion version to the degree dictated by min and max version.
        # This only matters if they are equal, and only occurs when a specific
        # version is provided.
        if min_version == max_version and len(min_version) < len(version):
            offset = len(version) - len(min_version)
            version = version[:-offset]
        if min_version <= version <= max_version:
            return True
        else:
            raise TestConfigError(
                "Incompatible with pavilion version '{}', compatible versions "
                "'{}'.".format(PavVars()['version'], comp_versions))

    def resolve_inheritance(self, suite_cfg, suite_path) \
            -> Dict[str, dict]:
        """Resolve inheritance between tests in a test suite. There's potential
        for loops in the inheritance hierarchy, so we have to be careful of
        that.

        :param base_config: Forms the 'defaults' for each test.
        :param suite_cfg: The suite configuration, loaded from a suite file.
        :param suite_path: The path to the suite file.
        :return: A dictionary of test configs.
        """

        self._loader = self._loader

        # This iterative algorithm recursively resolves the inheritance tree
        # from the root ('__base__') downward. Nodes that have been resolved are
        # separated from those that haven't. We then resolve any nodes whose
        # dependencies are all resolved and then move those nodes to the
        # resolved list. When we run out of nodes that can be resolved,
        # we're done. If there are still unresolved nodes, then a loop must
        # exist.

        test_ldr = self._loader

        # Organize tests into an inheritance tree.
        depended_on_by = defaultdict(list)
        # All the tests for this suite.
        suite_tests = {}
        # A list of tests whose parent's have had their dependencies
        # resolved.
        ready_to_resolve = list()
        if suite_cfg is None:  # Catch null test suites.
            raise TestConfigError("Test Suite {} is empty.".format(suite_path))
        try:
            for test_cfg_name, test_cfg in suite_cfg.items():
                if test_cfg is None:
                    raise TestConfigError(
                        "{} in {} is empty. Nothing will execute."
                        .format(test_cfg_name, suite_path))
                if test_cfg.get('inherits_from') is None:
                    test_cfg['inherits_from'] = '__base__'
                    # Tests that depend on nothing are ready to resolve.
                    ready_to_resolve.append(test_cfg_name)
                else:
                    depended_on_by[test_cfg['inherits_from']].append(test_cfg_name)

                try:
                    suite_tests[test_cfg_name] = test_ldr.normalize(test_cfg,
                                                                    root_name=test_cfg_name)
                except (TypeError, KeyError, ValueError) as err:
                    raise TestConfigError(
                        "Test '{}' in suite '{}' has an error.\n"
                        "See 'pav show test_config' for the pavilion test config format."
                        .format(test_cfg_name, suite_path), prior_error=err)
        except AttributeError:
            raise TestConfigError(
                "Test Suite {} has an invalid structure.\n"
                "Test suites should be structured as a yaml dict/mapping of tests.\n"
                "Example:\n"
                "  test_foo: \n"
                "    run:\n"
                "      cmds: \n"
                "        - echo 'I am a test!'\n"
                " See `pav show test_config` for more info on the test config format."
                .format(suite_path))
        # Add this so we can cleanly depend on it.
        suite_tests['__base__'] = self._base_config

        # Resolve all the dependencies
        while ready_to_resolve:
            # Grab a test whose parent's are resolved and the parent test.
            test_cfg_name = ready_to_resolve.pop(0)
            test_cfg = suite_tests[test_cfg_name]
            parent = suite_tests[test_cfg['inherits_from']]

            # Merge the parent and test.
            try:
                suite_tests[test_cfg_name] = self._loader.merge(parent, test_cfg)
            except TestConfigError as err:
                raise TestConfigError("Error merging in config '{}' from test suite '{}'."
                                      .format(test_cfg_name, suite_path), prior_error=err)

            suite_tests[test_cfg_name] = resolve.cmd_inheritance(suite_tests[test_cfg_name])

            # Now all tests that depend on this one are ready to resolve.
            ready_to_resolve.extend(depended_on_by.get(test_cfg_name, []))
            # Delete this test from here, for a sanity check to know we
            # resolved it.
            if test_cfg_name in depended_on_by:
                del depended_on_by[test_cfg_name]

        # If there's anything with dependencies left, that's bad. It
        # generally means there are cycles in our dependency tree.
        if depended_on_by:
            raise TestConfigError(
                "Tests in suite '{}' have dependencies on {} that "
                "could not be resolved."
                .format(suite_path, tuple(depended_on_by.keys())))

        # Remove the test base
        del suite_tests['__base__']

        return suite_tests
