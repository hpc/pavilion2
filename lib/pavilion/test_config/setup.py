import copy
import logging
import os
from collections import defaultdict

from yaml_config import RequiredError
from . import string_parser
from . import variables
from .format import TestConfigError, KEY_NAME_RE
from .format import TestConfigLoader, TestSuiteLoader

from pavilion.utils import dbg_print

# Config file types
CONF_HOST = 'hosts'
CONF_MODE = 'modes'
CONF_TEST = 'tests'

LOGGER = logging.getLogger('pav.' + __name__)


def _find_config(pav_cfg, conf_type, conf_name):
    """Search all of the known configuration directories for a config of the
    given type and name.
    :param pav_cfg: The pavilion config data.
    :param str conf_type: 'host', 'mode', or 'test'
    :param str conf_name: The name of the config (without a file extension).
    :return: The path to the first matching config found, or None if one wasn't
    found.
    """
    for conf_dir in pav_cfg.config_dirs:
        path = conf_dir/conf_type/'{}.yaml'.format(conf_name)
        if path.exists():
            return path

    return None


def find_all_tests(pav_cfg):
    """Find all the tests within known config directories.
    :param pav_cfg: The pavilion configuration.
    :return: Returns a data structure that looks like:
        suite_name -> {
            'path': Path to the suite file.
            'err': Error loading suite file.
            'supersedes': [superseded_suite_files]
            'tests': name -> {
                    'conf': The full test config (inheritance resolved),
                    'summary': Test summary string,
                    'doc': Test doc string,
            }
    """

    suites = {}

    for conf_dir in pav_cfg.config_dirs:
        path = conf_dir/'tests'

        if not (path.exists() and path.is_dir()):
            continue

        for file in os.listdir(path.as_posix()):

            file = path/file
            if file.suffix == '.yaml' and file.is_file():
                # It's ok if the tests aren't completely validated. They
                # may have been written to require a real host/mode file.
                with file.open('r') as suite_file:
                    try:
                        suite_cfg = TestSuiteLoader().load(suite_file,
                                                           partial=True)
                    except (TypeError, KeyError, ValueError) as err:
                        suites[suite_name]['err'] = err
                        continue
                suite_name = file.stem

                if suite_name not in suites:
                    suites[suite_name] = {
                        'path': file,
                        'err': '',
                        'tests': {},
                        'supersedes': [],
                    }
                else:
                    suites[suite_name]['supersedes'].append(file)

                base = TestConfigLoader().load_empty()

                try:
                    suite_cfgs = resolve_inheritance(
                        base_config=base,
                        suite_cfg=suite_cfg,
                        suite_path=file
                    )
                except Exception as err:
                    suites[suite_name]['err'] = err
                    continue

                for test_name, conf in suite_cfgs.items():
                    suites[suite_name]['tests'][test_name] = {
                        'conf': conf,
                        'summary': conf['summary'],
                        'doc': conf['doc'],
                    }

    return suites


