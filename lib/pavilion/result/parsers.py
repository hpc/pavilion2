"""This module contains the ResultParser plugin class, as well functions
to process result parser configurations defined by a test run."""

import glob
import inspect
import logging
import pprint
import re
import textwrap
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Callable, Any, List, Union, TextIO, Pattern

import yaml_config as yc
from pavilion.result.base import ResultError, RESULT_ERRORS
from pavilion.test_config import file_format, resolver
from pavilion.utils import auto_type_convert, IndentedLog
from yapsy import IPlugin

LOGGER = logging.getLogger(__file__)


# The dictionary of result parsers.
_RESULT_PARSERS = {}


class ParseErrorMsg:
    """Standardized result parser error message."""

    def __init__(self, key: str, parser: 'ResultParser',
                 msg: str, file: str = None):
        """Initialize the message.
        :param key: The key being parsed when the error occured.
        :param parser: The result parser being handled.
        :param msg: The error message.
        :param file: The file being parsed.
        """

        self.key = key
        self.parser = parser
        self.file = file
        self.msg = msg

    def __str__(self):
        if self.file:
            return (
                "Error parsing for key '{key}' under the result parser "
                "'{parser_name}' for file {file_path}.\n"
                "Parser module path: {module_path}\n{msg}".format(
                    key=self.key,
                    parser_name=self.parser.name,
                    file_path=self.file,
                    module_path=inspect.getfile(self.parser.__class__),
                    msg=self.msg))
        else:
            return (
                "Error parsing for key '{key}' under the result parser "
                "'{parser_name}'.\n"
                "Parser module path: {module_path}\n{msg}".format(
                    key=self.key,
                    parser_name=self.parser.name,
                    module_path=inspect.getfile(self.parser.__class__),
                    msg=self.msg))


def get_plugin(name):
    """Get the result plugin parser called name.

:param str name: The name of the result parser plugin to return.
:rtype: ResultParser
"""

    return _RESULT_PARSERS[name]


def list_plugins():
    """Return a list of result parser plugin names."""

    return list(_RESULT_PARSERS.keys())


def __reset():
    """Reset the plugin setup. This is for testing only."""

    global _RESULT_PARSERS  # pylint: disable=W0603

    # Remove all existing parsers.
    for parser in list(_RESULT_PARSERS.values()):
        parser.deactivate()


def normalize_filename(name: Path) -> str:
    """Remove any characters that aren't allowed in Pavilion variable names."""

    name = name.name.split('.')[0]

    parts = []
    for p in name:
        if not p.isalnum():
            parts.append('_')
        else:
            parts.append(p)
    return ''.join(parts)


NON_MATCH_VALUES = (None, [], False)
EMPTY_VALUES = (None, [])

ACTION_STORE = 'store'
ACTION_STORE_STR = 'store_str'
ACTION_TRUE = 'store_true'
ACTION_FALSE = 'store_false'
ACTION_COUNT = 'count'

# Action functions should take the raw value and convert it to a final value.
ACTIONS = {
    ACTION_STORE: auto_type_convert,
    ACTION_STORE_STR: lambda raw_val: raw_val,
    ACTION_COUNT: lambda raw_val: len(raw_val),
    ACTION_TRUE: lambda raw_val: raw_val not in NON_MATCH_VALUES,
    ACTION_FALSE: lambda raw_val: raw_val in NON_MATCH_VALUES,
}


