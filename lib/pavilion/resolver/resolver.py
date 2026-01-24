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
from functools import reduce
from typing import (List, IO, Dict, Tuple, NewType, Union, Any, Iterator, TextIO, Optional,
                    Iterable, TypeVar)

import similarity
import yc_yaml
import yaml_config as yc
from pavilion.enums import Verbose
from pavilion import output, variables
from pavilion import pavilion_variables
from pavilion import resolve
from pavilion import schedulers
from pavilion import sys_vars
from pavilion.config import PavConfig
from pavilion.errors import SystemPluginError
from pavilion.errors import VariableError, TestConfigError, PavilionError, SchedulerPluginError
from pavilion.pavilion_variables import PavVars
from pavilion.test_config import file_format
from pavilion.test_config.file_format import (TEST_NAME_RE,
                                             KEY_NAME_RE)
from pavilion.test_config.file_format import TestConfigLoader, TestSuiteLoader
from pavilion.utils import is_int, append_to_keys
from pavilion.micro import listfilter, select, set_default, listmap, remove_none, first_with
from pavilion.path_utils import exists, path_product
from yaml_config import RequiredError, YamlConfigLoader

from .proto_test import RawProtoTest, ProtoTest
from .request import TestRequest
from .test_suite import TestSuite
from .config_dir import ConfigDirectory
from .load_config import safe_load_config

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)

TEST_VERS_RE = re.compile(r'^\d+(\.\d+){0,2}$')

TestConfig = Dict


T = TypeVar("T")


class TestOptions:
    """Test options from the command line or series configs."""

    def __init__(self, modes: List[str], overrides: List[str], conditions: Dict):
        self.modes = modes if modes is not None else []
        self.overrides = overrides if overrides is not None else []
        self.conditions = conditions if conditions is not None else {}