def load_test_configs(pav_cfg, host, modes, tests):
    """Get a dictionary of raw test configs given a host, list of modes,
    and a list of tests. Each of these configs will be lightly modified with
    a few extra variables about their name, suite, and suite_file, as well as
    guaranteeing that they have 'variables' and 'permutations' sections.
    :param pav_cfg: The pavilion config data
    :param Union(str, None) host: The host the test is running on.
    :param list modes: A list (possibly empty) of modes to layer onto the test.
    :param list tests: A list (possibly empty) of tests to load. Each test can
    be either a '<test_suite>.<test_name>', '<test_suite>',
    or '<test_suite>.*'. A test suite by itself (or with a .*) get every
    test in a suite.
    :return: A mapping of '<test_suite>.<test_name>' -> raw_test_cfg
    """

    test_config_loader = TestConfigLoader()

    base_config = test_config_loader.load_empty()

    if host is not None:
        host_cfg_path = _find_config(pav_cfg, CONF_HOST, host)

        if host_cfg_path is not None:

            try:
                with host_cfg_path.open() as host_cfg_file:
                    # Load and validate the host test config defaults.
                    base_config = test_config_loader.load_merge(
                        base_config,
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
            except TypeError as err:
                # All config elements in test configs must be strings, and just
                # about everything converts cleanly to a string.
                raise RuntimeError(
                    "Host config '{}' raised a type error, but that "
                    "should never happen. {}".format(host_cfg_path, err))

    for mode in modes:
        mode_cfg_path = _find_config(pav_cfg, CONF_MODE, mode)

        if mode_cfg_path is None:
            raise TestConfigError("Could not find {} config file for {}."
                                  .format(CONF_MODE, mode))

        try:
            with mode_cfg_path.open() as mode_cfg_file:
                # Load this mode_config and merge it into the base_config.
                base_config = test_config_loader.load_merge(base_config,
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
        except TypeError as err:
            # All config elements in test configs must be strings, and just
            # about everything converts cleanly to a string.
            raise RuntimeError(
                "Mode config '{}' raised a type error, but that "
                "should never happen. {}".format(mode_cfg_path, err))

    # A dictionary of test suites to a list of subtests to run in that suite.
    all_tests = defaultdict(lambda: dict())
    picked_tests = []
    test_suite_loader = TestSuiteLoader()

    # Find and load all of the requested tests.
    for test_name in tests:
        # Make sure the test name has the right number of parts.
        # They should look like '<test_suite>.<subtest>', '<test_suite>.*'
        # or just '<test_suite>'
        name_parts = test_name.split('.')
        if len(name_parts) == 0 or name_parts[0] == '':
            raise TestConfigError("Empty test name given.")
        elif len(name_parts) > 2:
            raise TestConfigError(
                "Test names can be a general test suite, or a test suite "
                "followed by a specific test. Eg: 'supermagic' or "
                "'supermagic.fs_tests'")

        # Divide the test name into it's parts.
        if len(name_parts) == 2:
            test_suite, requested_test = name_parts
        else:
            test_suite = name_parts[0]
            requested_test = '*'

        # Make sure our test suite and subtest names are sane.
        if KEY_NAME_RE.match(test_suite) is None:
            raise TestConfigError("Invalid test suite name: '{}'"
                                  .format(test_suite))
        if requested_test != '*' and KEY_NAME_RE.match(requested_test) is None:
            raise TestConfigError("Invalid subtest for requested test: '{}'"
                                  .format(test_name))

        # Only load each test suite's tests once.
        if test_suite not in all_tests:
            test_suite_path = _find_config(pav_cfg, CONF_TEST, test_suite)

            if test_suite_path is None:
                raise TestConfigError(
                    "Could not find test suite {}. Looked in these "
                    "locations: {}"
                    .format(test_suite, pav_cfg.config_dirs))

            try:
                with test_suite_path.open() as test_suite_file:
                    # We're loading this in raw mode, because the defaults
                    # will have already been provided.
                    # Each test config will be individually validated later.
                    test_suite_cfg = test_suite_loader.load_raw(
                        test_suite_file)

            except (IOError, OSError) as err:
                raise TestConfigError("Could not open test suite config {}: {}"
                                      .format(test_suite_path, err))

            suite_tests = resolve_inheritance(
                base_config,
                test_suite_cfg,
                test_suite_path
            )

            # Add some basic information to each test config.
            for test_cfg_name, test_cfg in suite_tests.items():
                test_cfg['name'] = test_cfg_name
                test_cfg['suite'] = test_suite
                test_cfg['suite_path'] = str(test_suite_path)

            all_tests[test_suite] = suite_tests

        # Now that we know we've loaded and resolved a given suite,
        # get the relevant tests from it.
        if requested_test == '*':
            # All tests were requested.
            for test_cfg_name, test_cfg in all_tests[test_suite].items():
                picked_tests.append(test_cfg)

        else:
            # Get the one specified test.
            if requested_test not in all_tests[test_suite]:
                raise TestConfigError(
                    "Test suite '{}' does not contain a test '{}'."
                    .format(test_suite, requested_test))

            picked_tests.append(all_tests[test_suite][requested_test])

    return picked_tests


def resolve_inheritance(base_config, suite_cfg, suite_path):

    test_config_loader = TestConfigLoader()

    # Organize tests into an inheritance tree.
    depended_on_by = defaultdict(lambda: list())
    # All the tests for this suite.
    suite_tests = {}
    # A list of tests whose parent's have had their dependencies
    # resolved.
    ready_to_resolve = list()
    for test_cfg_name, test_cfg in suite_cfg.items():
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
                "Test {} in suite {} has an error: {}"
                .format(test_cfg_name, suite_path, err))

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
            "Tests in suite '{}' have dependencies on '{}' that "
            "could not be resolved."
            .format(suite_path, depended_on_by.keys()))

    # Remove the test base
    del suite_tests['__base__']

    # Validate each test config individually.
    for test_name, test_config in suite_tests.items():
        try:
            suite_tests[test_name] = test_config_loader.validate(test_config)
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
        except TypeError as err:
            # See the same error above when loading host configs.
            raise RuntimeError(
                "Loaded test '{}' in suite '{}' raised a type error, but that "
                "should never happen. {}".format(test_name, suite_path, err))

    return suite_tests


