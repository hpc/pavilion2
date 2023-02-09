"""
Pavilion has to take a bunch of raw Suite/Test configurations, incorporate
various Pavilion variables, resolve test inheritance and permutations,
and finally produce a bunch of TestRun objects. These steps, and more,
are all handled by the TestConfigResolver
"""

# pylint: disable=too-many-lines

import copy
import fnmatch
import io
import logging
import multiprocessing as mp
import os
import pprint
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List, IO, Dict, Tuple, NewType, Union, Any

import yc_yaml
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

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)

TEST_VERS_RE = re.compile(r'^\d+(\.\d+){0,2}$')


class TestRequest:
    """Represents a user request for a test. May end up being multiple tests."""

    REQUEST_RE = re.compile(r'^(?:(\d+)\*)?'       # Leading repeat pattern ('5*', '20*', ...)
                            r'([a-zA-Z0-9_-]+)'  # The test suite name.
                            r'(?:\.([a-zA-Z0-9_*-]+?))?'  # The test name.
                            r'(?:\.([a-zA-Z0-9_*-]+?))?'  # The permutation name.
                            r'(?:\*(\d+))?$'  # The post count for error handling
                            )

    def __init__(self, request_str):

        self.count = 1
        self.request = request_str
        self.checked = False

        match = self.REQUEST_RE.match(request_str)
        if not match:
            raise TestConfigError(
                "Test requests must be in the form 'suite_name', 'suite_name.test_name', or\n"
                "'suite_name.test_name.permutation_name. They may be preceeded by a repeat\n"
                "multiplier (e.g. '5*').\n"
                "Got: {}".format(request_str))

        count, self.suite, self.test, self.permutation, count_post = match.groups()

        if count_post:
            raise TestConfigError("A post-repeat count is specified. That's not allowed: {}. "
                                  "Please specify a pre-repeat count.".format(self.request))
        
        if count:
            self.count = int(count)

    def __str__(self):
        return "Request: {}.{} * {}".format(self.suite, self.test, self.count)

class ProtoTest:
    """An simple object that holds the pair of a test config and its variable
    manager."""

    def __init__(self, config: Dict, var_man: variables.VariableSetManager):
        self.config = config  # type: dict
        self.var_man = var_man  # type: variables.VariableSetManager

    def copy(self) -> 'ProtoTest':
        return ProtoTest(config=copy.deepcopy(self.config),
                         var_man=copy.deepcopy(self.var_man))

