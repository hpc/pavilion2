from typing import Dict, List, Union, Tuple

from pavilion import parsers
from pavilion import variables
from pavilion.errors import TestConfigError, DeferredError, StringParserError, ParserValueError

DEFERRED_PREFIX = '!deferred!'
NO_DEFERRED_ALLOWED = [
    'schedule',
    'build',
    'scheduler',
    'chunk',
    'only_if',
    'not_if',
]


def test_config(config, var_man):
    """Recursively resolve the variables in the value strings in the given
    configuration.

    Deferred Variable Handling
      When a config value references a deferred variable, it is left
      unresolved and prepended with the DEFERRED_PREFIX. To complete
      these, use deferred().

    :param dict config: The config dict to resolve recursively.
    :param variables.VariableSetManager var_man: A variable manager. (
        Presumably a permutation of the base var_man)
    :return: The resolved config,
    """

    resolved_dict = {}

    for section in config:
        try:
            resolved_dict[section] = section_values(
                component=config[section],
                var_man=var_man,
                allow_deferred=section not in NO_DEFERRED_ALLOWED,
                key_parts=(section,),
            )
        except (StringParserError, ParserValueError) as err:
            raise TestConfigError("Error parsing '{}' section".format(section), err)

    for section in ('only_if', 'not_if'):
        try:
            if section in config:
                resolved_dict[section] = mapping_keys(
                    base_dict=resolved_dict.get(section, {}),
                    var_man=var_man,
                    section_name=section)
        except (StringParserError, ParserValueError) as err:
            raise TestConfigError("Error parsing key '{}' section".format(section), err)

    return resolved_dict


def deferred(config, var_man):
    """Resolve only those values prepended with the DEFERRED_PREFIX. All
    other values are presumed to be resolved already.

    :param dict config: The configuration
    :param variables.VariableSetManager var_man: The variable manager. This
        must not contain any deferred variables.
    """

    if var_man.deferred:
        deferred_name = [
            ".".join([part for part in var_parts if part is not None])
            for var_parts in var_man.deferred
        ]

        raise RuntimeError(
            "The variable set manager must not contain any deferred "
            "variables, but contained these: {}"
            .format(deferred_name)
        )

    config = section_values(config, var_man, deferred_only=True)
    for section in ('only_if', 'not_if'):
        if section in config:
            config[section] = mapping_keys(
                base_dict=config.get(section, {}),
                var_man=var_man,
                section_name=section,
                deferred_only=True)

    return config


def mapping_keys(base_dict, var_man, section_name, deferred_only=False) -> dict:
    """Some sections of the test config can have Pavilion Strings for
    keys. Resolve the keys of the given dict.

    :param dict[str,str] base_dict: The dict whose keys need to be resolved.
    :param variables.VariableSetManager var_man: The variable manager to
        use to resolve the keys.
    :param str section_name: The name of this config section, for error
        reporting.
    :param bool deferred_only: Resolve only deferred keys, otherwise
        mark deferred keys as deferred.
    :returns: A new dictionary with the updated keys.
    """

    new_dict = type(base_dict)()
    for key, value in base_dict.items():
        new_key = section_values(
            component=key,
            var_man=var_man,
            allow_deferred=True,
            deferred_only=deferred_only,
            key_parts=(section_name + '[{}]'.format(key),))

        # The value will have already been resolved.
        new_dict[new_key] = value

    return new_dict


def section_values(component: Union[Dict, List, str],
                   var_man: variables.VariableSetManager,
                   allow_deferred: bool = False,
                   deferred_only: bool = False,
                   key_parts: Union[None, Tuple[str]] = None):
    """Recursively resolve the given config component's value strings
    using a variable manager.

    :param component: The config component to resolve.
    :param var_man: A variable manager. (Presumably a permutation of the
        base var_man)
    :param allow_deferred: Allow deferred variables in this section.
    :param deferred_only: Only resolve values prepended with
        the DEFERRED_PREFIX, and throw an error if such values can't be
        resolved. If this is True deferred values aren't allowed anywhere.
    :param Union[tuple[str],None] key_parts: A list of the parts of the
        config key traversed to get to this point.
    :return: The component, resolved.
    :raises: RuntimeError, TestConfigError
    """

    if key_parts is None:
        key_parts = tuple()

    if isinstance(component, dict):
        resolved_dict = type(component)()
        for key in component.keys():
            resolved_dict[key] = section_values(
                component[key],
                var_man,
                allow_deferred=allow_deferred,
                deferred_only=deferred_only,
                key_parts=key_parts + (key,))

        return resolved_dict

    elif isinstance(component, list):
        resolved_list = type(component)()
        for i in range(len(component)):
            resolved_list.append(
                section_values(
                    component[i], var_man,
                    allow_deferred=allow_deferred,
                    deferred_only=deferred_only,
                    key_parts=key_parts + (i,)
                ))
        return resolved_list

    elif isinstance(component, str):

        if deferred_only:
            # We're only resolving deferred value strings.

            if component.startswith(DEFERRED_PREFIX):
                component = component[len(DEFERRED_PREFIX):]

                try:
                    resolved = parsers.parse_text(component, var_man)
                except DeferredError:
                    raise RuntimeError(
                        "Tried to resolve a deferred config component, "
                        "but it was still deferred: {}"
                        .format(component)
                    )
                except StringParserError as err:
                    raise TestConfigError(
                        "Error resolving value '{}' in config at '{}':\n"
                        "{}\n{}"
                        .format(component, '.'.join(map(str, key_parts)),
                                err.message, err.context))
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
                    "happened because Pavilion called setup.config "
                    "when it should have called deferred."
                    .format(DEFERRED_PREFIX)
                )

            try:
                resolved = parsers.parse_text(component, var_man)
            except DeferredError:
                if allow_deferred:
                    return DEFERRED_PREFIX + component
                else:
                    raise TestConfigError(
                        "Deferred variable in value '{}' under key "
                        "'{}' where it isn't allowed"
                        .format(component, '.'.join(map(str, key_parts))))
            except StringParserError as err:
                raise TestConfigError(
                    "Error resolving value '{}' in config at '{}':\n"
                    "{}\n{}"
                    .format(component,
                            '.'.join([str(part) for part in key_parts]),
                            err.message, err.context))
            else:
                return resolved
    elif component is None:
        return None
    else:
        raise TestConfigError("Invalid value type '{}' for '{}' when "
                              "resolving strings. Key parts: {}"
                              .format(type(component), component, key_parts))


def cmd_inheritance(test_cfg):
    """Extend the command list by adding any prepend or append commands,
    then clear those sections so they don't get added at additional
    levels of config merging."""

    for section in ['build', 'run']:
        config = test_cfg.get(section)
        if not config:
            continue
        new_cmd_list = []
        if config.get('prepend_cmds', []):
            new_cmd_list.extend(config.get('prepend_cmds'))
            config['prepend_cmds'] = []
        new_cmd_list += test_cfg[section]['cmds']
        if config.get('append_cmds', []):
            new_cmd_list.extend(config.get('append_cmds'))
            config['append_cmds'] = []
        test_cfg[section]['cmds'] = new_cmd_list

    return test_cfg
