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
from typing import List, IO, Dict, Tuple, NewType, Union, Any, Iterator, TextIO

import similarity
import yc_yaml
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
from pavilion.utils import union_dictionary
from yaml_config import RequiredError

from .proto_test import RawProtoTest, ProtoTest
from .request import TestRequest

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)

TEST_VERS_RE = re.compile(r'^\d+(\.\d+){0,2}$')


class TestConfigResolver:
    """Converts raw test configurations into their final, fully resolved
    form."""

    def __init__(self, pav_cfg, host: str = None,
                 outfile: TextIO = None, verbosity: int = Verbose.QUIET):
        """Initialize the resolver.

        :param host: The host to configure tests for.
        :param outfile: The file to print output to.
        :param verbosity: Determines the format of the output. (See enums.Verbose)
        """

        self.pav_cfg = pav_cfg

        self._outfile = io.StringIO() if outfile is None else outfile
        self._verbosity = verbosity
        self._loader = TestConfigLoader()
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

        # This may throw an exception. It's expected to be caught by the caller.
        self._base_config = self._load_base_config(host)

        # Raw loaded test suites
        self._suites: Dict[Dict] = {}

    CONF_TYPE_DIRNAMES = {
        'suite': 'tests',
        'series': 'series',
        'host': 'hosts',
        'hosts': 'hosts',
        'mode': 'modes',
        'modes': 'modes',
    }

    def find_config(self, conf_type, conf_name) -> Tuple[str, Path]:
        """Search all of the known configuration directories for a config of the
        given type and name.

        :param str conf_type: 'host', 'mode', or 'test/suite'
        :param str conf_name: The name of the config (without a file extension).
        :return: A tuple of the config label under which a matching config was found
            and the path to that config. If nothing was found, returns (None, None).
        """

        conf_type = self.CONF_TYPE_DIRNAMES[conf_type]

        for label, config in self.pav_cfg.configs.items():
            path = config['path']/conf_type/'{}.yaml'.format(conf_name)
            if path.exists():
                return label, path

        return '', None

    def find_similar_configs(self, conf_type, conf_name) -> List[str]:
        """Find configs with a name similar to the one specified."""

        conf_type = self.CONF_TYPE_DIRNAMES[conf_type]

        for label, config in self.pav_cfg.configs.items():
            type_path = config['path']/conf_type

            names = []
            if type_path.exists():
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

        for label, config in self.pav_cfg.configs.items():
            path = config['path']/'tests'

            if not (path.exists() and path.is_dir()):
                continue

            for file in os.listdir(path.as_posix()):

                file = path/file
                if file.suffix != '.yaml' or not file.is_file():
                    continue

                suite_name = file.stem

                if suite_name not in suites:
                    suites[suite_name] = {
                        'path': file,
                        'label': label,
                        'err': '',
                        'tests': {},
                        'supersedes': [],
                    }
                else:
                    suites[suite_name]['supersedes'].append(file)

                # It's ok if the tests aren't completely validated. They
                # may have been written to require a real host/mode file.
                with file.open('r') as suite_file:
                    try:
                        suite_cfg = TestSuiteLoader().load(suite_file, partial=True)
                    except (TypeError,
                            KeyError,
                            ValueError,
                            yc_yaml.YAMLError) as err:
                        suites[suite_name]['err'] = err
                        continue

                base = self._loader.load_empty()

                try:
                    suite_cfgs = self.resolve_inheritance(
                        base_config=base,
                        suite_cfg=suite_cfg,
                        suite_path=file)
                except Exception as err:  # pylint: disable=W0703
                    suites[suite_name]['err'] = err
                    continue

                def default(val, dval):
                    """Return the dval if val is None."""

                    return dval if val is None else val

                for test_name, conf in suite_cfgs.items():
                    suites[suite_name]['tests'][test_name] = {
                        'conf': conf,
                        'maintainer': default(
                            conf['maintainer']['name'], ''),
                        'email': default(conf['maintainer']['email'], ''),
                        'summary': default(conf.get('summary', ''), ''),
                        'doc': default(conf.get('doc', ''), ''),
                    }
        return suites

    def find_all_configs(self, conf_type):
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

        configs = {}
        for config in self.pav_cfg.configs.values():
            path = config['path'] / conf_type

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

        if modes is None:
            modes = []

        if overrides is None:
            overrides = []


        if overrides is None:
            overrides = []

        if conditions is None:
            conditions = {}

        requests = [TestRequest(req) for req in tests]

        raw_tests = []
        for request in requests:
            # Convert each request into a list of RawProtoTest objects.
            try:
                raw_tests.extend(self._load_raw_configs(request, modes, conditions, overrides))
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
                                progress = len(ptests) - complete
                                progress = 1 - progress/len(ptests)
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

    def _load_raw_config(self, name: str, config_type: str, optional=False) \
            -> Tuple[Any, Union[Path, None], Union[str, None]]:
        """Load the given raw test config file. It can be a host, mode, or suite file.
        Returns a tuple of the config, path, and config label (name of the config area).
        """

        if config_type in ('host', 'mode'):
            loader = self._loader
        elif config_type == 'suite':
            loader = TestSuiteLoader()
        else:
            raise RuntimeError("Unknown config type: '{}'".format(config_type))

        cfg_label, path = self.find_config(config_type, name)
        if path is None:

            if optional:
                return None, None, None

            # Give a special message if it looks like they got their commands mixed up.
            if config_type == 'suite' and name == 'log':
                raise TestConfigError(
                    "Could not find test suite 'log'. Were you trying to run `pav log run`?")

            similar = self.find_similar_configs(config_type, name)
            show_type = 'test' if config_type == 'suite' else config_type
            if similar:
                raise TestConfigError(
                    "Could not find {} config {}.yaml.\n"
                    "Did you mean one of these? {}"
                    .format(config_type, name, ', '.join(similar)))
            else:
                raise TestConfigError(
                    "Could not find {0} config file '{1}.yaml' in any of the "
                    "Pavilion config directories.\n"
                    "Run `pav show {2}` to get a list of available {0} files."
                    .format(config_type, name, show_type))
        try:
            with path.open() as cfg_file:
                # Load the host test config defaults.
                raw_cfg = loader.load_raw(cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open {} config '{}'"
                                  .format(config_type, path), prior_error=err)
        except ValueError as err:
            raise TestConfigError(
                "{} config '{}' has invalid value."
                .format(config_type.capitalize(), path), prior_error=err)
        except KeyError as err:
            raise TestConfigError(
                "{} config '{}' has an invalid key."
                .format(config_type.capitalize(), path), prior_error=err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "{} config '{}' has a YAML Error"
                .format(config_type.capitalize(), path), prior_error=err)

        except TypeError as err:
            raise TestConfigError(
                "Structural issue with {} config '{}'"
                .format(config_type, path), prior_error=err)

        return raw_cfg, path, cfg_label


    def _load_raw_configs(self, request: TestRequest, modes: List[str],
                          conditions: Dict, overrides: List[str]) \
                         -> List[RawProtoTest]:
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

        try:
            suite_tests = self._load_suite_tests(request.suite)
        except TestConfigError as err:
            err.request = request
            self.errors.append(err)
            return []

        added_tests = []
        for test_name in suite_tests:
            if request.matches_test_name(test_name):
                added_tests.append(test_name)


        if not added_tests:
            self.errors.append(TestConfigError(
                "Test suite '{}' does not have a test that matches '{}'.\n"
                "Suite tests are:\n - {}\n"
                .format(
                    request.suite,
                    request.test,
                    "\n - ".join(suite_tests.keys())),
                request=request))
            return []


        test_configs = []
        for test_name in added_tests:
            test_cfg = copy.deepcopy(suite_tests[test_name])

            test_cfg['modes'] = modes

            # Apply any additional conditions.
            if conditions:
                test_cfg['only_if'] = union_dictionary(
                    test_cfg['only_if'], conditions['only_if']
                )
                test_cfg['not_if'] = union_dictionary(
                    test_cfg['not_if'], conditions['not_if']
                )

            # Apply modes.
            try:
                test_cfg = self.apply_modes(test_cfg, modes)
            except TestConfigError as err:
                err.request = request
                self.errors.append(err)
                continue

            # Save the overrides as part of the test config
            test_cfg['overrides'] = overrides

            # Apply overrides
            if overrides:
                try:
                    test_cfg = self.apply_overrides(test_cfg, overrides)
                except TestConfigError as err:
                    err.request = request
                    self.errors.append(err)
                except (KeyError, ValueError) as err:
                    self.errors.append(TestConfigError(
                        'Error applying overrides to test {} from suite {} at:\n{}' \
                        .format(test_cfg['name'], test_cfg['suite'], test_cfg['suite_path']),
                        request, err))
                    continue

            # Result evaluations can be added to all tests at the root pavilion config level.
            result_evals = test_cfg['result_evaluate']
            for key, const in self.pav_cfg.default_results.items():
                if key in result_evals:
                    # Don't override any that are already there.
                    continue

                test_cfg['result_evaluate'][key] = '"{}"'.format(const)

            # Now that we've applied all general transforms to the config, make it into a ProtoTest.
            try:
                rproto_test = RawProtoTest(request, test_cfg, self._base_var_man)
            except TestConfigError as err:
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

    def _load_base_config(self, host) -> Dict:
        """Load the base configuration for the given host.  This is done once and saved."""

        # Get the base, empty config, then apply the host config on top of it.
        base_config = self._loader.load_empty()
        return self.apply_host(base_config, host)

    def _load_suite_tests(self, suite: str):
        """Load the suite config, with standard info applied to """

        if suite in self._suites:
            return self._suites[suite]

        raw_suite_cfg, suite_path, cfg_label = self._load_raw_config(suite, 'suite')
        # Make sure each test has a dict as contents.
        for test_name, raw_test in raw_suite_cfg.items():
            if raw_test is None:
                raw_suite_cfg[test_name] = {}

        suite_tests = self.resolve_inheritance(raw_suite_cfg, suite_path)

        # Perform essential transformations to each test config.
        for test_cfg_name, test_cfg in list(suite_tests.items()):

            # Basic information that all test configs should have.
            test_cfg['name'] = test_cfg_name
            test_cfg['cfg_label'] = cfg_label
            working_dir = self.pav_cfg['configs'][cfg_label]['working_dir']
            test_cfg['working_dir'] = working_dir.as_posix()
            test_cfg['suite'] = suite
            test_cfg['suite_path'] = suite_path.as_posix()
            test_cfg['host'] = self._host

        self._suites[suite] = suite_tests
        return suite_tests

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

    def apply_host(self, test_cfg, host):
        """Apply the host configuration to the given config."""

        loader = self._loader

        raw_host_cfg, _, _ = self._load_raw_config(host, 'host', optional=True)
        if raw_host_cfg is None:
            return test_cfg

        host_cfg = loader.normalize(raw_host_cfg, root_name='host file {}'.format(host))

        try:
            return loader.merge(test_cfg, host_cfg)
        except (KeyError, ValueError) as err:
            raise TestConfigError(
                "Error merging host configuration for host '{}'".format(host))

    def apply_modes(self, test_cfg, modes: List[str]):
        """Apply each of the mode files to the given test config.

        :param test_cfg: The raw test configuration.
        :param modes: A list of mode names.
        """

        loader = self._loader

        for mode in modes:
            raw_mode_cfg, mode_cfg_path, _ = self._load_raw_config(mode, 'mode')
            mode_cfg = loader.normalize(raw_mode_cfg, root_name='mode file {}'.format(mode))

            try:
                test_cfg = loader.merge(test_cfg, mode_cfg)
            except (KeyError, ValueError) as err:
                raise TestConfigError(
                    "Error merging mode configuration for mode '{}'".format(mode))

            test_cfg = resolve.cmd_inheritance(test_cfg)

        return test_cfg

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

        for test_name, test_config in suite_tests.items():
            try:
                suite_tests[test_name] = self._loader.validate(test_config)
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
                self.check_version_compatibility(test_config)
            except TestConfigError as err:
                raise TestConfigError(
                    "Test '{}' in suite '{}' has incompatibility issues."
                    .format(test_name, suite_path), prior_error=err)

        return suite_tests


    NOT_OVERRIDABLE = ['name', 'suite', 'suite_path',
                       'base_name', 'host', 'modes']

    def apply_overrides(self, test_cfg, overrides) -> Dict:
        """Apply overrides to this test.

        :param dict test_cfg: The test configuration.
        :param list overrides: A list of raw overrides in a.b.c=value form.
        :raises: (ValueError,KeyError, TestConfigError)
    """

        config_loader = self._loader

        for ovr in overrides:
            if '=' not in ovr:
                raise ValueError(
                    "Invalid override value. Must be in the form: "
                    "<key>=<value>. Ex. -c run.modules=['gcc'] ")

            key, value = ovr.split('=', 1)
            key = key.strip()
            if not key:
                raise ValueError("Override '{}' given a blank key.".format(ovr))

            key = key.split('.')
            for part in key:
                if ' ' in part:
                    raise ValueError("Override '{}' has whitespace in its key.".format(ovr))
                if not part:
                    raise ValueError("Override '{}' has an empty key part.".format(ovr))

            self._apply_override(test_cfg, key, value)

        try:
            return config_loader.normalize(test_cfg, root_name='overrides')
        except TypeError as err:
            raise TestConfigError("Invalid override", prior_error=err)

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