class TestConfigResolver:
    """Converts raw test configurations into their final, fully resolved
    form."""

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

        # Raw loaded test suites
        self._suites: Dict[Dict] = {}

    @staticmethod
    def _get_config_dirname(cfg_type: str) -> str:
        """Returns the canonical config directory name for a given config type."""

        dirname = cfg_type.lower()

        if cfg_type == "series":
            return "series"
        if dirname[-1] != 's':
            dirname += 's'

        return dirname

    @staticmethod
    def _get_config_fname(cfg_type: str) -> str:
        """Given a config type, returns the name of the file in the
        suites directory corresponding to that type."""

        fname = cfg_type.lower()

        if fname in ("host", "mode", "platform"):
            fname += 's'

        return f"{fname}"

    def _get_relative_config_paths(self, cfg_type: str, cfg_name: str,
                                   suite_name: Optional[str] = None) -> List[Path]:
        """Get a list of possible paths, relative to the config directory, for the given config
        type and name."""

        paths = []

        if suite_name is not None and cfg_type != "series":
            cfg_path = Path("suites") / suite_name / self._get_config_fname(cfg_type)
            paths.append(cfg_path.with_suffix(".yaml"))
            paths.append(cfg_path.with_suffix(".yml"))

        if cfg_type is "suite":
            # Check in deprecated 'tests' directory
            cfg_path = Path("tests") / suite_name
            paths.append(cfg_path.with_suffix(".yaml"))
            paths.append(cfg_path.with_suffix(".yml"))

        cfg_path = Path(self._get_config_dirname(cfg_type)) / cfg_name
        paths.append(cfg_path.with_suffix(".yaml"))
        paths.append(cfg_path.with_suffix(".yml"))

        return paths

    def get_config_paths(self, cfg_type: str, cfg_name: str,
                         suite_name: Optional[str] = None) -> List[Path]:
        """Given a config name and type, get a list of possible paths to the config."""

        cfg_paths = self.pav_cfg.config_paths
        rel_paths = self._get_relative_config_paths(cfg_type, cfg_name, suite_name)

        return listfilter(exists, path_product(cfg_paths, rel_paths))

    def find_similar_configs(self, cfg_type: str, cfg_name: str,
                             suite: Optional[TestSuite] = None) -> List[str]:
        """Find configs with a name similar to the one specified."""

        names = []

        for path in self.pav_cfg.config_paths:
            names.append(ConfigDirectory(path, "").get_config_names(cfg_type))

            if suite is not None:
                # Only check within the specified suite for similar names, since configs
                # in other suites don't apply.
                names.extend(suite.get_names(cfg_type))

        return similarity.find_matches(cfg_name, names)

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

        cfg_dirs = map(lambda x, y: ConfigDirectory(y["path"], x), self.pav_cfg.configs.items())
        platform_paths = map(lambda x: x.get_config_path("platform", self._platform), cfg_dirs)
        platform_paths = remove_none(platform_paths)

        if len(platform_paths) > 1:
            raise TestConfigError(f"Multiple config files found for platform config with name "
                                  f"{self._platform}: {platform_paths}")
        if len(platform_paths) == 0:
            platform_cfg = None
        else:
            platform_cfg =

        for label, cfg in self.pav_cfg.configs.items():
            cfg_dir = ConfigDirectory(cfg["path"], label)

            platform_cfg = cfg_dir.load("platform", self._platform)
            host_cfg = cfg_dir.load("host", self._host)

            for suite in cfg_dir.suites:
                if suite.name not in suites:
                    suites[name] = {
                        'path': suite.path,
                        'label': label,
                        'err': '',
                        'tests': {},
                        'supersedes': [],
                    }
                else:
                    suites[name]['supersedes'].append(path)

                for test in suite.test_names:
                    try:
                        stack = suite.ancestors(test)
                        stack.append(suite.load_host(self._host, default=host_cfg))
                        stack.append(suite.load_platform(self._platform, default=platform_cfg))
                        stack.append(self._loader.load_empty())
                        stack.reverse()
                        cfg = self.resolve_config_stack(stack)
                    except Exception as err:  # pylint: disable=W0703
                        suites[name]['err'] = err
                        continue

                    suites[name]['tests'][test] = {
                        'conf': cfg,
                        'maintainer': set_default(
                            cfg['maintainer']['name'], ''),
                        'email': set_default(cfg['maintainer']['email'], ''),
                        'summary': set_default(cfg.get('summary', ''), ''),
                        'doc': set_default(cfg.get('doc', ''), ''),
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
        for label, config in self.pav_cfg.configs.values():
            cfg_dir = ConfigDirectory(config["path"], label)

            for path in cfg_dir.get_config_paths(conf_type):

            for file in os.listdir(path.as_posix()):
                name = file.stem
                configs[name] = {}

                try:
                    with file.open() as config_file:
                        config = self._loader.load(config_file)
                    configs[name]['path'] = file
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

    def load_iter(self, tests: List[str], modes: List[str] = None, overrides: List[str] = None,
             conditions=None, batch_size=None) -> Iterator[List[ProtoTest]]:
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

        options = TestOptions(modes, overrides, conditions)

        requests = [TestRequest(req) for req in tests]

        raw_tests = []

        for request in requests:
            # Convert each request into a list of RawProtoTest objects.
            try:
                raw_tests.extend(self._load_prototests(request, options))
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

    def load(self, tests: List[str],
             modes: List[str] = None, overrides: List[str] = None,
             conditions=None, throw_errors: bool = True) -> List[ProtoTest]:
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

    def _load_prototests(self,
                         request: TestRequest,
                         options: TestOptions) -> List[RawProtoTest]:
        """Get a list of raw test configs given a host, list of modes,
        and a list of tests. Each of these configs will be lightly modified with
        a few extra variables about their name, suite, and suite_file, as well
        as guaranteeing that they have 'variables' and 'permutations' sections.

        :param request: A test request to load tests for.
        :param modes: A list (possibly empty) of modes to layer onto the test.
        :param conditions: A list (possibly empty) of conditions to apply to each test config.
        :param overrides: A list of overrides to apply to each test config.
        :return: A list of RawProtoTests.
        """

        stacks = self._load_config_stacks(request)

        test_configs = []

        for stack in stacks:
            raw_test = self._apply_test_options(stack, options, request)
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

    def _load_config_stacks(self, request: TestRequest) -> List[List[yc.ConfigDict]]:
        """Get a list of configs stacks given a host, list of modes,
        and a list of tests. Each of these configs will be lightly modified with
        a few extra variables about their name, suite, and suite_file, as well
        as guaranteeing that they have 'variables' and 'permutations' sections.

        :param request: A test request to load tests for.
        :param modes: A list (possibly empty) of modes to layer onto the test.
        :param conditions: A list (possibly empty) of conditions to apply to each test config.
        :param overrides: A list of overrides to apply to each test config.
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

        return added_tests

    def _apply_test_options(self,
                            base_stack: List[yc.ConfigDict],
                            options: TestOptions,
                            request: TestRequest) -> Optional[Dict]:

        # TODO: This is kind of kludgy. Figure out a better way to transmit the suite name
        suite_name = base_stack[-1][2]["suite"]
        cfg_label = base_stack[-1][2]["cfg_label"]

        try:
            base_stack.extend(self.load_options_stack(options, suite_name))
            test_cfg = self.resolve_config_stack(select(2, base_stack))
        except TestConfigError as err:
            err.request = request
            self.errors.append(err)
            return None

        test_cfg["working_dir"] = self.pav_cfg["configs"][cfg_label]["working_dir"].as_posix()

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

            suite = TestSuite(path, label)

            platform_config = self.load_config("platform",
                                               self._platform,
                                               TestSuite(path),
                                               required=False)
            host_config = self.load_config("host", self._host, TestSuite(path), required=False)

            suite_tests = {}

            for test in suite.test_names:
                config_stack = list(reversed(suite.ancestors(test, platform_config, host_config)))

                suite_tests[test] = config_stack

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

    def load_options_stack(self,
                           options: TestOptions,
                           suite_path: Path) -> List[Tuple[str, str, yc.ConfigDict]]:
        """Get the stack of all configs to apply, labeled with the config type and config name and
        ordered by their sequence of application."""

        configs = []

        conditions = self._make_conditions_config(options.conditions)
        configs.append(("conditions", "conditions", conditions))

        for mode in options.modes:
            configs.append(("mode",
                            mode,
                            self.load_config("mode", mode, TestSuite(suite_path), required=False)))

        for override in options.overrides:
            try:
                configs.append(("override", "override", self._make_override_config(override)))
            except (KeyError, ValueError) as err:
                raise TestConfigError(
                    'Error parsing overrides for test {} from suite {} at:\n{}' \
                    .format(raw_test_cfg['name'], raw_test_cfg['suite'],
                    raw_test_cfg['suite_path']), prior_error=err)

        return configs

    def resolve_config_stack(self, configs: List[TestConfig]) -> TestConfig:
        """Resolve a list of test configs into a single test config."""

        return reduce(self._apply_config, configs)

    def load_config(self,
                    cfg_type: str,
                    cfg_name: str,
                    suite: Optional[TestSuite] = None,
                    required: bool = True) -> yc.ConfigDict:
        """Load the config, optionally raising an error if it cannot be found. Returns an empty dict
        if the config does not exist."""

        if suite is not None:
            cfg = suite.load(cfg_type, cfg_name)

            if not cfg.empty():
                return cfg

        cfg_dirs = listmap(lambda x, y: ConfigDirectory(y["path"], x), self.pav_cfg.configs.items())
        cfg_paths = map(lambda x: x.get_config_path(cfg_type, cfg_name), cfg_dirs)
        cfg_paths = list(remove_none(cfg_paths))

        if len(cfg_paths) > 1:
            raise TestConfigError(f"Multiple config files found for {cfg_type} config with name "
                                  f"{cfg_name}: {cfg_paths}")
        elif len(cfg_paths) == 0 and required:
            similar = self.find_similar_configs(cfg_type, cfg_name, suite)

            if similar:
                raise TestConfigError(
                    "Could not find {} config {}.yaml.\n"
                    "Did you mean one of these? {}"
                    .format(cfg_type, cfg_name, ', '.join(similar)))
            else:
                raise TestConfigError(
                    "Could not find {0} config file '{1}.yaml' in any of the "
                    "Pavilion config directories.\n"
                    "Run `pav show {2}` to get a list of available {0} files."
                    .format(cfg_type, cfg_name, cfg_type))
        elif len(cfg_paths) == 0:
            return yc.ConfigDict(raw_cfg)

        return first_with(
                    lambda x: not x.empty(),
                    map(lambda x: x.load(cfg_type, cfg_name), cfg_dirs))

    def _apply_config(self, base: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Cache results so we're not doing redundant work - HW
        try:
            return self._loader.merge(base, config)
        except (KeyError, ValueError, IndexError) as err:
            raise TestConfigError("Error merging configuration")

    def _make_conditions_config(self, conditions: Dict[str, Any]) -> yc.ConfigDict:
        """Create the conditions dict."""

        for value in conditions.values():
            append_to_keys(value, "+")

        return yc.ConfigDict(conditions)

    NOT_OVERRIDABLE = ['name', 'suite', 'suite_path',
                       'base_name', 'host', 'platform', 'modes']

    def _make_override_config(self, override: str) -> yc.ConfigDict:
        """Convert an override string to a ConfigDict object."""

        if '=' not in override:
            raise ValueError(
                "Invalid override value. Must be in the form: "
                "<key>=<value>. Ex. -c run.modules=['gcc'] ")

        key, value = override.split('=', 1)
        key = key.strip()

        if key == '':
            raise ValueError("Override '{}' given a blank key.".format(override))

        key = key.split('.')

        if key[0] in self.NOT_OVERRIDABLE:
            raise KeyError("You can't override the '{}' key in a test config"
                           .format(key[0]))

        cfg = self._loader.normalize(self._override_list_to_dict(key, value))

        cfg["overrides+"] = [override]

        return cfg

    @classmethod
    def _override_list_to_dict(cls, key: List[str], value: Any) -> Dict[str, Any]:
        """Convert a list of override keys and a value to a dictionary."""

        if key[0] == ' ':
            raise ValueError("Override has whitespace in its key.")
        if key[0] == '':
            raise ValueError("Override has an empty key part.")

        if len(key) == 2 and is_int(key[1]):
            value = [None] * (int(key[1]) - 1) + [value]
            final_key = key[0] + "@"
        elif len(key) == 1:
            final_key = key[0]
        else:
            return {key[0]: cls._override_list_to_dict(key[1:], value)}

        return {final_key: cls._validate_override_value(value, final_key)}

    @staticmethod
    def _validate_override_value(value: Any, disp_key: str) -> Any:
        """Validate the override value by attempting to write and load it from a file."""

        _value = value
        is_list = True

        if not isinstance(value, list):
            is_list = False
            value = [value]

        res = value.copy()

        for idx, val in enumerate(value):
            try:
                dummy_file = io.StringIO(val)
                res[idx] = yc_yaml.safe_load(dummy_file)
            except (yc_yaml.YAMLError, ValueError, KeyError) as err:
                raise TestConfigError("Invalid value '{}' for key '{}' in overrides"
                                    .format(_value, disp_key), prior_error=err)

        if is_list:
            return res

        return res[0]

    def _apply_override(self, test_cfg, key, value):
        """Set the given key to the given value in test_cfg.

        :param dict test_cfg: The test configuration.
        :param [str] key: A list of key components, like
            ``[`slurm', 'num_nodes']``
        :param str value: The value to assign. If this looks like a json
            structure, it will be decoded and treated as one.
        """

        cfg = test_cfg

        disp_key = '.'.join(key)

        if key[0] in self.NOT_OVERRIDABLE:
            raise KeyError("You can't override the '{}' key in a test config"
                           .format(key[0]))

        key_copy = list(key)
        last_cfg = None
        last_key = None

        # Normalize simple variable values.
        if key[0] == 'variables' and len(key) in (2, 3):
            is_var_value = True
        else:
            is_var_value = False

        # Validate the key by walking the config according to the key
        while key_copy:
            part = key_copy.pop(0)

            if isinstance(cfg, list):
                try:
                    idx = int(part)
                except ValueError:
                    raise KeyError("Trying to override list item with a "
                                   "non-integer '{}' in key '{}'."
                                   .format(part, disp_key))

                try:
                    last_cfg = cfg
                    last_key = idx
                    cfg = cfg[idx]
                except IndexError:
                    raise KeyError(
                        "Trying to override index '{}' from key '{}' "
                        "but the index is out of range."
                        .format(part, disp_key))
            elif isinstance(cfg, dict):

                if part not in cfg and key_copy:
                    raise KeyError("Trying to override '{}' from key '{}', "
                                   "but there is no such key."
                                   .format(part, disp_key))

                # It's ok to override a key that doesn't exist if it's the
                # last key component. We'll validate everything anyway.
                last_cfg = cfg
                last_key = part
                cfg = cfg.get(part, None)
            else:
                raise KeyError("Tried, to override key '{}', but '{}' isn't "
                               "a dict or list."
                               .format(disp_key, part))

        if last_cfg is None:
            # Should never happen.
            raise RuntimeError(
                "Trying to override an empty key: {}".format(key))

        # We should be at the final place where the value should go.
        try:
            dummy_file = io.StringIO(value)
            value = yc_yaml.safe_load(dummy_file)
        except (yc_yaml.YAMLError, ValueError, KeyError) as err:
            raise TestConfigError("Invalid value '{}' for key '{}' in overrides"
                                  .format(value, disp_key), prior_error=err)

        last_cfg[last_key] = self.normalize_override_value(value, is_var_value)

    def normalize_override_value(self, value, is_var_value=False):
        """Normalize a value to one compatible with Pavilion configs. It can
        be any structure of dicts and lists, as long as the leaf values are
        strings.

        :param value: The value to normalize.
        :param is_var_value: True if the value will be used to set a variable value.
        :returns: A string or a structure of dicts/lists whose leaves are
            strings.
        """

        if isinstance(value, (int, float, bool, bytes)):
            value = str(value)

        if isinstance(value, str):
            if is_var_value:
                # Normalize a simple value into the standard variable format.
                return [{None: value}]
            else:
                return value
        elif isinstance(value, (list, tuple)):
            return [self.normalize_override_value(v) for v in value]
        elif isinstance(value, dict):
            dict_val = {str(k): self.normalize_override_value(v)
                        for k, v in value.items()}

            if is_var_value:
                # Normalize a single dict item into a list of them for variables.
                return [dict_val]
            else:
                return dict_val
        else:
            raise ValueError("Invalid type in override value: {}".format(value))
