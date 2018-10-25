from __future__ import division, unicode_literals, print_function
from collections import defaultdict
from pavilion import string_parser, variables
from pavilion.config_format import TestConfigLoader, TestSuiteLoader, TestConfigError, KEY_NAME_RE
import logging
import os

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

def find_config(pav_config, conf_type, conf_name):
    """Search all of the known configuration directories for a config of the given
    type and name.
    :param pav_config:
    :param conf_type:
    :param conf_name:
    :return: The path to the first matching config found, or None if one wasn't found.
    """
    for conf_dir in pav_config.config_dirs:
        path = os.path.join(conf_dir, conf_type, '{}.yaml'.format(conf_name))
        if os.path.exists(path):
            return path

    return None


def get_tests(pav_config, host, modes, tests):
    """Get a dictionary of the test configs given a host, list of modes,
    and a list of tests.
    :param pav_config:
    :param Union(str, None) host:
    :param list modes: A list (possibly empty) of modes to layer onto the test.
    :param list tests: A list (possibly empty) of tests to load. Each test can be either a
                       '<test_suite>.<test_name>', '<test_suite>', or '<test_suite>.*'. A test
                       suite by itself (or with a .*) get every test in a suite.
    :return: A mapping of '<test_suite>.<test_name>' -> raw_test_cfg
    """

    test_config_loader = TestConfigLoader()

    if host is None:
        # Use the defaults if a host config isn't given.
        base_config = test_config_loader.load_empty()
    else:
        host_cfg_path = find_config(pav_config, CONF_HOST, host)
        if host_cfg_path is None:
            raise TestConfigError("Could not find {} config file for {}.".format(CONF_HOST, host))

        try:
            with open(host_cfg_path) as host_cfg_file:
                # Load and validate the host test config defaults.
                base_config = test_config_loader.load(host_cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open host config '{}': {}".format(host_cfg_path, err))

    for mode in modes:
        mode_cfg_path = find_config(pav_config, CONF_MODE, mode)

        if mode_cfg_path is None:
            raise TestConfigError("Could not find {} config file for {}.".format(CONF_MODE, mode))

        try:
            with open(mode_cfg_path) as mode_cfg_file:
                # Load this mode_config and merge it into the base_config.
                base_config = test_config_loader.load_merge(base_config, mode_cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open mode config '{}': {}".format(mode_cfg_path, err))

    # A dictionary of test suites to a list of subtests to run in that suite.
    all_tests = defaultdict(lambda: dict())
    picked_tests = dict()
    test_suite_loader = TestSuiteLoader()

    # Find and load all of the requested tests.
    for test_name in tests:
        # Make sure the test name has the right number of parts.
        # They should look like '<test_suite>.<subtest>', '<test_suite>.*' or just '<test_suite>'
        name_parts = test_name.split('.')
        if len(name_parts) == 0 or name_parts[0] == '':
            raise TestConfigError("Empty test name given.")
        elif len(name_parts) > 2:
            raise TestConfigError("Test names can be a general test suite, or a test suite followed"
                                  "by a specific test. Eg: 'supermagic' or 'supermagic.fs_tests'")

        # Divide the test name into it's parts.
        if len(name_parts == 2):
            test_suite, requested_test = name_parts
        else:
            test_suite = name_parts[0]
            requested_test = '*'

        # Make sure our test suite and subtest names are sane.
        if KEY_NAME_RE.match(test_suite) is None:
            raise TestConfigError("Invalid test suite name: '{}'".format(test_suite))
        if requested_test != '*' and KEY_NAME_RE.match(requested_test) is None:
            raise TestConfigError("Invalid subtest for requested test: '{}'".format(test_name))

        # Only load each test suite's tests once.
        if test_suite not in all_tests:
            test_suite_path = find_config(pav_config, CONF_TEST, test_suite)

            if test_suite_path is None:
                raise TestConfigError("Could not find test suite {}. Looked in these locations: {}"
                                      .format(test_suite, pav_config.config_dirs))

            try:
                with open(test_suite_path) as test_suite_file:
                    test_suite_cfg = test_suite_loader.load(test_suite_file)

            except (IOError, OSError) as err:
                raise TestConfigError("Could not open test suite config {}: {}"
                                      .format(test_suite_path, err))

            # Organize tests into an inheritance tree.
            depended_on_by = defaultdict(lambda: list())
            # All the tests for this suite.
            suite_tests = {}
            # Tests that haven't been processed whose dependencies are resolved.
            dep_resolved = []
            for test_cfg_name, test_cfg in test_suite_cfg.items():
                if test_cfg.get('inherits_from') is None:
                    test_cfg.inherits_from = '__base__'
                    dep_resolved.append(test_cfg_name)
                else:
                    depended_on_by[test_cfg.inherits_from].append(test_cfg)

                suite_tests[test_cfg_name] = test_cfg

            suite_tests['__base__'] = base_config

            # Resolve all the dependencies
            while dep_resolved:
                test_cfg_name = dep_resolved.pop(0)
                test_cfg = suite_tests[test_cfg_name]
                parent = suite_tests[test_cfg.inherits_from]

                suite_tests[test_cfg_name] = test_config_loader.merge(parent, test_cfg)

                dep_resolved.append(depended_on_by.get(test_cfg_name, []))
                del depended_on_by[test_cfg_name]

            if depended_on_by:
                raise TestConfigError("Tests in suite '{}' have dependencies on '{}' that "
                                      "could not be resolved."
                                      .format(test_suite_path, depended_on_by.keys()))

            # Add some basic information to each test config.
            for test_cfg_name, test_cfg in suite_tests:
                test_cfg['name'] = test_suite_cfg
                test_cfg['suite'] = test_suite
                test_cfg['suite_path'] = test_suite_path

            all_tests[test_suite] = suite_tests

        if requested_test == '*':
            # Get all the tests in the given test suite.
            for test_cfg_name, test_cfg in all_tests[test_suite].items():
                picked_tests['{}.{}'.format(test_suite, test_cfg_name)] = test_cfg

        else:
            # Get the one specified test.
            if requested_test not in all_tests[test_suite]:
                raise TestConfigError("Test suite '{}' does not contain a test '{}'."
                                      .format(test_suite, requested_test))

            picked_tests[test_name] = all_tests[test_suite][requested_test]

    return picked_tests


def get_all_tests(pav_config):
    """Find all the tests within known config directories.
    :param pav_config:
    :return:
    """


class TestConfigurator(object):
    """
    """

    def __init__(self, test_cfg, pav_vars, sys_vars, sched_vars):
        """Create a new TestConfig object.
        :param dict test_cfg: The raw test configuration.
        :param dict pav_vars: The pavilion provided variables.
        :param dict sys_vars: The system provided variables.
        :param dict sched_vars: A
        """

        self._logger = logging.getLogger('pav.' + self.__class__.__name__)

        self.suite = test_cfg['suite']
        self.name = test_cfg['name']
        self._suite_path = test_cfg['suite_path']
        self.subtitle = test_cfg.get('subtitle')
        self.scheduler = test_cfg.get('scheduler')

        # Add the permutation and regular variables to the variable set, then remove them from
        # our config, as they're tracked separately.
        self._var_man = variables.VariableSetManager()
        if 'permutations' in test_cfg:
            self._var_man.add_var_set('per', test_cfg['permutations'])
        del test_cfg['permutations']

        if 'variables' in test_cfg:
            self._var_man.add_var_set('var', test_cfg['variables'])
        del test_cfg['variables']

        self._var_man.add_var_set('sys', sys_vars)
        self._var_man.add_var_set('pav', pav_vars)
        self._var_man.add_var_set('sched', sched_vars)

        # Parse all the strings in the config.
        self._config = self._parse_strings(test_cfg)

        # Get all the used permutaiton vars for this config set.
        self._used_per_vars = self._get_used_per_vars(self._config)

    def _parse_strings(self, section):
        """Parse all non-key strings in the given config section, and replace them with a PavString
        object. This involves recursively walking any data-structures in the given section.
        :param section: The config section to process.
        :return: The original dict with the non-key strings replaced.
        """

        if isinstance(section, dict):
            for key in section.keys():
                section[key] = self._parse_strings(section[key])
            return section
        elif isinstance(section, list):
            for i in range(len(section)):
                section[i] = self._parse_strings(section[i])
            return section
        elif isinstance(section, unicode):
            try:
                return string_parser.parse(section)
            except (string_parser.ScanError, string_parser.ParseError) as err:
                raise TestConfigError("Bad string in '{}' test '{}': {}"
                                      .format(self._suite_path, self.name, err))
        else:
            raise TestConfigError("Invalid value type in suite at '{}' test config '{}'. Type '{}'"
                                  "of value '{}'.".format(self._suite_path, self.name,
                                                          type(section), section))

    def _get_used_per_vars(self, section):
        """Recursively get all the variables used by this test config, in canonical form."""

        used_per_vars = set()

        if isinstance(section, dict):
            for key in section.keys():
                used_per_vars = used_per_vars.union(self._get_used_per_vars(section[key]))

        elif isinstance(section, list):
            for i in range(len(section)):
                used_per_vars = used_per_vars.union(self._get_used_per_vars(section[i]))

        elif isinstance(section, string_parser.PavString):
            for var in section.variables:
                var_set, var, idx, sub = self._var_man.resolve_key(var)

                if var_set == 'per':
                    if idx is not None:
                        raise TestConfigError("In suite '{}', test '{}', permutation variable "
                                              "reference '{}' includes index."
                                              .format(self._suite_path, self.name, var))

                    used_per_vars.add(var)
        else:
            raise TestConfigError("Invalid value type in suite at '{}' test config '{}'. Type '{}'"
                                  "of value '{}'.".format(self._suite_path, self.name,
                                                          type(section), section))

        return used_per_vars

    @classmethod
    def resolve(cls, component, var_man):
        """Recursively resolve the given config component, using the given variable manager.
        :param component: The config component to resolve.
        :param var_man: A variable manager. (Presumably a permutation of the base var_man)
        :return: The component, resolved.
        """

        if isinstance(component, dict):
            resolved_dict = {}
            for key in component.keys():
                resolved_dict[key] = cls.resolve(component[key], var_man)
            return resolved_dict

        elif isinstance(component, list):
            resolved_list = []
            for i in range(len(component)):
                resolved_list.append(cls.resolve(component[i], var_man))
            return resolved_list

        elif isinstance(component, string_parser.PavString):
            return component.resolve(var_man)
        else:
            raise TestConfigError("Invalid value type ('{}') when resolving strings in suite '{}', "
                                  "test '{}'.".format(type(component), self._suite_path, self.name))

    def flatten(self):
        """Resolve permutation variables, turning this TestConfig into a list of TestConfigs.
        :returns: A list of TestConfigs
        """

        return self._var_man.get_permutations(self._get_used_per_vars(self._config))