def store_values(stor: dict, keys: str, values: Any,
                 action: Callable[[Any], Any]) -> List[str]:
    """Store the values under the appropriate keys in the given dictionary
    using the given action.

    For single keys like 'flops', the action modified value is simply stored.

    For complex keys like 'flops, , speed', values is expected to be a list
    of at least this length, and the action modified values are stored in
    the key that matches their index.

    A list of errors/warnings are returned."""

    print('storing:\n stor - {}\n keys - {}\n values - {}\n action - {}\n'
          .format(stor, keys, values, action))

    errors = []

    if ',' in keys:
        keys = [k.strip() for k in keys.split(',')]
        # Strip the last item if it's empty, as it can be used to denote
        # storing a single item from a list.
        if keys[-1] == '':
            keys = keys[:-1]

        if not isinstance(values, list):
            errors.append(
                "Trying to store non-list value in a multi-keyed result.\n"
                "Just storing under the first non-null key.\n"
                "keys: {}\nvalue: {}".format(keys, values))
            key = [k for k in keys if k][0]
            stor[key] = action(values)

        else:
            values = list(reversed(values))

            if len(values) < len(keys):
                errors.append(
                    "More keys than values for multi-keyed result.\n"
                    "Storing 'null' for missing values.\n"
                    "keys: {}, values: {}".format(keys, values))

            for key in keys:
                val = values.pop() if values else None
                if key:
                    stor[key] = action(val)

    else:
        stor[keys] = action(values)

    return errors


# Per file callbacks.
# These should take a results dict, key string (which may list multiple
# keys), per_file values dict, and an action callable.
# In general, they'll choose one or more of the per-file results
# to store in the results dict at the given key/s.
# They should return a list of errors/warnings.
def per_first(results: dict, key: str, file_vals: Dict[Path, Any],
              action: Callable[[dict, str, Any], None]) -> List[str]:
    """Store the first non-empty value."""

    errors = []

    first = [val for val in file_vals.values() if val not in EMPTY_VALUES][:1]
    if not first:
        first = [None]
        errors.append(
            "No matches for key '{}' for any of these found files: {}."
            .format(key, ','.join(f.name for f in file_vals.keys())))

    errors.extend(store_values(results, key, first[0], action))
    return errors


def per_last(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable[[dict, str, Any], None]):
    """Store the last non-empty value."""

    errors = []

    last = [val for val in file_vals if val not in EMPTY_VALUES][-1:]
    if not last:
        last = [None]
        errors.append(
            "No matches for key '{}' for any of these found files: {}."
            .format(key, ','.join(f.name for f in file_vals.keys())))

    errors.extend(store_values(results, key, last[0], action))
    return errors


def per_name(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable[[dict, str, Any], None]):
    """Store in a dict by file fullname."""

    per_file = results['per_file']
    errors = []
    normalized = {}

    for file, val in file_vals.items():
        name = normalize_filename(file)
        normalized[name] = normalized.get(name, []) + [file]
        per_file[name] = per_file.get(name, {})

        errors.extend(store_values(per_file[name], key, val, action))

    for name, files in normalized.items():
        if len(files) > 1:
            errors.append(
                "When storing value for key '{}' per 'name', "
                "multiple files normalized to the name '{}': {}"
                .format(key, name, ', '.join([f.name for f in files])))

    return errors


def per_name_list(results: dict, key: str, file_vals: Dict[Path, Any],
                  action):
    """Store the file name for each file with a match. The action is ignored,
    and the key is expected to be a single value."""

    _ = action

    matches = []
    normalized = {}

    for file, val in file_vals.items():
        name = normalize_filename(file)
        normalized[name] = normalized.get(name, []) + [file]

        if val not in NON_MATCH_VALUES:
            matches.append(name)

    results[key] = matches

    errors = []
    for name, files in normalized.items():
        if len(files) > 1:
            errors.append(
                "When storing value for key '{}' per 'name_list', "
                "multiple files normalized to the name '{}': {}"
                .format(key, name, ', '.join([f.name for f in files])))
    return errors


def per_list(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable):
    """Merge all values from all files into a single list. If the values
    are lists, they will be merged and the action will be applied to each
    sub-item. Single valued keys only."""

    all_vals = []
    for _, val in file_vals.items():
        if val in EMPTY_VALUES:
            continue

        if isinstance(val, list):
            all_vals.extend(val)
        else:
            all_vals.append(val)

    return store_values(results, key, all_vals, action)


def per_any(results: dict, key: str, file_vals: Dict[Path, Any], action):
    """Set True (single valued keys only) if any file had a match. The
    action is ignored."""

    _ = action

    results[key] = any(val not in NON_MATCH_VALUES
                       for val in file_vals.values())

    return []