NOT_OVERRIDABLE = ['name', 'suite', 'suite_path']


def apply_overrides(test_cfg, overrides):
    """Apply overrides to this test.
    :param dict test_cfg: The test configuration.
    :param dict overrides: A dictionary of values to override in all
        configs. This occurs at the highest level, after inheritance is
        resolved.
    """

    _apply_overrides(test_cfg, overrides, _first_level=True)


def _apply_overrides(test_cfg, overrides, _first_level=True):
    """Apply overrides recursively."""

    for key in overrides.keys():
        if _first_level and key in NOT_OVERRIDABLE:
            LOGGER.warning("You can't override the '{}' key in a test config."
                           .format(key))
            continue

        if key not in test_cfg:
            test_cfg[key] = overrides[key]
        elif isinstance(test_cfg[key], dict):
            if isinstance(overrides[key], dict):
                _apply_overrides(test_cfg[key], overrides[key])
            else:
                raise TestConfigError(
                    "Cannot override a dictionary of values with a "
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
                raise TestConfigError(
                    "Tried to override list key {} with a {} ({})"
                    .format(key, type(overrides[key]), overrides[key]))
        elif isinstance(test_cfg[key], str):
            if isinstance(overrides[key], str):
                test_cfg[key] = overrides[key]
            else:
                raise TestConfigError(
                    "Tried to override str key {} with a {} ({})"
                    .format(key, type(overrides[key]), overrides[key]))
        else:
            raise TestConfigError(
                "Configuration contains an element of an unrecognized type. "
                "Key: {}, Type: {}.".format(key, type(test_cfg[key])))


def resolve_permutations(raw_test_cfg, pav_vars, sys_vars):
    """Resolve permutations for all used permutation variables, returning a
    variable manager for each permuted version of the test config. We use
    this opportunity to populate the variable manager with most other
    variable types as well.
    :param dict raw_test_cfg: The raw test configuration dictionary.
    :param dict pav_vars: The pavilion provided variable set.
    :param Union(dict, pavilion.system_variables.SysVarDict) sys_vars: The
        system plugin provided variable set.
    :returns: The parsed, modified configuration, and a list of variable set
        managers, one for each permutation. These will already contain all the
        var, sys, pav, and (resolved) permutation (per) variable sets. The
        'sched' variable set will have to be added later.
    :rtype: (dict, [variables.VariableSetManager])
    :raises TestConfigError: When there are problems with variables or the
        permutations.
    """

    test_cfg = copy.deepcopy(raw_test_cfg)

    if 'permutations' in test_cfg:
        per_vars = test_cfg['permutations']
        # This is no longer used in the config.
        del test_cfg['permutations']
    else:
        per_vars = {}

    base_var_man = variables.VariableSetManager()
    try:
        base_var_man.add_var_set('per', per_vars)
    except variables.VariableError as err:
        raise TestConfigError("Error in permutations section: {}".format(err))

    # We don't resolve variables within the variables section, so we remove
    # those parts now.

    if 'variables' in test_cfg:
        user_vars = test_cfg['variables']
        del test_cfg['variables']
    else:
        user_vars = {}

    # Recursively make our configuration a little less raw, recursively
    # parsing all string values into PavString objects.
    test_cfg = _parse_strings(test_cfg)

    # We only want to permute over the permutation variables that are
    # actually used.  This also provides a convenient place to catch any
    # problems with how those variables are used.
    try:
        used_per_vars = _get_used_per_vars(test_cfg, base_var_man)
    except RuntimeError as err:
        raise TestConfigError(
            "In suite file '{}' test name '{}': {}"
            .format(test_cfg['suite'], test_cfg['name'], err))

    # Since per vars are the highest in resolution order, we can make things
    # a bit faster by adding these after we find the used per vars.
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
    """Parse all non-key strings in the given config section, and replace
    them with a PavString object. This involves recursively walking any
    data-structures in the given section.
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
    elif section is None:
        return None
    else:
        # Should probably never happen (We're going to see this error a lot
        # until we get a handle on strings vs unicode though).
        raise RuntimeError("Invalid value type '{}' of value '{}'."
                           .format(type(section), section))


def _get_used_per_vars(component, var_man):
    """Recursively get all the variables used by this test config, in canonical
        form.
    :param component: A section of the configuration file to look for per vars
        in.
    :param variables.VariableSetManager: The variable set manager.
    :returns: A list of used 'per' variables names (Just the 'var' component).
    :raises RuntimeError: For invalid sections.
    """

    used_per_vars = set()

    if isinstance(component, dict):
        for key in sorted(component.keys()):
            try:
                used_per_vars = used_per_vars.union(
                    _get_used_per_vars(component[key], var_man))
            except KeyError:
                pass

    elif isinstance(component, list):
        for i in range(len(component)):
            try:
                used_per_vars = used_per_vars.union(
                    _get_used_per_vars(component[i], var_man))
            except KeyError:
                pass

    elif isinstance(component, string_parser.PavString):
        for var in component.variables:
            try:
                var_set, var, idx, sub = var_man.resolve_key(var)
            except KeyError:
                continue

            # Grab just 'per' vars. Also, if per variables are used by index,
            # we just resolve that value normally rather than permuting over
            # it.
            if var_set == 'per' and idx is None:
                used_per_vars.add(var)
    elif component is None:
        # It's ok if this is None.
        pass
    else:
        # This should be unreachable.
        raise RuntimeError("Unknown config component type '{}' of '{}'"
                           .format(type(component), component))

    return used_per_vars


def resolve_all_vars(config, var_man, no_deferred_allowed):
    """Recursively resolve the given config's variables, using a
    variable manager.
    :param dict config: The config component to resolve.
    :param var_man: A variable manager. (Presumably a permutation of the
        base var_man)
    :param list no_deferred_allowed: Do not allow deferred variables in
        sections of these names.
    :return: The component, resolved.
    """

    #dbg_print("\nresolve_all_vars input config: " + str(config))
    resolved_dict = {}

    for key in config:
        allow_deferred = False if key in no_deferred_allowed else True

        resolved_dict[key] = _resolve_section_vars(config[key],
                                                   var_man, allow_deferred)

    #dbg_print("\nresolve_all_vars output config: " + str(resolved_dict))
    return resolved_dict


def _resolve_section_vars(component, var_man, allow_deferred):
    """Recursively resolve the given config component's  variables, using a
     variable manager.
    :param dict component: The config component to resolve.
    :param var_man: A variable manager. (Presumably a permutation of the
        base var_man)
    :param bool allow_deferred: Do not allow deferred variables in this section.
    :return: The component, resolved.
    """

    if isinstance(component, dict):
        resolved_dict = {}
        for key in component.keys():
            resolved_dict[key] = _resolve_section_vars(component[key], var_man,
                                                       allow_deferred)
        return resolved_dict

    elif isinstance(component, list):
        resolved_list = []
        for i in range(len(component)):
            resolved_list.append(_resolve_section_vars(component[i], var_man,
                                                       allow_deferred))
        return resolved_list

    elif isinstance(component, string_parser.PavString):
        return component.resolve(var_man, allow_deferred=allow_deferred)
    elif isinstance(component, str):
        # Some PavStrings may have already been resolved.
        return component
    elif component is None:
        return None
    else:
        raise TestConfigError("Invalid value type '{}' for '{}' when "
                              "resolving strings."
                              .format(type(component), component))

def resolve_cir_ref(raw_test_cfg):
    
    test_cfg = {}
    if 'variables' in raw_test_cfg:
        test_cfg = raw_test_cfg['variables']

    dbg_print("OLD VARIABLES: " + str(test_cfg))
    # traverse dictionary, look for values that references keys
    for k,v in test_cfg.items():
        for i in range(len(v)):
            ele = v[i]
            if '{{' in ele:
                ele = ele.replace('{{','')
                ele = ele.replace('}}','')
                try:
                    dbg_print('\n' + k + " " + ele)
                    if(_resolve_cir_ref(test_cfg, k, ele)):
                        dbg_print(k + " " + ele + " is a circ. ref.")
                    else:
                        dbg_print(k + " " + ele + " works!")
                    #cir_ref = _resolve_cir_ref(test_cfg,k,ele)
                    #dbg_print(cir_ref)
                    #dbg_print("new val: " + str(new_val))
                    #dbg_print(test_cfg[k][i])
                    #test_cfg[k] = new_val
                except:
                    print("circular references don't have source")

    dbg_print("\nNEW VARIABLES: " + str(test_cfg))

def _resolve_cir_ref(config_dict, key, ref):
    # input: variable reference
    # returns true if circular ref
    
    if key == ref:
        dbg_print("variable cannot reference itself")
        return 1
    elif str(ref) in config_dict:
        new_ref = config_dict[ref][0].replace('{{','')
        new_ref = new_ref.replace('}}','')
        dbg_print(key + " " + " " + ref + " " + new_ref)
        return _resolve_cir_ref(config_dict, key, new_ref)

    return 0
