"""
Pavilion has to take a bunch of raw Suite/Test configurations, incorporate
various Pavilion variables, resolve test inheritance and permutations,
and finally produce a bunch of TestRun objects. These steps, and more,
are all handled by functions in this module.
"""

import copy
import io
import logging
import os
from collections import defaultdict

from yaml_config import RequiredError
import yc_yaml
from . import string_parser
from . import variables
from .file_format import TestConfigError, TEST_NAME_RE, KEY_NAME_RE
from .file_format import TestConfigLoader, TestSuiteLoader

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
    :rtype: Path
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
:return: Returns a dictionary of suite names to an info dict.
:rtype: dict(dict)

The returned data structure looks like: ::

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
                    suite_cfgs = resolve_inheritance(
                        base_config=base,
                        suite_cfg=suite_cfg,
                        suite_path=file
                    )
                except Exception as err:  # pylint: disable=W0703
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
    """Get a list of raw test configs given a host, list of modes,
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
    :rtype: list(dict)
    :return: A list of raw test_cfg dictionaries.
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
            except yc_yaml.YAMLError as err:
                raise TestConfigError(
                    "Host config '{}' has a YAML Error: {}"
                    .format(host_cfg_path, err)
                )
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

    # A dictionary of test suites to a list of subtests to run in that suite.
    all_tests = defaultdict(dict)
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
        if requested_test != '*' and TEST_NAME_RE.match(requested_test) is None:
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

            except (IOError, OSError, ) as err:
                raise TestConfigError("Could not open test suite config {}: {}"
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
                # All config elements in test configs must be strings, and just
                # about everything converts cleanly to a string.
                raise RuntimeError(
                    "Test suite '{}' raised a type error, but that "
                    "should never happen. {}".format(test_suite_path, err))

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
                if not test_cfg_name.startswith('_'):
                    picked_tests.append(test_cfg)

        else:
            # Get the one specified test.
            if requested_test not in all_tests[test_suite]:
                raise TestConfigError(
                    "Test suite '{}' does not contain a test '{}'."
                    .format(test_suite, requested_test))

            picked_tests.append(all_tests[test_suite][requested_test])

    # Get the default configuration for a const result parser.
    const_elem = TestConfigLoader().find('results.constant.*')

    # Add the pav_cfg default_result configuration items to each test.
    for test_cfg in picked_tests:
        if 'constant' not in test_cfg['results']:
            test_cfg['results']['constant'] = []

        const_keys = [const['key'] for const in test_cfg['results']['constant']]

        for key, const in pav_cfg.default_results.items():

            if key in const_keys:
                # Don't override any that are already there.
                continue

            new_const = const_elem.validate({
                'key': key,
                'const': const,
            })
            test_cfg['results']['constant'].append(new_const)

    return picked_tests


def resolve_inheritance(base_config, suite_cfg, suite_path):
    """Resolve inheritance between tests in a test suite. There's potential
    for loops in the inheritance hierarchy, so we have to be careful of that."""

    test_config_loader = TestConfigLoader()

    # This iterative algorithm recursively resolves the inheritance tree from
    # the root ('__base__') downward. Nodes that have been resolved are
    # separated from those that haven't. We then resolve any nodes whose
    # dependencies are all resolved and then move those nodes to the resolved
    # list. When we run out of nodes that can be resolved, we're done. If there
    # are still unresolved nodes, then a loop must exist.

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
                raise TestConfigError("{} in {} is empty. Nothing will execute."
                                      .format(test_cfg_name, suite_path))
            if test_cfg.get('inherits_from') is None:
                test_cfg['inherits_from'] = '__base__'
                # Tests that depend on nothing are ready to resolve.
                ready_to_resolve.append(test_cfg_name)
            else:
                depended_on_by[test_cfg['inherits_from']].append(test_cfg_name)

            try:
                suite_tests[test_cfg_name] = TestConfigLoader().normalize(
                    test_cfg)
            except (TypeError, KeyError, ValueError) as err:
                raise TestConfigError(
                    "Test {} in suite {} has an error: {}"
                    .format(test_cfg_name, suite_path, err))
    except AttributeError as err:
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
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "Test {} in suite {} has a YAML Error: {}"
                .format(test_name, suite_path, err)
            )
        except TypeError as err:
            # See the same error above when loading host configs.
            raise RuntimeError(
                "Loaded test '{}' in suite '{}' raised a type error, but that "
                "should never happen. {}".format(test_name, suite_path, err))

    return suite_tests


NOT_OVERRIDABLE = ['name', 'suite', 'suite_path', 'scheduler']


def apply_overrides(test_cfg, overrides):
    """Apply overrides to this test.

    :param dict test_cfg: The test configuration.
    :param list overrides: A list of raw overrides in a.b.c=value form.
    :raises: ValueError, KeyError