def per_all(results: dict, key: str, file_vals: Dict[Path, Any], action):
    """Set True (single valued keys only) if any file had a match. The
    action is ignored."""

    _ = action

    results[key] = all(val not in NON_MATCH_VALUES
                       for val in file_vals.values())

    return []


PER_FIRST = 'first'
PER_LAST = 'last'
PER_NAME = 'name'
PER_NAME_LIST = 'name_list'
PER_LIST = 'list'
PER_ALL = 'all'
PER_ANY = 'any'

PER_FILES = {
    PER_FIRST: per_first,
    PER_LAST: per_last,
    PER_NAME: per_name,
    PER_NAME_LIST: per_name_list,
    PER_LIST: per_list,
    PER_ALL: per_all,
    PER_ANY: per_any,
}

MATCH_FIRST = 'first'
MATCH_LAST = 'last'
MATCH_ALL = 'all'
MATCH_CHOICES = {
    MATCH_FIRST: 0,
    MATCH_LAST: -1,
    MATCH_ALL: None,
}


DEFAULT_KEY = '_defaults'


def set_parser_defaults(rconf: dict, def_conf: dict):
    """Set the default values for each result parser. The default conf
    can hold defaults that apply across an entire result parser."""

    base = DEFAULTS.copy()

    for key, val in def_conf.items():
        if val not in (None, []):
            base[key] = val

    for key, val in rconf.items():
        if val is None:
            continue

        if key in base and val == []:
            continue

        base[key] = val

    return base


def match_select_validator(match_select):
    """Make sure this is predefined string or integer."""

    if match_select in ('first', 'last', 'all'):
        return

    try:
        int(match_select)
    except ValueError:
        raise ValueError(
            "This must be one of {} or an integer."
            .format(match_select, list(MATCH_CHOICES.keys())))


def match_pos_validator(match_pos):
    """Validate match position arguments."""
    try:
        re.compile(match_pos)
    except re.error as err:
        raise ValueError("Invalid regular expression.\n{}"
                         .format(match_pos, err.args[0]))


# Validators are used to check the attribute values. When a attribute
# is a list, they are applied against each list item.
BASE_VALIDATORS = {
    'match_select': match_select_validator,
    'preceded_by': match_pos_validator,
    'for_lines_matching': match_pos_validator,
    'action': tuple(ACTIONS.keys()),
    'per_file': tuple(PER_FILES.keys()),
}


DEFAULTS = {
    'per_file':           PER_FIRST,
    'action':             ACTION_STORE,
    'files':              ['../run.log'],
    'match_select':       MATCH_FIRST,
    'for_lines_matching': '',
}