class TestConfigResolver:
    """Converts raw test configurations into their final, fully resolved
    form."""

    def __init__(self, pav_cfg):
        self.pav_cfg = pav_cfg

        self.base_var_man = variables.VariableSetManager()

        try:
            self.base_var_man.add_var_set(
                'sys', sys_vars.get_vars(defer=True)
            )
        except SystemPluginError as err:
            raise TestConfigError(
                "Error in system variables"
                .format(err)
            )

        self.base_var_man.add_var_set(
            'pav', pavilion_variables.PavVars()
        )

    def build_variable_manager(self, raw_test_cfg):
        """Get all of the different kinds of Pavilion variables into a single
        variable set manager for this test.

        NOTE: Errors generated when getting scheduler variables will be placed
            in the 'sched.errors' variable in the variable manager. This can happen
            primarily because we're doing this before we filter tests for conditions
            like the type of system the test is running on. If the test is skipped,
            then it's a not problem, but in all other cases we should inform the user.

        :param raw_test_cfg: A raw test configuration. It should be from before
            any variables are resolved.
        :rtype: variables.VariableSetManager
        """

        user_vars = raw_test_cfg.get('variables', {})
        var_man = copy.deepcopy(self.base_var_man)
        test_name = raw_test_cfg.get('name', '<no name>')

        # Since per vars are the highest in resolution order, we can make things
        # a bit faster by adding these after we find the used per vars.
        try:
            var_man.add_var_set('var', user_vars)
        except VariableError as err:
            raise TestConfigError("Error in variables section for test '{}'"
                                  .format(test_name), err)

        # This won't have a 'sched' variable set unless we're permuting over scheduler vars.
        return var_man

    def check_permutations(self, resolved_tests, test_checks, outfile: IO[str] = None) -> List[ProtoTest]:
        """Check the list of resolved tests and ensure they match the given request.

        :param resolved_tests: An unfiltered list of all resolved tests.
        :param test_checks: A list of test requests.
        :param outfile: Where to write status output.
        :rtype: List[ProtoTest]
        """

        _ = self

        checked_tests = []

        for test, check in zip(resolved_tests, test_checks):
            test_name = ''
            check_name = check.suite

            for item in [check.test, check.permutation]:
                if item:
                    check_name += '.' + item
                else:
                    check_name += '.*'

            if test.config['subtitle']:
                test_name = '.'.join([test.config['suite'], test.config['name'], test.config['subtitle']])
            else:
                if check.permutation:
                    output.fprint(outfile, 'Permutation not found: {}.'.format(check_name))
                    continue

                checked_tests.append(test)
                continue

            if fnmatch.fnmatch(test_name, check_name):
                checked_tests.append(test)
                check.checked = True
            elif not check.checked:
                output.fprint(outfile, 'Permutation not found: {}.'.format(check_name))

        return checked_tests


    def check_variable_consistency(self, config: Dict):
        """Check all the variables defined as defaults with a null value to
        make sure they were actually defined, and that all sub-var dicts have consistent keys."""

        _ = self

        test_name = config.get('name', '<unnamed>')
        test_suite = config.get('suite_path', '<no suite>')

        for var_key, values in config.get('variables', {}).items():

            if not values:
                raise TestConfigError(
                    "In test '{}' from suite '{}', test variable '{}' was defined "
                    "but wasn't given a value."
                    .format(test_name, test_suite, var_key))

            first_value_keys = set(values[0].keys())
            for i, value in enumerate(values):
                for subkey, subval in value.items():
                    if subkey is None:
                        full_key = var_key
                    else:
                        full_key = '.'.join([var_key, subkey])

                    if subval is None:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has an empty "
                            "value. Empty defaults are fine (as long as they are "
                            "overridden), but regular variables should always be given "
                            "a value (even if it's just an empty string)."
                            .format(test_name, test_suite, full_key))

                value_keys = set(value.keys())
                if value_keys != first_value_keys:
                    if None in first_value_keys:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has  "
                            "inconsistent keys. The first value was a simple variable "
                            "with value '{}', while value {} had keys {}"
                            .format(test_name, test_suite, var_key, values[0][None], i + 1,
                                    value_keys))
                    elif None in value_keys:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has "
                            "inconsistent keys.The first value had keys {}, while value "
                            "{} was a simple value '{}'."
                            .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                    value[None]))
                    else:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has "
                            "inconsistent keys. The first value had keys {}, "
                            "while value {} had keys {}"
                            .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                    value_keys))

                if not values:
                    raise TestConfigError(
                        "In test '{}' from suite '{}', test variable '{}' was defined "
                        "but wasn't given a value."
                        .format(test_name, test_suite, var_key))

                first_value_keys = set(values[0].keys())
                for i, value in enumerate(values):
                    for subkey, subval in value.items():
                        if subkey is None:
                            full_key = var_key
                        else:
                            full_key = '.'.join([var_key, subkey])

                        if subval is None:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has an empty "
                                "value. Empty defaults are fine (as long as they are "
                                "overridden), but regular variables should always be given "
                                "a value (even if it's just an empty string)."
                                .format(test_name, test_suite, full_key))

                    value_keys = set(value.keys())
                    if value_keys != first_value_keys:
                        if None in first_value_keys:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has  "
                                "inconsistent keys. The first value was a simple variable "
                                "with value '{}', while value {} had keys {}"
                                .format(test_name, test_suite, var_key, values[0][None], i + 1,
                                        value_keys))
                        elif None in value_keys:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has "
                                "inconsistent keys.The first value had keys {}, while value "
                                "{} was a simple value '{}'."
                                .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                        value[None]))
                        else:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has "
                                "inconsistent keys. The first value had keys {}, "
                                "while value {} had keys {}"
                                .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                        value_keys))


    def find_config(self, conf_type, conf_name) -> Tuple[str, Path]:
        """Search all of the known configuration directories for a config of the
        given type and name.

        :param str conf_type: 'host', 'mode', or 'test/suite'
        :param str conf_name: The name of the config (without a file extension).
        :return: A tuple of the config label under which a matching config was found
            and the path to that config. If nothing was found, returns (None, None).
        """

        if conf_type == 'suite':
            conf_type = 'tests'
        elif conf_type == 'host':
            conf_type = 'hosts'
        elif conf_type == 'mode':
            conf_type = 'modes'

        for label, config in self.pav_cfg.configs.items():
            path = config['path']/conf_type/'{}.yaml'.format(conf_name)
            if path.exists():
                return label, path

        return '', None

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
                        suite_cfg = TestSuiteLoader().load(suite_file,
                                                           partial=True)
                    except (
                            TypeError,
                            KeyError,
                            ValueError,
                            yc_yaml.YAMLError,
                    ) as err:
                        suites[suite_name]['err'] = err
                        continue

                base = TestConfigLoader().load_empty()

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
                            config = file_format.TestConfigLoader().load(
                                config_file)
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

    def load(self, tests: List[str], host: str = None,
             modes: List[str] = None, overrides: List[str] = None,
             conditions=None, outfile: IO[str] = None) \
            -> List[ProtoTest]:
        """Load the given tests, updated with their host and mode files.
        Returns 'ProtoTests', a simple object with 'config' and 'var_man'
        attributes for each resolved test.

        :param tests: A list of test names to load.
        :param host: The host to load tests for. Defaults to the value
            of the 'sys_name' variable.
        :param modes: A list of modes to load.
        :param overrides: A dict of key:value pairs to apply as overrides.
        :param conditions: A dict containing the only_if and not_if conditions.
        :param outfile: Where to write status output.
        """

        if outfile is None:
            outfile = io.StringIO()

        if modes is None:
            modes = []

        if overrides is None:
            overrides = []

        if host is None:
            host = self.base_var_man['sys.sys_name']

        requested_tests = [TestRequest(test_req) for test_req in tests]

        raw_tests = self.load_raw_configs(requested_tests, host, modes, conditions=conditions,
                                          overrides=overrides)

        for _, test_cfg in raw_tests:
            # Make sure the variables section is properly set up.
            self.check_variable_consistency(test_cfg)

        permuted_tests = []
        for request, test_cfg in raw_tests:
            var_man = self.build_variable_manager(test_cfg)

            # Resolve all configuration permutations.
            try:
                p_cfg, permutes = self.resolve_permutations(test_cfg, var_man)
                for p_var_man in permutes:
                    # Get the scheduler from the config.
                    permuted_tests.append((request, p_cfg, p_var_man))

            except TestConfigError as err:
                msg = 'Error resolving permutations for test {} from {}' \
                    .format(test_cfg['name'], test_cfg['suite_path'])

                raise TestConfigError(msg, err)
        complete = 0

        resolved_tests = []
        if not permuted_tests:
            return []
        elif len(permuted_tests) == 1:
            request, test_cfg, var_man = permuted_tests[0]
            resolved_cfg = self.resolve(test_cfg, var_man)
            resolved_tests.append((request, ProtoTest(resolved_cfg, var_man)))
        else:
            async_results = []
            proc_count = min(self.pav_cfg['max_cpu'], len(permuted_tests))
            with mp.Pool(processes=proc_count) as pool:
                for request, test_cfg, var_man in permuted_tests:
                    aresult = pool.apply_async(self.resolve, (test_cfg, var_man))
                    async_results.append((aresult, request, var_man))

                while async_results:
                    not_ready = []
                    for aresult, request, var_man in list(async_results):
                        if aresult.ready():
                            try:
                                result = aresult.get()
                            except PavilionError:
                                raise
                            except Exception as err:
                                raise TestConfigError("Unexpected error loading tests", err)

                            resolved_tests.append((request, ProtoTest(result, var_man)))

                            complete += 1
                            progress = len(permuted_tests) - complete
                            progress = 1 - progress/len(permuted_tests)
                            output.fprint(outfile,
                                          "Resolving Test Configs: {:.0%}".format(progress),
                                          end='\r')
                        else:
                            not_ready.append((aresult, request, var_man))
                    async_results = not_ready

                    if async_results:
                        try:
                            async_results[0][0].wait(0.5)
                        except TimeoutError:
                            pass

        if outfile and len(permuted_tests) > 1:
            output.fprint(outfile, '')

        # Now that tests are resolved, multiply them out based on the requested count.
        all_resolved_tests = []
        permutation_filters = []
        for request, proto_test in resolved_tests:
            # Add the original, copy the rest.
            all_resolved_tests.append(proto_test)
            permutation_filters.append(request)
            for i in range(request.count - 1):
                all_resolved_tests.append(proto_test.copy())
                permutation_filters.append(request)

        # NOTE: The deferred scheduler errors will be handled when we try to save
        #       the test object. (See build_variable_manager() above)

        all_resolved_tests = self.check_permutations(all_resolved_tests, permutation_filters, outfile)

        return all_resolved_tests

    def resolve(self, test_cfg: dict, var_man: variables.VariableSetManager) -> Dict:
        """Resolve all the strings in one test config. This mostly exists to consolidate
        error handling (we could call resolve.test_config directly)."""

        _ = self

        try:
            return resolve.test_config(test_cfg, var_man)
        except TestConfigError as err:
            if test_cfg.get('permute_on'):
                permute_values = {key: var_man.get(key) for key in test_cfg['permute_on']}

                raise TestConfigError(
                    "Error resolving test {} with permute values:"
                    .format(test_cfg['name']), err, data=permute_values)
            else:
                raise TestConfigError(
                    "Error resolving test {}".format(test_cfg['name']), err)


    def _load_raw_config(self, name: str, config_type: str, optional=False) \
            -> Tuple[Any, Union[Path, None], Union[str, None]]:
        """Load the given raw test config file. It can be a host, mode, or suite file.
        Returns a tuple of the config, path, and config label (name of the config area).
        """

        if config_type in ('host', 'mode'):
            loader = TestConfigLoader()
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

            raise TestConfigError(
                "Could not find {} config file '{}.py' in any of the Pavilion config directories.\n"
                "See `pav config list` for a list of config directories.".format(config_type, name))

        try:
            with path.open() as cfg_file:
                # Load the host test config defaults.
                raw_cfg = loader.load_raw(cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open {} config '{}'"
                                  .format(config_type, path), err)
        except ValueError as err:
            raise TestConfigError(
                "{} config '{}' has invalid value."
                .format(config_type.capitalize(), path), err)
        except KeyError as err:
            raise TestConfigError(
                "{} config '{}' has an invalid key."
                .format(config_type.capitalize(), path), err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "{} config '{}' has a YAML Error"
                .format(config_type.capitalize(), path), err)
        except TypeError as err:
            raise TestConfigError(
                "Structural issue with {} config '{}'"
                .format(config_type, path), err)

        return raw_cfg, path, cfg_label


    def load_raw_configs(self, tests: List[TestRequest], host: str, modes: List[str],
                         conditions: Union[None, Dict] = None,
                         overrides: Union[None, List[str]] = None) \
                         -> List[Tuple[TestRequest, Dict]]:
        """Get a list of raw test configs given a host, list of modes,
        and a list of tests. Each of these configs will be lightly modified with
        a few extra variables about their name, suite, and suite_file, as well
        as guaranteeing that they have 'variables' and 'permutations' sections.

        :param list tests: A list (possibly empty) of tests to load. Each test
            can be either a '<test_suite>.<test_name>', '<test_suite>',
            or '<test_suite>.*'. A test suite by itself (or with a .*) get every
            test in a suite.
        :param host: The host the test is running on.
        :param modes: A list (possibly empty) of modes to layer onto the test.
        :param conditions: A list (possibly empty) of conditions to apply to each test config.
        :param overrides: A list of overrides to apply to each test config.
        :return: A list of (request, config) tuples.
        """

        test_config_loader = TestConfigLoader()

        # Get the base, empty config, then apply the host config on top of it.
        base_config = test_config_loader.load_empty()
        base_config = self.apply_host(base_config, host)

        # Find all the suite configs.
        suites = {}
        for request in tests:
            # Only load each test suite once.
            if request.suite in suites:
                continue

            raw_suite_cfg, suite_path, cfg_label = self._load_raw_config(request.suite, 'suite')
            suite_tests = self.resolve_inheritance(base_config, raw_suite_cfg, request.suite)

            # Perform essential transformations to each test config.
            for test_cfg_name, test_cfg in list(suite_tests.items()):

                # Basic information that all test configs should have.
                test_cfg['name'] = test_cfg_name
                test_cfg['cfg_label'] = cfg_label
                working_dir = self.pav_cfg['configs'][cfg_label]['working_dir']
                test_cfg['working_dir'] = working_dir.as_posix()
                test_cfg['suite'] = request.suite
                test_cfg['suite_path'] = str(suite_path)
                test_cfg['host'] = host
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
                test_cfg = self.apply_modes(test_cfg, modes)

                # Apply overrides
                if overrides:
                    try:
                        test_cfg = self.apply_overrides(test_cfg, overrides)
                    except (KeyError, ValueError) as err:
                        raise TestConfigError(
                            'Error applying overrides to test {} from suite {} at:\n{}' \
                            .format(test_cfg['name'], test_cfg['suite'], test_cfg['suite_path']),
                            err)

                # Result evaluations can be added to all tests at the root pavilion config level.
                result_evals = test_cfg['result_evaluate']
                for key, const in self.pav_cfg.default_results.items():
                    if key in result_evals:
                        # Don't override any that are already there.
                        continue

                    test_cfg['result_evaluate'][key] = '"{}"'.format(const)

                # Save our altered test config.
                suite_tests[test_cfg_name] = test_cfg

            suites[request.suite] = suite_tests

        all_tests: List[Tuple[TestRequest, Dict]] = []
        # Make sure we get the correct amount of tests
        for request in tests:
            if request.test is None:
                # Add all tests in the suite, except the 'hidden' ones.
                add_tests = [test_name for test_name in suites[request.suite].keys()
                             if not test_name.startswith('_')]
            else:
                # Add a single test, even a 'hidden' one.
                add_tests = [request.test]

            # Add each of the tests to our list of loaded tests.
            for test_check in add_tests:
                checked_tests = fnmatch.filter(list(suites[request.suite].keys()), test_check)
                if checked_tests:
                    for test_name in checked_tests:
                        all_tests.append((request, suites[request.suite][test_name]))
                else:
                    raise TestConfigError(
                        "Test suite '{}' does not contain a test '{}'."
                        .format(request.suite, test_check))

        return all_tests

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

        loader = TestConfigLoader()

        raw_host_cfg, _, _ = self._load_raw_config(host, 'host', optional=True)
        if raw_host_cfg is None:
            return test_cfg

        host_cfg = loader.normalize(raw_host_cfg)

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

        loader = TestConfigLoader()

        for mode in modes:
            raw_mode_cfg, mode_cfg_path, _ = self._load_raw_config(mode, 'mode')
            mode_cfg = loader.normalize(raw_mode_cfg)

            try:
                test_cfg = loader.merge(test_cfg, mode_cfg)
            except (KeyError, ValueError) as err:
                raise TestConfigError(
                    "Error merging host configuration for host '{}'".format(mode))

            test_cfg = resolve.cmd_inheritance(test_cfg)

        return test_cfg

    def resolve_inheritance(self, base_config, suite_cfg, suite_path) \
            -> Dict[str, dict]:
        """Resolve inheritance between tests in a test suite. There's potential
        for loops in the inheritance hierarchy, so we have to be careful of
        that.

        :param base_config: Forms the 'defaults' for each test.
        :param suite_cfg: The suite configuration, loaded from a suite file.
        :param suite_path: The path to the suite file.
        :return: A dictionary of test configs.
        """

        test_config_loader = TestConfigLoader()

        # This iterative algorithm recursively resolves the inheritance tree
        # from the root ('__base__') downward. Nodes that have been resolved are
        # separated from those that haven't. We then resolve any nodes whose
        # dependencies are all resolved and then move those nodes to the
        # resolved list. When we run out of nodes that can be resolved,
        # we're done. If there are still unresolved nodes, then a loop must
        # exist.

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
                    suite_tests[test_cfg_name] = TestConfigLoader().normalize(test_cfg)
                except (TypeError, KeyError, ValueError) as err:
                    raise TestConfigError(
                        "Test {} in suite {} has an error."
                        .format(test_cfg_name, suite_path), err)
        except AttributeError:
            raise TestConfigError(
                "Test Suite {} has objects but isn't a dict. Check syntax "
                " or prepend '-f' if running a list of tests "
                .format(suite_path))
        # Add this so we can cleanly depend on it.
        suite_tests['__base__'] = base_config

        # Resolve all the dependencies
        while ready_to_resolve:
            # Grab a test whose parent's are resolved and the parent test.
            test_cfg_name = ready_to_resolve.pop(0)
            test_cfg = suite_tests[test_cfg_name]
            parent = suite_tests[test_cfg['inherits_from']]

            # Merge the parent and test.
            try:
                suite_tests[test_cfg_name] = test_config_loader.merge(parent,
                                                                      test_cfg)
            except TestConfigError as err:
                raise TestConfigError("Error merging in config '{}' from test suite '{}'."
                                      .format(test_cfg_name, suite_path), err)

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
                suite_tests[test_name] = test_config_loader.validate(test_config)
            except RequiredError as err:
                raise TestConfigError(
                    "Test {} in suite {} has a missing key."
                    .format(test_name, suite_path), err)
            except ValueError as err:
                raise TestConfigError(
                    "Test {} in suite {} has an invalid value."
                    .format(test_name, suite_path), err)
            except KeyError as err:
                raise TestConfigError(
                    "Test {} in suite {} has an invalid key."
                    .format(test_name, suite_path), err)
            except yc_yaml.YAMLError as err:
                raise TestConfigError(
                    "Test {} in suite {} has a YAML Error"
                    .format(test_name, suite_path), err)
            except TypeError as err:
                raise TestConfigError(
                    "Structural issue with test {} in suite {}"
                    .format(test_name, suite_path), err)

            try:
                self.check_version_compatibility(test_config)
            except TestConfigError as err:
                raise TestConfigError(
                    "Test '{}' in suite '{}' has incompatibility issues."
                    .format(test_name, suite_path), err)

        return suite_tests

    def check_permute_vars(self, permute_on, var_man) -> List[Tuple[str, str]]:
        """Check the permutation variables and report errors. Returns a set of the
        (var_set, var) tuples."""

        _ = self
        per_vars = set()
        for per_var in permute_on:
            try:
                var_set, var, index, subvar = var_man.resolve_key(per_var)
            except KeyError:
                # We expect to call this without adding scheduler variables first.
                if per_var.startswith('sched.') and '.' not in per_var:
                    per_vars.add(('sched', per_var))
                    continue
                else:
                    raise TestConfigError(
                        "Permutation variable '{}' is not defined. Note that if you're permuting "
                        "over a scheduler variable, you must specify the variable type "
                        "(ie 'sched.node_list')"
                        .format(per_var))
            if index is not None or subvar is not None:
                raise TestConfigError(
                    "Permutation variable '{}' contains index or subvar. "
                    "When giving a permutation variable only the variable name "
                    "and variable set (optional) are allowed. Ex: 'sys.foo' "
                    " or just 'foo'."
                    .format(per_var))
            elif var_man.any_deferred(per_var):
                raise TestConfigError(
                    "Permutation variable '{}' references a deferred variable "
                    "or one with deferred components."
                    .format(per_var))
            per_vars.add((var_set, var))

        return sorted(list(per_vars))

    def make_subtitle_template(self, permute_vars, subtitle, var_man) -> str:
        """Make an appropriate default subtitle given the permutation variables.

        :param permute_vars: The permutation vars, as returned by check_permute_vars.
        :param subtitle: The raw existing subtitle.
        :param var_man: The variable manager.
        """

        _ = self

        parts = []
        if permute_vars and subtitle is None:
            var_dict = var_man.as_dict()
            # These should already be sorted
            for var_set, var in permute_vars:
                if var_set == 'sched':
                    parts.append('{{sched.' + var + '}}')
                elif isinstance(var_dict[var_set][var][0], dict):
                    parts.append('_' + var + '_')
                else:
                    parts.append('{{' + var + '}}')

            return '-'.join(parts)
        else:
            return subtitle

    def resolve_permutations(self, test_cfg: Dict, base_var_man: variables.VariableSetManager)\
            -> Tuple[Dict, List[variables.VariableSetManager]]:
        """Resolve permutations for all used permutation variables, returning a
        variable manager for each permuted version of the test config. This requires that
        we iteratively apply permutations - permutation variables may contain references that
        refer to each other (or scheduler variables), so we have to resolve non-permuted
        variables, apply any permutations that are ready, and repeat until all are applied
        (taking a break to add scheduler variables when we can't proceed without them anymore).

        :param dict test_cfg: The raw test configuration dictionary.
        :param variables.VariableSetManager base_var_man: The variables for
            this config (absent the scheduler variables).
        :returns: The modified configuration, and a list of variable set
            managers, one for each permutation.
        :raises TestConfigError: When there are problems with variables or the
            permutations.
        """

        _ = self

        permute_on = test_cfg['permute_on']
        test_cfg['permute_base'] = uuid.uuid4().hex

        used_per_vars = self.check_permute_vars(permute_on, base_var_man)
        test_cfg['subtitle'] = self.make_subtitle_template(
            used_per_vars, test_cfg.get('subtitle'), base_var_man)

        test_name = test_cfg.get('name', '<no name>')

        sched_name = test_cfg.get('scheduler')
        if sched_name is None:
            raise TestConfigError("No scheduler was given. This should only happen "
                                  "when unit tests fail to define it.")
        try:
            sched = schedulers.get_plugin(sched_name)
        except SchedulerPluginError:
            raise TestConfigError("Could not find scheduler '{}' for test '{}'"
                                  .format(sched_name, test_name))
        if not sched.available():
            raise TestConfigError("Test {} requested scheduler {}, but it isn't "
                                  "available on this system.".format(test_name, sched_name))

        var_men = [base_var_man]
        # Keep trying to resolve variables and create permutations until we're out. This
        # iteratively takes care of any permutations that aren't self-referential and don't
        # depend on the scheduler variables.
        while True:
            # Resolve what references we can in variables, but refuse to resolve any based on
            # permute vars. (Note this does handle any recursive references properly)
            basic_per_vars = [var for var_set, var in used_per_vars if var_set == 'var']
            try:
                resolved, _ = base_var_man.resolve_references(partial=True,
                                                              skip_deps=basic_per_vars)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (progressive).", err)

            # Convert to the same format as our per_vars
            resolved = [('var', var) for var in resolved]

            # Variables to permute on this iteration.
            permute_now = []
            for var_set, var in used_per_vars.copy():
                if var_set not in ('sched', 'var') or (var_set, var) in resolved:
                    permute_now.append((var_set, var))
                    used_per_vars.remove((var_set, var))

            # We've done all we can without resolving scheduler variables.
            if not permute_now:
                break

            new_var_men = []
            for var_man in var_men:
                new_var_men.extend(var_man.get_permutations(permute_now))
            var_men = new_var_men

        # Calculate permutations for variables that we 'could resolve' if not for the fact
        # that they are permutation variables. These are variables that refer to themselves
        # (either directly (a.b->a.c) or indirectly (a.b -> d -> a.c).
        all_var_men = []
        for var_man in var_men:
            basic_per_vars = [var for var_set, var in used_per_vars if var_set == 'var']
            try:
                _, could_resolve = var_man.resolve_references(partial=True,
                                                              skip_deps=basic_per_vars)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (post-prog).", err)

            # Resolve permutations only for those 'could_resolve' variables that
            # we actually permute over.
            all_var_men.extend(var_man.get_permutations(
                [('var', var_name) for var_name in could_resolve
                 if var_name in could_resolve]))
        var_men = all_var_men

        # Everything left at this point will require the sched vars to deal with.
        all_var_men = []
        for var_man in var_men:
            try:
                var_man.resolve_references(partial=True)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (pre-sched).", err)

            sched_cfg = test_cfg.get('schedule', {})
            try:
                sched_cfg = resolve.test_config(sched_cfg, var_man)
            except KeyError as err:
                raise TestConfigError(
                    "Failed to resolve the scheduler config due to a missing or "
                    "unresolved variable for test {}".format(test_name), err)

            try:
                sched_vars = sched.get_initial_vars(sched_cfg)
            except SchedulerPluginError as err:
                raise TestConfigError(
                    "Error getting initial variables from scheduler {} for test '{}': {} \n\n"
                    "Scheduler Config: \n{}"
                    .format(sched_name, test_name, err.args[0], pprint.pformat(sched_cfg)))

            var_man.add_var_set('sched', sched_vars)
            # Now we can really fully resolve all the variables.
            try:
                var_man.resolve_references()
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (final).", err)

            # And do the rest of the permutations.
            all_var_men.extend(var_man.get_permutations(used_per_vars))

        return test_cfg, all_var_men

    NOT_OVERRIDABLE = ['name', 'suite', 'suite_path', 'scheduler',
                       'base_name', 'host', 'modes']

    def apply_overrides(self, test_cfg, overrides) -> Dict:
        """Apply overrides to this test.

        :param dict test_cfg: The test configuration.
        :param list overrides: A list of raw overrides in a.b.c=value form.
        :raises: (ValueError,KeyError)
    """

        config_loader = TestConfigLoader()

        for ovr in overrides:
            if '=' not in ovr:
                raise ValueError(
                    "Invalid override value. Must be in the form: "
                    "<key>=<value>. Ex. -c run.modules=['gcc'] ")

            key, value = ovr.split('=', 1)
            key = key.strip()
            key = key.split('.')

            self._apply_override(test_cfg, key, value)

        try:
            return config_loader.normalize(test_cfg)
        except TypeError as err:
            raise TestConfigError("Invalid override", err)

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
                raise KeyError("Tried, to override key '{}', but '{}' isn't"
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
            raise ValueError("Invalid value ({}) for key '{}' in overrides"
                             .format(value, disp_key), err)

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
