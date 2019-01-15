from collections import defaultdict
from pavilion import string_parser, variables
from pavilion.config_format import TestConfigLoader, TestSuiteLoader, TestConfigError, KEY_NAME_RE
import logging
import os

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)


def find_config(pav_config, conf_type, conf_name):
    """Search all of the known configuration directories for a config of the given
    type and name.
    :param pav_config: The pavilion config data.
    :param unicode conf_type: 'host', 'mode', or 'test'
    :param conf_name: The name of the config (without a file extension).
    :return: The path to the first matching config found, or None if one wasn't found.
    """
    for conf_dir in pav_config.config_dirs:
        path = os.path.join(conf_dir, conf_type, '{}.yaml'.format(conf_name))
        if os.path.exists(path):
            return path

    return None


def get_tests(pav_config, host, modes, tests):
    """Get a dictionary of raw test configs given a host, list of modes,
    and a list of tests. Each of these configs will be lightly modified with a few extra variables
    about their name, suite, and suite_file, as well as guaranteeing that they have 'variables' and
    'permutations' sections.
    :param pav_config: The pavilion config data
    :param Union(str, None) host: The host the test is running on.
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
    picked_tests = []
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
                if 'variables' not in test_cfg:
                    test_cfg['variables'] = dict()
                if 'permutations' not in test_cfg:
                    test_cfg['permutations'] = dict()

            all_tests[test_suite] = suite_tests

        if requested_test == '*':
            # Get all the tests in the given test suite.
            for test_cfg_name, test_cfg in all_tests[test_suite].items():
                picked_tests.append(test_cfg)

        else:
            # Get the one specified test.
            if requested_test not in all_tests[test_suite]:
                raise TestConfigError("Test suite '{}' does not contain a test '{}'."
                                      .format(test_suite, requested_test))

            picked_tests.append(all_tests[test_suite][requested_test])

    return picked_tests


NOT_OVERRIDABLE = ['name', 'suite', 'suite_path']


def apply_overrides(test_cfg, overrides, _first_level=True):
    """Apply overrides to this test.
    :param dict test_cfg: The test configuration.
    :param dict overrides: A dictionary of values to override in all configs. This occurs at the
        highest level, after inheritance is resolved.
    """

    return _apply_overrides(test_cfg, overrides, _first_level=True)


def _apply_overrides(test_cfg, overrides, _first_level=True):
    """Apply overrides recursively."""

    for key in overrides.keys():
        if _first_level and key in NOT_OVERRIDABLE:
            LOGGER.warning("You can't override the '{}' key in a test config.".format(key))
            continue

        if key not in test_cfg:
            test_cfg[key] = overrides[key]
        elif isinstance(test_cfg[key], dict):
            if isinstance(overrides[key], dict):
                _apply_overrides(test_cfg[key], overrides[key])
            else:
                raise TestConfigError("Cannot override a dictionary of values with a "
                                      "non-dictionary. Tried to put {} in key {} valued {}."
                                      .format(overrides[key], key, test_cfg[key]))
        elif isinstance(test_cfg[key], list):
            # We always get lists from overrides as our 'array' type.
            if isinstance(overrides[key], list):
                test_cfg[key] = overrides[key]
            # Put single values in a list.
            elif isinstance(overrides[key], str):
                test_cfg[key] = [overrides[key]]
            else:
                raise TestConfigError("Tried to override list key {} with a {} ({})"
                                      .format(key, type(overrides[key]), overrides[key]))
        elif isinstance(test_cfg[key], str):
            if isinstance(overrides[key], str):
                test_cfg[key] = overrides[key]
            else:
                raise TestConfigError("Tried to override str key {} with a {} ({})"
                                      .format(key, type(overrides[key]), overrides[key]))
        else:
            raise TestConfigError("Configuration contains an element of an unrecognized type. "
                                  "Key: {}, Type: {}.".format(key, type(test_cfg[key])))


        # TODO: Write this function, maybe?
def get_all_tests(pav_config):
    """Find all the tests within known config directories.
    :param dict pav_config:
    :return:
    """


def resolve_permutations(raw_test_cfg, pav_vars, sys_vars):
    """Resolve permutations for all used permutation variables, returning a variable manager for
    each permuted version of the test config. We use this opportunity to populate the variable
    manager with most other variable types as well.
    :param dict raw_test_cfg: The raw test configuration dictionary.
    :param dict pav_vars: The pavilion provided variable set.
    :param dict sys_vars: The system plugin provided variable set.
    :returns: The parsed, modified configuration, and a list of variable set managers,
        one for each permutation. These will already contain all the var, sys, pav,
        and (resolved) permutation (per) variable sets. The 'sched' variable set will have to
        be added later.
    :rtype: (dict, [variables.VariableSetManager])
    :raises TestConfigError: When there are problems with variables or the permutations.
    """

    base_var_man = variables.VariableSetManager()
    try:
        base_var_man.add_var_set('per', raw_test_cfg['permutations'])
    except variables.VariableError as err:
        raise TestConfigError("Error in permutations section: {}".format(err))

    # We don't resolve variables within the variables section, so we remove those parts now.
    del raw_test_cfg['permutations']
    user_vars = raw_test_cfg['variables']
    del raw_test_cfg['variables']

    del raw_test_cfg['variables']
    # Recursively make our configuration a little less raw, recursively parsing all string values
    # into PavString objects.
    test_cfg = _parse_strings(raw_test_cfg)

    # We only want to permute over the permutation variables that are actually used.
    # This also provides a convenient place to catch any problems with how those variables
    # are used.
    try:
        used_per_vars = _get_used_per_vars(raw_test_cfg, base_var_man)
    except RuntimeError as err:
        raise TestConfigError("In suite file '{}' test name '{}': {}"
                              .format(raw_test_cfg['suite'], raw_test_cfg['name'], err))

    # Since per vars are the highest in resolution order, we can make things a bit faster
    # by adding these after we find the used per vars.
    try:
        base_var_man.add_var_set('var', user_vars)
    except variables.VariableError as err:
        raise TestConfigError("Error in variables section: {}".format(err))

    try:
        base_var_man.add_var_set('sys', sys_vars)
    except variables.VariableError as err:
        raise TestConfigError("Error in sys variables: {}".format(err))

    try:
        base_var_man.add_var_set('pav', pav_vars)
    except variables.VariableError as err:
        raise TestConfigError("Error in pav variables: {}".format(err))

    return test_cfg, base_var_man.get_permutations(used_per_vars)


def _parse_strings(section):
    """Parse all non-key strings in the given config section, and replace them with a PavString
    object. This involves recursively walking any data-structures in the given section.
    :param section: The config section to process.
    :return: The original dict with the non-key strings replaced.
    """

    if isinstance(section, dict):
        for key in section.keys():
            section[key] = _parse_strings(section[key])
        return section
    elif isinstance(section, list):
        for i in range(len(section)):
            section[i] = _parse_strings(section[i])
        return section
    elif isinstance(section, str):
        return string_parser.parse(section)
    else:
        # Should probably never happen (We're going to see this error a lot until we get a handle
        # on strings vs unicode though).
        raise RuntimeError("Invalid value type '{}' of value '{}'."
                           .format(type(section), section))


def _get_used_per_vars(component, var_man):
    """Recursively get all the variables used by this test config, in canonical form.
    :param component: A section of the configuration file to look for per vars in.
    :param variables.VariableSetManager: The variable set manager.
    :returns: A list of used 'per' variables names (Just the 'var' component).
    :raises RuntimeError: For invalid sections.
    """

    used_per_vars = set()

    if isinstance(component, dict):
        for key in component.keys():
            try:
                used_per_vars = used_per_vars.union(_get_used_per_vars(component[key], var_man))
            except KeyError:
                pass

    elif isinstance(component, list):
        for i in range(len(component)):
            try:
                used_per_vars = used_per_vars.union(_get_used_per_vars(component[i], var_man))
            except KeyError:
                pass

    elif isinstance(component, string_parser.PavString):
        for var in component.variables:
            var_set, var, idx, sub = var_man.resolve_key(var)

            # Grab just 'per' vars.
            # Also, if per variables are used by index, we just resolve that value normally rather
            # than permuting over it.
            if var_set == 'per' and idx is None:
                used_per_vars.add(var)
    else:
        # This should be unreachable.
        raise RuntimeError("Unknown config component type '{}' of '{}'"
                           .format(type(component), component))

    return used_per_vars


def resolve_all_vars(component, var_man):
    """Recursively resolve the given config component's variables, using a variable manager.
    :param component: The config component to resolve.
    :param var_man: A variable manager. (Presumably a permutation of the base var_man)
    :return: The component, resolved.
    """

    if isinstance(component, dict):
        resolved_dict = {}
        for key in component.keys():
            resolved_dict[key] = resolve_all_vars(component[key], var_man)
        return resolved_dict

    elif isinstance(component, list):
        resolved_list = []
        for i in range(len(component)):
            resolved_list.append(resolve_all_vars(component[i], var_man))
        return resolved_list

    elif isinstance(component, string_parser.PavString):
        return component.resolve(var_man)
    elif isinstance(component, str):
        # Some PavStrings may have already been resolved
        return component
    else:
        raise TestConfigError("Invalid value type '{}' for '{}' when resolving strings."
                              .format(type(component), component))