class ResultParser(IPlugin.IPlugin):
    """Base class for creating a result parser plugin. These are essentially
a callable that implements operations on the test or test files. The
arguments for the callable are provided automatically via the test
config. The doc string of result parser classes is used as the user help
text for that class, along with the help from the config items."""

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    FORCE_DEFAULTS = []
    """Let the user know they can't set these config keys for this result
    parser, effectively forcing the value to the default."""

    def __init__(self, name, description, defaults=None,
                 config_elems=None, validators=None,
                 priority=PRIO_COMMON):
        """Initialize the plugin object

:param str name: The name of this plugin.
:param str description: A short description of this result parser.
:param List[yaml_config.ConfigElement] config_elems: A list of configuration
    elements (from the yaml_config library) to use to define the
    config section for this result parser. These will be passed as arguments
    to the parser function. Only StrElem and ListElems are accepted. Any type
    conversions should be done with validators. Use the defaults and validators
    argument to set defaults, rather than the YamlConfig options.
:param dict defaults: A dictionary of defaults for the result parser's
    arguments.
:param dict validators: A dictionary of auto-validators. These can
    take several forms:

    - A tuple - The value must be one of the items in the tuple.
    - a function - The function should accept a single argument. The
      returned value is used. ValueError or ResultError should be raised
      if there are issues. Typically this will be a type conversion function.
      For list arguments this is applied to each of the list values.
:param int priority: The priority of this plugin, compared to plugins
    of the same name. Higher priority plugins will supersede others.
"""

        self.name = name
        self.description = description
        self.defaults = {} if defaults is None else defaults

        self.validators = BASE_VALIDATORS.copy()

        if validators is not None:
            for key, validator in validators.items():
                if not (isinstance(validator, tuple) or
                        callable(validator)):
                    raise RuntimeError(
                        "Validator for key {} in result parser {} at {} must "
                        "be a tuple or a function."
                        .format(key, name, self.path)
                    )

                validators[key] = validator

        config_elems = config_elems if config_elems is not None else []
        for elem in config_elems:
            if not (isinstance(elem, yc.StrElem) or
                    (isinstance(elem, yc.ListElem) and
                     isinstance(elem._sub_elem, yc.StrElem))):
                raise RuntimeError(
                    "Config elements for result parsers must be strings"
                    "or lists of strings. Got elem {} in parser at {}"
                    .format(elem, self.path)
                )

            if elem.default not in [None, []] or elem._choices is not None:
                raise RuntimeError(
                    "Config elements for result parsers shouldn't set "
                    "a default or choices (use the defaults or validators"
                    "argument for the result_parser init). Problem found "
                    "in {} in result parser at {}"
                    .format(elem, self.path)
                )

        self.config_elems = config_elems
        self.priority = priority

        super().__init__()

    def __call__(self, file, **kwargs):
        """This is where the result parser is actually implemented.

:param pavilion.test_run.TestRun test: The test run object.
:param file: This will be a file object advanced to a position that fits
    the criteria of the 'preceded_by' and 'for_lines_matching' options.
:param dict kwargs: The arguments are the config values from the the
    test's result config section for this parser. These should be
    explicitly defined in your result parser class.
:raises ResultParserError: When something goes wrong.
"""

        raise NotImplementedError("A result parser plugin must implement"
                                  "the __call__ method.")

    def _check_args(self, **kwargs) -> dict:
        """Override this to add custom checking of the arguments at test
kickoff time. This prevents errors in your arguments from causing
a problem in the middle of a test run. The yaml_config module handles
structural checking (and can handle more). This should raise a
descriptive ResultParserError if any issues are found.

:param kwargs: Child result parsers should override these with
    specific kwargs for their arguments. They should all default to
    and rely on the config parser to set their defaults.
:raises ResultParserError: If there are bad arguments.
"""

        _ = self

        return kwargs

    def check_args(self, **kwargs) -> dict:
        """Check the arguments for any errors at test kickoff time, if they
don't contain deferred variables. We can't check tests with
deferred args. On error, should raise a ResultParserError.

:param dict kwargs: The arguments from the config.
:raises ResultError: When bad arguments are given.
"""

        # The presence or absence of needed args should be enforced by
        # setting 'required' in the yaml_config config items.
        args = self.defaults.copy()
        for key, val in kwargs.items():
            if val is None or (key in args and val == []):
                continue
            args[key] = kwargs[key]
        kwargs = args

        base_keys = ('action', 'per_file', 'files', 'match_select',
                     'for_lines_matching', 'preceded_by')

        for key in base_keys:
            if key not in kwargs:
                raise RuntimeError(
                    "Result parser '{}' missing required attribute '{}'. These "
                    "are validated at the config level, so something is "
                    "probably wrong with plugin."
                    .format(self.name, key)
                )

        match_select = MATCH_CHOICES.get(kwargs['match_select'],
                                         kwargs['match_select'])
        if match_select is not None:
            try:
                int(match_select)
            except ValueError:
                raise ResultError(
                    "Invalid value for 'match_select'. Must be one of "
                    "{} or an integer.")

        for arg in self.FORCE_DEFAULTS:
            if kwargs[arg] != DEFAULTS[arg]:
                raise ResultError(
                    "This parser requires that you not set the '{}' key, as "
                    "the default value is the only valid option."
                    .format(arg))

        if kwargs['for_lines_matching'] is None and not kwargs['preceded_by']:
            raise ResultError(
                "At least one of 'for_lines_matching' or 'preceded_by' "
                "must be set. You should only see this if the default for "
                "'for_lines_matching' was explicitly set to null.")

        for key, validator in self.validators.items():
            if isinstance(validator, tuple):
                if kwargs[key] not in validator:
                    raise ResultError(
                        "Invalid value for option '{}'.\n"
                        "Expected one of {}, got '{}'."
                        .format(key, validator, kwargs[key])
                    )
            else:
                # Must be a validator function.
                value = kwargs[key]

                try:
                    if isinstance(value, list):
                        kwargs[key] = [validator(val) for val in value]
                    else:
                        kwargs[key] = validator(value)

                except ValueError as err:
                    raise ResultError(
                        "Validation error for option '{}' with "
                        "value '{}'.\n{}"
                        .format(key, kwargs[key], err.args[0])
                    )

        for key in base_keys:
            # The parser plugins don't know about these keys, as they're
            # handled at a higher level.
            del kwargs[key]

        return self._check_args(**kwargs)

    GLOBAL_CONFIG_ELEMS = [
        yc.StrElem(
            "action",
            help_text=(
                "What to do with parsed results.\n"
                "  {STORE} - Just store the result automatically converting "
                "       the value's type(default).\n"
                "  {STORE_STR} - Just store the value, with no type "
                "       conversion.\n"
                "  {TRUE} - Store True if there was a result.\n"
                "  {FALSE} - Store True for no result.\n"
                "  {COUNT} - Count the number of results.\n"
                .format(
                    STORE=ACTION_STORE,
                    STORE_STR=ACTION_STORE_STR,
                    TRUE=ACTION_TRUE,
                    FALSE=ACTION_FALSE,
                    COUNT=ACTION_COUNT))
        ),
        # The default for the file is handled by the test object.
        yc.ListElem(
            "files",
            sub_elem=yc.StrElem(),
            help_text="Path to the file/s that this result parser "
                      "will examine. Each may be a file glob,"
                      "such as '*.log'"),
        yc.StrElem(
            "per_file",
            help_text=(
                "How to save results for multiple file matches.\n"
                "  {FIRST} - The result from the first file with a "
                "non-empty result. If no files were found, this "
                "is considerd an error. (default)\n"
                "  {LAST} - As '{FIRST}', but last result.\n"
                "  {NAME} - Store the results on a per file "
                "basis under results['per_name'][<filename>][<key>]. The "
                "filename only includes the parts before any '.', and "
                "is normalized to replace non-alphanum characters with "
                "'_'\n"
                "  {NAME_LIST} - Save the matching (normalized) file "
                "names, rather than the parsed values, in a list.\n"
                "  {LIST} - Merge all each result and result list "
                "into a single list.\n"
                .format(
                    FIRST=PER_FIRST,
                    LAST=PER_LAST,
                    NAME=PER_NAME,
                    NAME_LIST=PER_NAME_LIST,
                    LIST=PER_LIST))
        ),
        yc.StrElem(
            "for_lines_matching",
            help_text=(
                "A regular expression used to identify the line where "
                "result parsing should start. The result parser will "
                "see the file starting at this line. Defaults to matching "
                "every line."
            )
        ),
        yc.ListElem(
            "preceded_by", sub_elem=yc.StrElem(),
            help_text=(
                "A list of regular expressions that must match lines that "
                "precede the lines to be parsed. Empty items"
                "in the sequence will match anything. The result parser "
                "will see the file starting from start of the line after "
                "these match.")),
        yc.StrElem(
            "match_select",
            help_text=(
                "In cases where multiple matches are possible, how to"
                "handle them. By default, find the first '{FIRST}' "
                "match and use it. '{LAST}' returns  the final match, and "
                "'{ALL}' will return a list of all matches. You may also "
                "give an integer to get the Nth match (starting at 0). "
                "Negative integers (starting at -1)count in reverse."

                .format(
                    FIRST=MATCH_FIRST,
                    LAST=MATCH_LAST,
                    ALL=MATCH_ALL))
        ),
    ]

    def get_config_items(self):
        """Get the config for this result parser. This should be a list of
yaml_config.ConfigElement instances that will be added to the test
config format at plugin activation time. The simplest format is a
list of yaml_config.StrElem objects, but any structure is allowed
as long as the leaf elements are StrElem type.

The config values will be passed as the keyword arguments to the
result parser when it's run and when its arguments are checked. The base
implementation provides several arguments that must be present for every result
parser. See the implementation of this method in result_parser.py for more
info on those arguments and what they do.

Example: ::

    config_items = super().get_config_items()
    config_items.append(
        yaml_config.StrElem('token', default='PASSED',
            help="The token to search for in the file."
    )
    return config_items

"""

        config_items = self.GLOBAL_CONFIG_ELEMS.copy()
        config_items.extend(self.config_elems)
        return config_items

    @property
    def path(self):
        """The path to the file containing this result parser plugin."""

        return inspect.getfile(self.__class__)

    def doc(self):
        """Return documentation on this result parser."""

        def wrap(text: str, indent=0):
            """Wrap a multi-line string."""

            indent = ' ' * indent

            out_lines = []
            for line in text.splitlines():
                out_lines.extend(
                    textwrap.wrap(line, initial_indent=indent,
                                  subsequent_indent=indent))

            return out_lines

        doc = [
            self.name,
            '-'*len(self.name)
        ]
        doc.extend(wrap(self.description))

        doc.extend([
            '\nArguments',
            '---------',
        ])

        for arg in self.get_config_items():
            doc.append('  ' + arg.name)
            doc.extend(wrap(arg.help_text, indent=4))
            if arg.name in self.defaults:
                doc.extend(wrap("default: '{}'".format(self.defaults[arg.name]),
                                indent=4))
            if arg.name in self.validators:
                validator = self.validators[arg.name]
                if isinstance(validator, tuple):
                    doc.extend(wrap('choices: ' + str(validator), indent=4))
            doc.append('')

        return '\n'.join(doc)

    def activate(self):
        """Yapsy runs this when adding the plugin.

In this case it:

- Adds the config section (from get_config_items()) to the test config
  format.
- Adds the result parser to the list of known result parsers.
"""

        config_items = self.get_config_items()

        file_format.TestConfigLoader.add_result_parser_config(self.name,
                                                              config_items)

        if self.name in _RESULT_PARSERS:
            other = _RESULT_PARSERS[self.name]
            if self.priority > other.priority:
                LOGGER.info(
                    "Result parser '%s' at %s is superseded by %s.",
                    self.name, other.path, self.path)
                _RESULT_PARSERS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info(
                    "Result parser '%s' at %s is ignored in lieu of %s.",
                    self.name, self.path, other.path)
            else:
                raise RuntimeError("Result parser conflict. Parser '{}' at {}"
                                   "has the same priority as {}"
                                   .format(self.name, other.path, self.path))
        else:
            _RESULT_PARSERS[self.name] = self

    def deactivate(self):
        """Yapsy calls this to remove this plugin. We only ever
    do this in unittests."""

        # Remove the section from the config.
        file_format.TestConfigLoader.remove_result_parser_config(self.name)

        # Remove from list of available result parsers.
        del _RESULT_PARSERS[self.name]


