"""This module contains the ResultParser plugin class, as well functions
to process result parser configurations defined by a test run."""

import inspect
import logging
import re
import textwrap
from typing import List

import yaml_config as yc
from pavilion.test_config import file_format
from pavilion.test_config import variables
from yapsy import IPlugin
from .common import ResultError
from .options import (PER_FIRST, PER_LAST, PER_NAME, PER_LIST,
                      PER_NAME_LIST, PER_ALL, PER_ANY, PER_FILES,
                      MATCH_FIRST, MATCH_LAST, MATCH_ALL, MATCH_CHOICES,
                      ACTION_STORE, ACTION_STORE_STR, ACTION_TRUE,
                      ACTION_FALSE, ACTION_COUNT, ACTIONS)

LOGGER = logging.getLogger(__file__)


# The dictionary of result parsers.
_RESULT_PARSERS = {}


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
            if kwargs[arg] != self._DEFAULTS[arg]:
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
                "{STORE} - Just store the result automatically converting \n"
                "  the value's type(default).\n"
                "{STORE_STR} - Just store the value, with no type "
                "conversion.\n"
                "{TRUE} - Store True if there was a result.\n"
                "{FALSE} - Store True for no result.\n"
                "{COUNT} - Count the number of results.\n"
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
                "{FIRST} - (default) The result from the first file with a \n"
                "  non-empty result. If no files were found, this is \n"
                "  considerd an error. (default)\n"
                "{LAST} - As '{FIRST}', but last result.\n"
                "{NAME} - Store the results on a per file basis under \n"
                "  results['per_name'][<filename>][<key>]. The \n"
                "  filename only includes the parts before any '.', and \n"
                "  is normalized to replace non-alphanum characters with '_'\n"
                "{NAME_LIST} - Save the matching (normalized) file \n"
                "  names, rather than the parsed values, in a list.\n"
                "{LIST} - Merge all each result and result list \n"
                "  into a single list.\n"
                "{ALL} - Set 'True' if all files found at least one match.\n"
                "{ANY} - Set 'True' if any file found at lest one match.\n"
                .format(
                    FIRST=PER_FIRST,
                    LAST=PER_LAST,
                    NAME=PER_NAME,
                    NAME_LIST=PER_NAME_LIST,
                    LIST=PER_LIST,
                    ANY=PER_ANY,
                    ALL=PER_ALL,
                ))
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

        doc.append('\n{} Parser Specific Arguments'.format(self.name))
        doc.append('-'*len(doc[-1]))

        args = self.get_config_items()
        specific_args = [arg for arg in args
                         if arg.name not in self._DEFAULTS]

        def add_arg_doc(arg):
            """Add an arg to the documentation."""
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

        for arg in specific_args:
            if arg.name not in self._DEFAULTS:
                add_arg_doc(arg)

        doc.append('Universal Parser Arguments')
        doc.append('-'*len(doc[-1]))

        for arg in args:
            if arg.name in self._DEFAULTS:
                add_arg_doc(arg)

        return '\n'.join(doc)

    _DEFAULTS = {
        'per_file':           PER_FIRST,
        'action':             ACTION_STORE,
        'files':              ['../run.log'],
        'match_select':       MATCH_FIRST,
        'for_lines_matching': '',
        'preceded_by':        [],
    }
    """Defaults for the common parser arguments. This in not meant to be
    changed by subclasses."""

    def set_parser_defaults(self, rconf: dict, def_conf: dict):
        """Set the default values for each result parser. The default conf
        can hold defaults that apply across an entire result parser."""

        base = self._DEFAULTS.copy()

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

    def check_config(self, rconf: dict, keys: List[str]) -> None:
        """Validate the parser configuration.

        :param rconf: The results parser configuration.
        :param keys: The keys (generally one) under which the parsed results
            will be stored.
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
                if variables.DeferredVariable.was_deferred(value):
                    found_deferred = True

        if found_deferred:
            # We can't continue checking from this point if anything
            # was deferred.
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
            self.check_args(**rconf)
        except ResultError as err:
            raise ResultError(
                "Key '{}': {}".format(keys, err.args[0]))

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
