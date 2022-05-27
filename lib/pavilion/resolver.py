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
import multiprocessing as mp
import os
import pprint
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List, IO, Dict

import yc_yaml
from pavilion import output, variables
from pavilion import pavilion_variables
from pavilion import resolve
from pavilion import schedulers
from pavilion import sys_vars
from pavilion.errors import VariableError, TestConfigError
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


class ProtoTest:
    """An simple object that holds the pair of a test config and its variable
    manager."""

    def __init__(self, config, var_man):
        self.config = config  # type: dict
        self.var_man = var_man  # type: variables.VariableSetManager


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
        except sys_vars.SystemPluginError as err:
            raise TestConfigError(
                "Error in system variables: {}"
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
            raise TestConfigError("Error in variables section for test '{}': {}"
                                  .format(test_name, err))

        scheduler = raw_test_cfg.get('scheduler', '<undefined>')
        try:
            sched = schedulers.get_plugin(scheduler)
        except schedulers.SchedulerPluginError:
            raise TestConfigError(
                "Could not find scheduler '{}' for test '{}'"
                .format(scheduler, test_name))

        if not sched.available():
            raise TestConfigError(
                "Scheduler '{}' is not available on this system (test {})"
                .format(sched.name, test_name))

        schedule_cfg = raw_test_cfg.get('schedule', {})
        schedule_cfg = resolve.test_vars(schedule_cfg, var_man)

        try:
            sched_vars = sched.get_initial_vars(schedule_cfg)
        except schedulers.SchedulerPluginError as err:
            # Errors should generally be deferred here, but just in case.
            raise TestConfigError(
                "Error getting initial variables from scheduler {} for test '{}': {} \n\n"
                "Scheduler Config: \n{}"
                .format(scheduler, test_name, err.args[0], pprint.pformat(schedule_cfg)))

        var_man.add_var_set('sched', sched_vars)

        return var_man

    def check_required_variables(self, raw_tests: List[Dict]):
        """Check all of the variables defined as defaults with a null value to
        make sure they were actually defined."""

        for config in raw_tests:
            # This should be a VarCatElem, which has a built-in defaults dict.
            defaults: Dict = config['variables'].defaults
            vars = config['variables']
            for key, def_val in defaults.items():
                if def_val is None and key not in vars or vars[key] is None:
                    raise TestConfigError(
                        "In test '{}', variable '{}' is required but was never set."
                        .format(config['name'], key))
                elif isinstance(def_val, dict):
                    # Check all the sub-value defaults for required values.
                    for skey, sdef_val in def_val.items():
                        # There's another potential case here where the base
                        # variable doesn't exist. That shouldn't actually be possible,
                        # as if nothing is defined the defaults are set as the value.
                        if sdef_val is None and skey not in config['variables'].get(key, {}):
                            raise TestConfigError(
                                "In test '{}', variable '{}.{}' is required, but was not set"
                                .format(config['name'], key, skey))

    def find_config(self, conf_type, conf_name) -> (str, Path):
        """Search all of the known configuration directories for a config of the
        given type and name.

        :param str conf_type: 'host', 'mode', or 'test'
        :param str conf_name: The name of the config (without a file extension).
        :return: A tuple of the config label under which a matching config was found
            and the path to that config. If nothing was found, returns (None, None).
        """
        for label, config in self.pav_cfg.configs.items():
            path = config['path']/conf_type/'{}.yaml'.format(conf_name)
            if path.exists():
                return label, path

        return None, None

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
                        suite_path=file
                    )
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

        raw_tests = self.load_raw_configs(tests, host, modes)

        # apply series-defined conditions
        if conditions:
            for raw_test in raw_tests:
                raw_test['only_if'] = union_dictionary(
                    raw_test['only_if'], conditions['only_if']
                )
                raw_test['not_if'] = union_dictionary(
                    raw_test['not_if'], conditions['not_if']
                )

        resolved_tests = []

        for raw_test in raw_tests:
            # Apply the overrides to each of the config values.
            try:
                self.apply_overrides(raw_test, overrides)
            except (KeyError, ValueError) as err:
                msg = 'Error applying overrides to test {} from {}: {}' \
                    .format(raw_test['name'], raw_test['suite_path'], err)
                raise TestConfigError(msg)

        self.check_required_variables(raw_tests)

        complete = 0

        if len(raw_tests) == 0:
            return []
        elif len(raw_tests) == 1:
            base_var_man = self.build_variable_manager(raw_tests[0])
            return self.resolve(raw_tests[0], base_var_man)
        else:
            async_results = []
            proc_count = min(self.pav_cfg['max_cpu'], len(raw_tests))
            with mp.Pool(processes=proc_count) as pool:
                for raw_test in raw_tests:
                    base_var_man = self.build_variable_manager(raw_test)
                    async_results.append(
                        pool.apply_async(self.resolve, (raw_test, base_var_man))
                    )

                while async_results:
                    for aresult in list(async_results):
                        if aresult.ready():
                            async_results.remove(aresult)

                            resolved_tests.extend(aresult.get())

                            complete += 1
                            progress = len(raw_tests) - complete
                            progress = (1 - progress/len(raw_tests))
                            output.fprint(outfile,
                                          "Resolving Test Configs: {:.0%}".format(progress),
                                          end='\r')

                    try:
                        aresult.wait(0.5)
                    except TimeoutError:
                        pass

        if outfile:
            output.fprint(outfile, '')

        # NOTE: The deferred scheduler errors will be handled when we try to save
        #       the test object. (See build_variable_manager() above)

        return resolved_tests

    def resolve(self, test_cfg: dict, base_var_man: variables.VariableSetManager):
        """Resolve one test config, and apply the given overrides."""

        resolved_tests = []

        # A list of tuples of test configs and their permuted var_man
        permuted_tests = []  # type: (dict, variables.VariableSetManager)

        sched_errors = base_var_man.get('sched.errors')

        # Resolve all configuration permutations.
        try:
            p_cfg, permutes = self.resolve_permutations(
                test_cfg,
                base_var_man=base_var_man
            )
            for p_var_man in permutes:
                # Get the scheduler from the config.
                permuted_tests.append((p_cfg, p_var_man))

        except TestConfigError as err:
            msg = 'Error resolving permutations for test {} from {}: {}' \
                .format(test_cfg['name'], test_cfg['suite_path'], err)

            if sched_errors is not None:
                msg += "\nScheduler errors also happened, which may be the root " \
                       "cause:\n{}".format(sched_errors)

            raise TestConfigError(msg)

        # Set the scheduler variables for each test.
        for ptest_cfg, pvar_man in permuted_tests:
            # Resolve all variables for the test (that aren't deferred).
            try:
                resolved_config = resolve.test_vars(ptest_cfg, pvar_man)
            except TestConfigError as err:
                msg = ('In test {} from {}:\n{}'
                       .format(test_cfg['name'], test_cfg['suite_path'],
                               err.args[0]))

                if sched_errors is not None:
                    msg += "\nScheduler errors also happened, which may be the root " \
                           "cause:\n{}".format(sched_errors)

                raise TestConfigError(msg)

            resolved_tests.append(ProtoTest(resolved_config, pvar_man))

        return resolved_tests

    def load_raw_configs(self, tests, host, modes):
        """Get a list of raw test configs given a host, list of modes,
        and a list of tests. Each of these configs will be lightly modified with
        a few extra variables about their name, suite, and suite_file, as well
        as guaranteeing that they have 'variables' and 'permutations' sections.

        :param list tests: A list (possibly empty) of tests to load. Each test
            can be either a '<test_suite>.<test_name>', '<test_suite>',
            or '<test_suite>.*'. A test suite by itself (or with a .*) get every
            test in a suite.
        :param Union(str, None) host: The host the test is running on.
        :param list modes: A list (possibly empty) of modes to layer onto the
            test.
        :rtype: list(dict)
        :return: A list of raw test_cfg dictionaries.
        """

        test_config_loader = TestConfigLoader()

        base_config = test_config_loader.load_empty()

        base_config = self.apply_host(base_config, host)

        # A dictionary of test suites to a list of subtests to run in that
        # suite.
        all_tests = defaultdict(dict)
        picked_tests = []
        test_suite_loader = TestSuiteLoader()

        total_tests = []
        # Make sue we get the correct amount of tests
        for test_name in tests:
            # Make sure the test name has the right number of parts.
            # They should look like '<test_suite>.<subtest>', '<test_suite>.*'
            # or just '<test_suite>'

            name_parts = test_name.split('.')
            if len(name_parts) == 0 or name_parts[0] == '':
                continue
            elif len(name_parts) > 2:
                raise TestConfigError(
                    "Test names can be a general test suite, or a test suite "
                    "followed by a specific test. Eg: 'supermagic' or "
                    "'supermagic.fs_tests'")

            # Divide the test name into it's parts.
            if len(name_parts) == 2:
                test_suite, requested_test = name_parts
                if requested_test == '*':
                    raise TestConfigError(
                        "Invalid subtest for requested test: '*'\n"
                        "<suite_name>.* is no longer support, use 'pav "
                        "run <suite_name>' instead."
                    )
                try:
                    if '*' in test_suite:
                        count, test_suite = test_suite.split("*")
                        total_tests.extend([test_suite+"."+requested_test]*int(count))
                        continue

                    if '*' in requested_test:
                        test, count = requested_test.split("*")
                        total_tests.extend([test_suite+"."+test]*int(count))
                        continue
                except ValueError as err:
                    raise TestConfigError("Invalid repeat notation: {}"
                                          .format(err))
                total_tests.append(test_name)

            else:
                test_suite = name_parts[0]
                if "*" in test_suite:
                    left, right = test_suite.split("*")
                    try:
                        if left.isdigit():
                            total_tests.extend([right] * int(left))
                            continue
                        elif right.isdigit():
                            total_tests.extend([left] * int(right))
                            continue
                        else:
                            raise ValueError("No digit present in {}"
                                             .format([left, right]))
                    except ValueError as err:
                        raise TestConfigError("Invalid repeat notation: {}"
                                              .format(err))
                else:
                    total_tests.append(test_suite)

        # Find and load all of the requested tests.
        for test_name in total_tests:
            name_parts = test_name.split('.')
            if len(name_parts) == 2:
                test_suite, requested_test = name_parts
            else:
                test_suite = name_parts[0]
                requested_test = "*"

            # Make sure our test suite and subtest names are sane.
            if KEY_NAME_RE.match(test_suite) is None:
                raise TestConfigError("Invalid test suite name: '{}'"
                                      .format(test_suite))
            if (requested_test != '*' and
                    TEST_NAME_RE.match(requested_test) is None):
                raise TestConfigError("Invalid subtest for requested test: '{}'"
                                      .format(test_name))

            # Only load each test suite's tests once.
            if test_suite not in all_tests:
                cfg_label, test_suite_path = self.find_config(CONF_TEST, test_suite)

                if test_suite_path is None:
                    if test_suite == 'log':
                        raise TestConfigError(
                            "Could not find test suite 'log'. If you were "
                            "trying to get the run log, use the 'pav log run "
                            "<testid>' command.")

                    cdirs = [str(cfg['path']) for cfg in self.pav_cfg.configs.values()]
                    raise TestConfigError(
                        "Could not find test suite {}. Looked in these "
                        "locations: {}"
                        .format(test_suite, cdirs))

                try:
                    with test_suite_path.open() as test_suite_file:
                        # We're loading this in raw mode, because the defaults
                        # will have already been provided.
                        # Each test config will be individually validated later.
                        test_suite_cfg = test_suite_loader.load_raw(
                            test_suite_file)

                except (IOError, OSError, ) as err:
                    raise TestConfigError(
                        "Could not open test suite config {}: {}"
                        .format(test_suite_path, err))
                except ValueError as err:
                    raise TestConfigError(
                        "Test suite '{}' has invalid value. {}"
                        .format(test_suite_path, err))
                except KeyError as err:
                    raise TestConfigError(
                        "Test suite '{}' has an invalid key. {}"
                        .format(test_suite_path, err))
                except yc_yaml.YAMLError as err:
                    raise TestConfigError(
                        "Test suite '{}' has a YAML Error: {}"
                        .format(test_suite_path, err)
                    )
                except TypeError as err:
                    # All config elements in test configs must be strings,
                    # and just about everything converts cleanly to a string.
                    raise RuntimeError(
                        "Test suite '{}' raised a type error, but that "
                        "should never happen. {}".format(test_suite_path, err))

                suite_tests = self.resolve_inheritance(
                    base_config,
                    test_suite_cfg,
                    test_suite_path
                )

                # Add some basic information to each test config.
                for test_cfg_name, test_cfg in suite_tests.items():
                    test_cfg['name'] = test_cfg_name
                    test_cfg['cfg_label'] = cfg_label
                    working_dir = self.pav_cfg['configs'][cfg_label]['working_dir']
                    test_cfg['working_dir'] = working_dir.as_posix()
                    test_cfg['suite'] = test_suite
                    test_cfg['suite_path'] = str(test_suite_path)
                    test_cfg['host'] = host
                    test_cfg['modes'] = modes

                all_tests[test_suite] = suite_tests

            # Now that we know we've loaded and resolved a given suite,
            # get the relevant tests from it.
            if requested_test == '*':
                # All tests were requested.
                for test_cfg_name, test_cfg in all_tests[test_suite].items():
                    if not test_cfg_name.startswith('_'):
                        picked_tests.append(test_cfg)

            else:
                # Get the one specified test.
                if requested_test not in all_tests[test_suite]:
                    raise TestConfigError(
                        "Test suite '{}' does not contain a test '{}'."
                        .format(test_suite, requested_test))

                picked_tests.append(all_tests[test_suite][requested_test])

        picked_tests = [
            self.apply_modes(test_cfg, modes)
            for test_cfg in picked_tests]

        # Add the pav_cfg default_result configuration items to each test.
        for test_cfg in picked_tests:
            result_evals = test_cfg['result_evaluate']

            for key, const in self.pav_cfg.default_results.items():
                if key in result_evals:
                    # Don't override any that are already there.
                    continue

                test_cfg['result_evaluate'][key] = '"{}"'.format(const)

        return picked_tests

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

        test_config_loader = TestConfigLoader()

        if host is not None:
            _, host_cfg_path = self.find_config(CONF_HOST, host)

            if host_cfg_path is not None:
                try:
                    with host_cfg_path.open() as host_cfg_file:
                        # Load the host test config defaults.
                        test_cfg = test_config_loader.load_merge(
                            test_cfg,
                            host_cfg_file,
                            partial=True)
                except (IOError, OSError) as err:
                    raise TestConfigError("Could not open host config '{}': {}"
                                          .format(host_cfg_path, err))
                except ValueError as err:
                    raise TestConfigError(
                        "Host config '{}' has invalid value. {}"
                        .format(host_cfg_path, err))
                except KeyError as err:
                    raise TestConfigError(
                        "Host config '{}' has an invalid key. {}"
                        .format(host_cfg_path, err))
                except yc_yaml.YAMLError as err:
                    raise TestConfigError(
                        "Host config '{}' has a YAML Error: {}"
                        .format(host_cfg_path, err)
                    )
                except TypeError as err:
                    # All config elements in test configs must be strings,
                    # and just about everything converts cleanly to a string.
                    raise RuntimeError(
                        "Host config '{}' raised a type error, but that "
                        "should never happen. {}".format(host_cfg_path, err))

            test_cfg = resolve.cmd_inheritance(test_cfg)

        return test_cfg

    def apply_modes(self, test_cfg, modes):
        """Apply each of the mode files to the given test config.
        :param dict test_cfg: A raw test configuration.
        :param list modes: A list of mode names.
        """

        test_config_loader = TestConfigLoader()

        for mode in modes:
            _, mode_cfg_path = self.find_config(CONF_MODE, mode)

            if mode_cfg_path is None:
                raise TestConfigError(
                    "Could not find {} config file for {}."
                    .format(CONF_MODE, mode))

            try:
                with mode_cfg_path.open() as mode_cfg_file:
                    # Load this mode_config and merge it into the base_config.
                    test_cfg = test_config_loader.load_merge(test_cfg,
                                                             mode_cfg_file,
                                                             partial=True)
            except (IOError, OSError) as err:
                raise TestConfigError("Could not open mode config '{}': {}"
                                      .format(mode_cfg_path, err))
            except ValueError as err:
                raise TestConfigError(
                    "Mode config '{}' has invalid value. {}"
                    .format(mode_cfg_path, err))
            except KeyError as err:
                raise TestConfigError(
                    "Mode config '{}' has an invalid key. {}"
                    .format(mode_cfg_path, err))
            except yc_yaml.YAMLError as err:
                raise TestConfigError(
                    "Mode config '{}' has a YAML Error: {}"
                    .format(mode_cfg_path, err)
                )
            except TypeError as err:
                # All config elements in test configs must be strings, and just
                # about everything converts cleanly to a string.
                raise RuntimeError(
                    "Mode config '{}' raised a type error, but that "
                    "should never happen. {}".format(mode_cfg_path, err))

            test_cfg = resolve.cmd_inheritance(test_cfg)

        return test_cfg

    def resolve_inheritance(self, base_config, suite_cfg, suite_path):
        """Resolve inheritance between tests in a test suite. There's potential
        for loops in the inheritance hierarchy, so we have to be careful of
        that.

        :param base_config: Forms the 'defaults' for each test.
        :param suite_cfg: The suite configuration, loaded from a suite file.
        :param suite_path: The path to the suite file.
        :return: A dictionary of test configs.
        :rtype: dict(str,dict)
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
                    depended_on_by[test_cfg['inherits_from']]\
                        .append(test_cfg_name)

                try:
                    suite_tests[test_cfg_name] = TestConfigLoader()\
                        .normalize(test_cfg)
                except (TypeError, KeyError, ValueError) as err:
                    raise TestConfigError(
                        "Test {} in suite {} has an error:\n{}"
                        .format(test_cfg_name, suite_path, err))
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
            suite_tests[test_cfg_name] = test_config_loader.merge(parent,
                                                                  test_cfg)

            suite_tests[test_cfg_name] = resolve.cmd_inheritance(suite_tests[test_cfg_name])
            tcfg = suite_tests[test_cfg_name]

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
            # Validation hoses these. We need to restore them afterwords
            variable_defaults = test_config['variables'].defaults
            try:
                suite_tests[test_name] = test_config_loader\
                                            .validate(test_config)
            except RequiredError as err:
                raise TestConfigError(
                    "Test {} in suite {} has a missing key. {}"
                    .format(test_name, suite_path, err))
            except ValueError as err:
                raise TestConfigError(
                    "Test {} in suite {} has an invalid value. {}"
                    .format(test_name, suite_path, err))
            except KeyError as err:
                raise TestConfigError(
                    "Test {} in suite {} has an invalid key. {}"
                    .format(test_name, suite_path, err))
            except yc_yaml.YAMLError as err:
                raise TestConfigError(
                    "Test {} in suite {} has a YAML Error: {}"
                    .format(test_name, suite_path, err)
                )
            except TypeError as err:
                # See the same error above when loading host configs.
                raise RuntimeError(
                    "Loaded test '{}' in suite '{}' raised a type error, "
                    "but that should never happen. {}"
                    .format(test_name, suite_path, err))

            suite_tests[test_name]['variables'].defaults = variable_defaults

            try:
                self.check_version_compatibility(test_config)
            except TestConfigError as err:
                raise TestConfigError(
                    "Test '{}' in suite '{}' has incompatibility issues:\n{}"
                    .format(test_name, suite_path, err))

        return suite_tests

    def resolve_permutations(self, test_cfg, base_var_man):
        """Resolve permutations for all used permutation variables, returning a
        variable manager for each permuted version of the test config. We use
        this opportunity to populate the variable manager with most other
        variable types as well.

        :param dict test_cfg: The raw test configuration dictionary.
        :param variables.VariableSetManager base_var_man: The variables for
            this config (absent the scheduler variables).
        :returns: The modified configuration, and a list of variable set
            managers, one for each permutation.
        :rtype: (dict, [variables.VariableSetManager])
        :raises TestConfigError: When there are problems with variables or the
            permutations.
        """

        _ = self

        permute_on = test_cfg['permute_on']
        test_cfg['permute_base'] = uuid.uuid4().hex

        used_per_vars = set()
        for per_var in permute_on:
            try:
                var_set, var, index, subvar = base_var_man.resolve_key(per_var)
            except KeyError:
                raise TestConfigError(
                    "Permutation variable '{}' is not defined."
                    .format(per_var))
            if index is not None or subvar is not None:
                raise TestConfigError(
                    "Permutation variable '{}' contains index or subvar. "
                    "When giving a permutation variable only the variable name "
                    "and variable set (optional) are allowed. Ex: 'sys.foo' "
                    " or just 'foo'."
                    .format(per_var))
            elif base_var_man.any_deferred(per_var):

                raise TestConfigError(
                    "Permutation variable '{}' references a deferred variable "
                    "or one with deferred components."
                    .format(per_var))
            used_per_vars.add((var_set, var))

        if permute_on and test_cfg.get('subtitle', None) is None:
            subtitle = []
            var_dict = base_var_man.as_dict()
            for per_var in permute_on:
                var_set, var, index, subvar = base_var_man.resolve_key(per_var)
                if isinstance(var_dict[var_set][var][0], dict):
                    subtitle.append('_' + var + '_')
                else:
                    subtitle.append('{{' + per_var + '}}')

            subtitle = '-'.join(subtitle)

            test_cfg['subtitle'] = subtitle

        # var_men is a list of variable managers, one for each permutation
        var_men = base_var_man.get_permutations(list(used_per_vars))
        for var_man in var_men:
            try:
                var_man.resolve_references()
            except (KeyError, ValueError, VariableError) as err:
                raise TestConfigError(
                    "Error resolving vars in permuted test '{}':\n{}"
                    .format(test_cfg.get('name', '<no name>'), err))
        return test_cfg, var_men

    NOT_OVERRIDABLE = ['name', 'suite', 'suite_path', 'scheduler',
                       'base_name', 'host', 'modes']

    def apply_overrides(self, test_cfg, overrides):
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
            test_cfg = config_loader.normalize(test_cfg)
        except TypeError as err:
            raise TestConfigError("Invalid override: {}"
                                  .format(err))
        config_loader.validate(test_cfg)

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
            raise ValueError("Invalid value ({}) for key '{}' in overrides: {}"
                             .format(value, disp_key, err))

        last_cfg[last_key] = self.normalize_override_value(value)

    def normalize_override_value(self, value):
        """Normalize a value to one compatible with Pavilion configs. It can
        be any structure of dicts and lists, as long as the leaf values are
        strings.

        :param value: The value to normalize.
        :returns: A string or a structure of dicts/lists whose leaves are
            strings.
        """
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float, bool, bytes)):
            return str(value)
        elif isinstance(value, (list, tuple)):
            return [self.normalize_override_value(v) for v in value]
        elif isinstance(value, dict):
            return {str(k): self.normalize_override_value(v)
                    for k, v in value.items()}
        else:
            raise ValueError("Invalid type in override value: {}".format(value))