def check_parser_conf(rconf: dict, keys: List[str], parser) -> None:
    """Validate the given parser configuration.

    :raises: ResultError on failure.
    """

    action = rconf.get('action')
    per_file = rconf.get('per_file')

    found_deferred = False
    # Don't check args if they have deferred values.
    for option, values in rconf.items():
        if not isinstance(values, list):
            values = [values]

        for value in values:
            if resolver.TestConfigResolver.was_deferred(value):
                found_deferred = True

    if found_deferred:
        # We can't continue checking from this point if anything was deferred.
        return

    if ('result' in keys
            and action not in (ACTION_TRUE,
                               ACTION_FALSE)
            and per_file not in (PER_FIRST, PER_LAST)):
        raise ResultError(
            "Result parser has key 'result', but must store a "
            "boolean. Use action '{}' or '{}', along with a "
            "per_file setting of 'first', 'last', 'any', or 'all'"
            .format(ACTION_TRUE, ACTION_FALSE))

    try:
        parser.check_args(**rconf)
    except ResultError as err:
        raise ResultError(
            "Key '{}': {}".format(keys, err.args[0]))


def parse_results(test, results: Dict, log: IndentedLog) -> None:
    """Parse the results of the given test using all the result parsers
configured for that test.

- Find the result parser
- Parse results for each found file via the 'files' attr.
- Save those results (for each file) according to the 'action' attr.
- Combine file results into a single object with the 'per_file' attr
  and add them to the results dict.

:param pavilion.test_run.TestRun test: The pavilion test run to gather
    results for.
:param results: The dictionary of default result values. This will be
    updated in place.
:param log: The logging callable from 'result.get_result_logger'.
"""

    log("Starting result parsing.")

    parser_configs = test.config['result_parse']

    log("Got result parser configs:")
    log(pprint.pformat(parser_configs))
    log("---------------")

    # Get the results for each of the parsers specified.
    for parser_name in parser_configs.keys():
        # This is almost guaranteed to work, as the config wouldn't
        # have validated otherwise.
        parser = get_plugin(parser_name)

        defaults = parser_configs[parser_name].get(DEFAULT_KEY, {})

        log.indent = 1
        log("Parsing results for parser {}".format(parser_name))

        # Each parser has a list of configs. Process each of them.
        for key, rconf in parser_configs[parser_name].items():
            log.indent = 2
            log("Parsing value for key '{}'".format(key))

            error = parse_result(
                results=results,
                key=key,
                parser_cfg=set_parser_defaults(rconf, defaults),
                parser=parser,
                test=test,
                log=log)

            if error is not None:
                results[RESULT_ERRORS].append(str(error))