"""

    for ovr in overrides:
        if '=' not in ovr:
            raise ValueError(
                "Invalid override value. Must be in the form: "
                "<key>=<value>. Ex. -c run.modules=['gcc'] ")

        key, value = ovr.split('=', 1)
        key = key.split('.')

        _apply_override(test_cfg, key, value)

    TestConfigLoader().validate(test_cfg)


def _apply_override(test_cfg, key, value):
    """Set the given key to the given value in test_cfg.
    :param dict test_cfg: The test configuration.
    :param [str] key: A

    """

    cfg = test_cfg

    disp_key = '.'.join(key)

    if key[0] in NOT_OVERRIDABLE:
        raise KeyError("You can't override the '{}' key in a test config")

    key_copy = list(key)
    last_cfg = None
    last_key = None
    # Validate the key.
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
                raise KeyError("Trying to override index '{}' from key '{}' "
                               "but the index is out of range."
                               .format(part, disp_key))
        elif isinstance(cfg, dict):
            if part not in cfg:
                raise KeyError("Trying to override '{}' from key '{}', but "
                               "there is no such key."
                               .format(part, disp_key))
            last_cfg = cfg
            last_key = part
            cfg = cfg[part]
        else:
            raise KeyError("Tried, to override key '{}', but '{}' isn't"
                           "a dict or list."
                           .format(disp_key, part))

    if last_cfg is None:
        # Should never happen.
        raise RuntimeError("Trying to override an empty key: {}".format(key))

    # We should be at the final place where the value should go.
    try:
        dummy_file = io.StringIO(value)
        value = yc_yaml.safe_load(dummy_file)
    except (yc_yaml.YAMLError, ValueError, KeyError) as err:
        raise ValueError("Invalid value ({}) for key '{}' in overrides: {}"
                         .format(value, disp_key, err))

    last_cfg[last_key] = normalize_override_value(value)


def normalize_override_value(value):
    """Normalize a value to one compatible with Pavilion configs. It can be
    any structure of dicts and lists, as long as the leaf values are strings.
    :param value: The value to normalize.
    """
    if isinstance(value, str):
        return value
    elif isinstance(value, (int, float, bool, bytes)):
        return str(value)
    elif isinstance(value, (list, tuple)):
        return [normalize_override_value(v) for v in value]
    elif isinstance(value, dict):
        return {str(k): normalize_override_value(v)
                for k, v in value.items()}
    else:
        raise ValueError("Invalid type in override value: {}".format(value))


def resolve_permutations(raw_test_cfg, pav_vars, sys_vars):
    """Resolve permutations for all used permutation variables, returning a
    variable manager for each permuted version of the test config. We use
    this opportunity to populate the variable manager with most other
    variable types as well.

    :param dict raw_test_cfg: The raw test configuration dictionary.
    :param dict pav_vars: The pavilion provided variable set.
    :param Union(dict, pavilion.system_variables.SysVarDict) sys_vars: The
        system plugin provided variable set.
    :returns: The modified configuration, and a list of variable set
        managers, one for each permutation. These will already contain all the
        var, sys, pav, and (resolved) permutation (per) variable sets. The
        'sched' variable set will have to be added later.
    :rtype: (dict, [variables.VariableSetManager])
    :raises TestConfigError: When there are problems with variables or the
        permutations.
    """
    test_cfg = copy.deepcopy(raw_test_cfg)
    base_var_man = variables.VariableSetManager()

    permute_on = test_cfg['permute_on']
    del test_cfg['permute_on']
    del test_cfg['variables']

    user_vars = raw_test_cfg.get('variables', {})

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
                "Permutation variable '{}' contains index or subvar."
                .format(per_var))
        elif base_var_man.is_deferred(var_set, var):
            raise TestConfigError(
                "Permutation variable '{}' references a deferred variable."
                .format(per_var))
        used_per_vars.add((var_set, var))

    # var_men is a list of variable managers, one for each permutation
    var_men = base_var_man.get_permutations(used_per_vars)
    for var_man in var_men:
        var_man.resolve_references(string_parser.parse)
    return test_cfg, var_men


DEFERRED_PREFIX = '!deferred!'


def was_deferred(val):
    """Return true if config item val was deferred when we tried to resolve
    the config.

    :param str val: The config value to check.
    :rtype: bool
    """

    return val.startswith(DEFERRED_PREFIX)


def resolve_config(config, var_man, no_deferred_allowed):
    """Recursively resolve the variables in the value strings in the given
    configuration.

    Deferred Variable Handling
      When a config value references a deferred variable, it is left unresolved
      and prepended with the DEFERRED_PREFIX. To complete these, use
      resolve_deferred().

    :param dict config: The config dict to resolve recursively.
    :param variables.VariableSetManager var_man: A variable manager. (
        Presumably a permutation of the base var_man)
    :param list no_deferred_allowed: Do not allow deferred variables in
        sections of with these names.
    :return: The resolved config,
    """

    resolved_dict = {}

    for key in config:
        allow_deferred = False if key in no_deferred_allowed else True

        resolved_dict[key] = resolve_section_vars(
            component=config[key],
            var_man=var_man,
            allow_deferred=allow_deferred,
            deferred_only=False,
        )

    return resolved_dict


def resolve_deferred(config, var_man):
    """Resolve only those values prepended with the DEFERRED_PREFIX. All
    other values are presumed to be resolved already.

    :param dict config: The configuration
    :param variables.VariableSetManager var_man: The variable manager. The must
        not contain any deferred variables.
    """

    if var_man.deferred:
        deferred = [
            ".".join([part for part in var_parts if part is not None])
            for var_parts in var_man.deferred
        ]

        raise RuntimeError(
            "The variable set manager must not contain any deferred "
            "variables, but contained these: {}"
            .format(deferred)
        )

    return resolve_section_vars(config, var_man,
                                allow_deferred=False,
                                deferred_only=True)


def resolve_section_vars(component, var_man, allow_deferred, deferred_only):
    """Recursively resolve the given config component's variables, using a
     variable manager.

    :param dict component: The config component to resolve.
    :param var_man: A variable manager. (Presumably a permutation of the
        base var_man)
    :param bool allow_deferred: Do not allow deferred variables in this section.
    :param bool deferred_only: Only resolve values prepended with
        the DEFERRED_PREFIX, and throw an error if such values can't be
        resolved.
    :return: The component, resolved.
    """

    if isinstance(component, dict):
        resolved_dict = type(component)()
        for key in component.keys():
            resolved_dict[key] = resolve_section_vars(component[key], var_man,
                                                      allow_deferred,
                                                      deferred_only)
        return resolved_dict

    elif isinstance(component, list):
        resolved_list = type(component)()
        for i in range(len(component)):
            resolved_list.append(resolve_section_vars(component[i], var_man,
                                                      allow_deferred,
                                                      deferred_only))
        return resolved_list

    elif isinstance(component, str):

        if deferred_only:
            # We're only resolving deferred value strings.

            if component.startswith(DEFERRED_PREFIX):
                component = component[len(DEFERRED_PREFIX):]

                resolved = string_parser.parse(component).resolve(var_man)
                if resolved is None:
                    raise RuntimeError(
                        "Tried to resolve a deferred config component, but it "
                        "was still deferred: {}"
                        .format(component)
                    )
                return resolved

            else:
                # This string has already been resolved in the past.
                return component

        else:
            if component.startswith(DEFERRED_PREFIX):
                # This should never happen
                raise RuntimeError(
                    "Tried to resolve a pavilion config string, but it was "
                    "started with the deferred prefix '{}'. This probably "
                    "happened because Pavilion called setup.resolve_config "
                    "when it should have called resolve_deferred."
                    .format(DEFERRED_PREFIX)
                )

            try:
                resolved = string_parser.parse(component).resolve(var_man)
            except string_parser.ResolveError as err:
                raise TestConfigError(err)

            if resolved is None:
                if allow_deferred:
                    return DEFERRED_PREFIX + component
                else:
                    raise string_parser.ResolveError(
                        "Deferred variable in section where it isn't allowed."
                        "'{}'".format(component)
                    )

            else:
                return resolved
    elif component is None:
        return None
    else:
        raise TestConfigError("Invalid value type '{}' for '{}' when "
                              "resolving strings."
                              .format(type(component), component))