def advance_file(file: TextIO, conds: List[Pattern]) -> Union[int, None]:
    """Advance the file to a position where the previous lines match each
    of the 'before' regexes (in order) and the 'at' regex.

    :param file: The file to search. The file cursor will (probably) be moved.
    :param conds: A list of regexes that must match the sequence of lines
        that precede the line up to and including the current line before we
        can claim a match.
    :return: The position of the start of the line after the one advanced
        to. If None, then no matched position was found.
    """

    next_pos = file.tell()
    restart = None
    cond_idx = 0
    rewind_pos = None

    while cond_idx < len(conds):
        rewind_pos = next_pos

        line = file.readline()
        print('pos', rewind_pos, 'line', line)

        if line == '':
            return None

        next_pos = file.tell()
        if cond_idx == 0:
            restart = next_pos

        # When we match a condition, advance to the next one, otherwise reset.
        if conds[cond_idx].search(line) is not None:
            cond_idx += 1
        else:
            cond_idx = 0
            file.seek(restart)

        print(cond_idx, len(conds))
        # We've satisfied all conditions, stop searching.

    file.seek(rewind_pos)

    return next_pos


def parse_file(path: Path, parser: Callable, parser_args: dict,
               match_idx: Union[int, None],
               pos_regexes: List[Pattern],
               log: IndentedLog) -> Any:
    """Parse results for a single results file.

    :return: A list of all matching results found. Will be cut short if
        we only need the first result.
    """

    matches = []

    log.indent = 3
    log("Parsing for file '{}':".format(path.as_posix()))
    with path.open() as file:
        print("advancing file")
        next_pos = advance_file(file, pos_regexes)
        print("next_pos", next_pos, flush=True)

        while next_pos is not None:
            log("Found potential match at pos {} in file."
                .format(file.tell()))
            res = parser(file, **parser_args)
            print('result', res)

            if res is not None:

                matches.append(res)
                log("Parser extracted result '{}'".format(res))

            if match_idx is not None and 0 <= match_idx < len(matches):
                break

            next_pos = advance_file(file, pos_regexes)

    if match_idx is None:
        return matches
    else:
        try:
            return matches[match_idx]
        except IndexError:
            log("Match select index '{}' out of range. There were only {} "
                "matches.".format(match_idx, len(matches)))
            return None


def parse_result(results: Dict, key: str, parser_cfg: Dict,
                 parser: ResultParser, test, log: IndentedLog) \
        -> Union[ParseErrorMsg, None]:
    """Use a result parser and it's settings to parse a single value.

    :param results: The results dictionary.
    :param key: The key we're parsing.
    :param parser_cfg: The parser config dict.
    :param parser: The result parser plugin object.
    :param test: The test object.
    :param log: The result log callback.
    :returns: A ParseErrorMsg object, which standardizes the error message
        format.
    """

    # Grab these for local use.
    action_name = parser_cfg['action']
    globs = parser_cfg['files']
    per_file_name = parser_cfg['per_file']

    print('key: {}, parser: {}'.format(key, parser.name))
    print(MATCH_CHOICES, parser_cfg)
    match_idx = MATCH_CHOICES.get(parser_cfg['match_select'],
                                  parser_cfg['match_select'])
    match_idx = int(match_idx) if match_idx is not None else None

    # Compile the regexes for finding the appropriate lines on which to
    # call the result parser.
    match_cond_rex = [re.compile(cond) for cond in parser_cfg['preceded_by']]
    match_cond_rex.append(re.compile(parser_cfg['for_lines_matching']))

    # The result key is always true/false. It's ACTION_TRUE by
    # default.
    if (key == 'result' and
            action_name not in (ACTION_FALSE, ACTION_TRUE)):
        action_name = ACTION_TRUE
        log("Forcing action to '{}' for the 'result' key.")

    try:
        parser_args = parser.check_args(**parser_cfg.copy())
    except ResultError as err:
        return ParseErrorMsg(key, parser, err.args[0])

    # The per-file results for this parser
    presults = OrderedDict()

    log("Looking for files that match file globs: {}".format(globs))

    print('globs', globs)

    # Find all the files we'll be parsing.
    paths = []
    for file_glob in globs:
        if not file_glob.startswith('/'):
            file_glob = '{}/build/{}'.format(test.path, file_glob)

        paths_found = glob.glob(file_glob)
        paths_found.reverse()
        if paths_found:
            paths.extend(Path(path) for path in paths_found)
        else:
            presults[file_glob] = None

    print('paths: {}'.format([p.name for p in paths]))

    if not paths:
        msg = "File globs {} for key {} found no files.".format(globs, key)
        log(msg)

    log("Found {} matching files.".format(len(paths)))
    log("Results will be stored with action '{}'".format(action_name))
    log.indent = 3

    # Apply the result parser to each file we're parsing.
    # Handle the results according to the 'action' config attribute.
    for path in paths:
        try:
            res = parse_file(
                path=path,
                parser=parser, parser_args=parser_args,
                pos_regexes=match_cond_rex,
                match_idx=match_idx,
                log=log,
            )

        except OSError as err:
            msg = "Error reading file: {}".format(err)
            log(msg)
            return ParseErrorMsg(key, parser, msg, file=path.as_posix())
        except Exception as err:  # pylint: disable=W0703
            msg = "UnexpectedError: {}".format(err)
            log(msg)
            return ParseErrorMsg(key, parser, msg, file=path.as_posix())

        presults[path] = res
        log("Stored value '{}' for file '{}'".format(res, path.name))

    print('presults', presults)

    log.indent = 2
    log("Results for each found files:")
    for res_path, res_value in presults.items():
        if res_path.parent == test.build_path:
            res_path = res_path.name
        else:
            res_path = res_path.as_posix()
        log(' - {}: {}'.format(res_path, res_value))

    log("Handling results for key '{}' on a per-file basis with "
        "per_file setting '{}'".format(key, per_file_name))

    per_file_func = PER_FILES[per_file_name]  # type: per_first

    try:
        errors = per_file_func(
            results=results,
            key=key,
            file_vals=presults,
            action=ACTIONS[parser_cfg['action']]
        )

        for error in errors:
            results[RESULT_ERRORS].append(error)
            log(error)

        log("Processed results from key {} with per_file setting {} "
            "and action {}.".format(key, per_file_name, action_name))

    except ResultError as err:
        msg = (
            "Error handling results with per_file and action options.\n{}"
            .format(err.args[0]))

        log(msg)
        return ParseErrorMsg(key, parser, msg, file=globs)

    return None
