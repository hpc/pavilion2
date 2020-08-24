"""This module contains the ResultParser plugin class, as well functions
to process result parser configurations defined by a test run."""

import glob
import inspect
import logging
import pprint
from collections import OrderedDict
from pathlib import Path
import textwrap
from typing import Dict, Callable, Any, List

import yaml_config as yc
from pavilion.result.base import ResultError
from pavilion.test_config import file_format, resolver
from yapsy import IPlugin

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

NON_MATCH_VALUES = (None, [], False)
EMPTY_VALUES = (None, [])

ACTION_STORE = 'store'
ACTION_TRUE = 'store_true'
ACTION_FALSE = 'store_false'
ACTION_COUNT = 'count'
ACTION_MULTI = 'store_multi'


def action_store(stor: dict, key: str, value):
    """Simply store the value under the key."""
    stor[key] = value


def action_true(stor: dict, key: str, value):
    """Evaluate for truth and store."""
    stor[key] = value not in NON_MATCH_VALUES


def action_false(stor: dict, key: str, value):
    """Evaluate for truth and store."""
    stor[key] = value in NON_MATCH_VALUES


def action_count(stor: dict, key: str, value):
    """Store the number of items. A value that isn't a list/tuple gets
    stored as 1 or 0 depending on its truth value."""
    # Count the returned items.

    if isinstance(value, (list, tuple)):
        stor[key] = len(value)
    elif value not in NON_MATCH_VALUES:
        stor[key] = 1
    else:
        stor[key] = 0


def action_multi(stor: dict, key: str, value):
    """Evaluate for truth and store."""

    if isinstance(value, dict):
        stor.update(value)
    else:
        stor[key] = "Non-dict result could not be stored with 'store_multi'"


# Action functions should take a dictionary, the key, and the raw value to
# store.
ACTIONS = {
    ACTION_STORE: action_store,
    ACTION_COUNT: action_count,
    ACTION_TRUE: action_true,
    ACTION_FALSE: action_false,
    ACTION_MULTI: action_multi,
}


def per_first(results: dict, key: str, file_vals: dict,
             action: Callable[[dict, str, Any], None],
             errors: List[str], log: Callable):
    """Store the first non-empty value."""

    first = [val for val in file_vals if val not in EMPTY_VALUES][:1]
    if not first:
        first = [None]
        errors.append("No matches for key {}.".format(key))
        log(errors[-1])

    action(results, key, first)

    log("PER_FIRST: Picked non-empty value '{}'".format(first))


def per_last(results: dict, key: str, file_vals: dict,
             action: Callable[[dict, str, Any], None],
             errors: List[str], log: Callable):
    """Store the last non-empty value."""

    last = [val for val in file_vals if val not in EMPTY_VALUES][-1:]
    if not last:
        last = [None]
        errors.append("No matches for key {}.".format(key))
        log(errors[-1])

    action(results, key, last[0])

    log("PER_LAST: Picked non-empty value '{}'".format(last))


def per_fullname(results: dict, key: str, file_vals: dict,
                 action: Callable[[dict, str, Any], None],
                 errors: List[str], log: Callable):
    """Store in a dict by file fullname."""

    per_file = results['per_file']





PER_FIRST = 'first'
PER_LAST = 'last'
PER_FULLNAME = 'fullname'
PER_NAME = 'name'
PER_FULLNAME_LIST = 'fullname_list'
PER_NAME_LIST = 'name_list'
PER_LIST = 'list'
PER_ANY = 'any'
PER_ALL = 'all'

MATCH_FIRST = 'first'
MATCH_LAST = 'last'
MATCH_ALL = 'all'
MATCH_CHOICES = (MATCH_FIRST, MATCH_LAST, MATCH_ALL)

MATCHES_ELEM = yc.StrElem(
    "match_type",
    help_text=(
        "How to handle multiple matches. '{FIRST}' (default) and '{LAST}'"
        "should return a single item (or nothing), while '{ALL}' "
        "should return a list of all matches."
        .format(
            FIRST=MATCH_FIRST,
            LAST=MATCH_LAST,
            ALL=MATCH_ALL,
        ))
)
"""This is to use in any result parser plugin that can match multiple items.
It's provided here for consistency between plugins."""


DEFAULTS = {
    'per_file': PER_FIRST,
    'action': ACTION_STORE,
    'files': ['../run.log']
}

CHOICES = {
    'per_file': (PER_FIRST, PER_LAST, PER_ANY, PER_ALL, PER_LIST, PER_NAME,
                 PER_FULLNAME, PER_NAME_LIST, PER_FULLNAME_LIST),
    'action': (ACTION_COUNT, ACTION_STORE, ACTION_TRUE, ACTION_FALSE),
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


def check_parser_conf(rconf, key, parser):
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
            elif option in CHOICES:
                if value not in CHOICES[option]:
                    raise ResultError(
                        "Option '{}' in result parser for key '{}' has a "
                        "value of '{}', but it must be one of '{}'"
                        .format(option, key, value, CHOICES[option]))

    if found_deferred:
        # We can't continue checking from this point if anything was deferred.
        return

    if (key == 'result'
            and action not in (ACTION_TRUE,
                               ACTION_FALSE)
            and per_file not in (PER_FIRST, PER_LAST,
                                 PER_ANY, PER_ALL)):
        raise ResultError(
            "Result parser has key 'result', but must store a "
            "boolean. Use action 'first' or 'last', along with a "
            "per_file setting of 'first', 'last', 'any', or 'all'")

    try:
        parser.check_args(**rconf)
    except ResultError as err:
        raise ResultError(
            "Key '{}': {}".format(key, err.args[0]))


class ResultParser(IPlugin.IPlugin):
    """Base class for creating a result parser plugin. These are essentially
a callable that implements operations on the test or test files. The
arguments for the callable are provided automatically via the test
config. The doc string of result parser classes is used as the user help
text for that class, along with the help from the config items."""

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, description, defaults=None,
                 config_elems=None, validators=None, open_mode='r',
                 priority=PRIO_COMMON):
        """Initialize the plugin object

:param str name: The name of this plugin.
:param str description: A short description of this result parser.
:param Union[str, None] open_mode: How to open each file handed to the parser.
    None denotes that a path rather than a file object is expected.
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

        if validators is not None:
            for key, val in validators.items():
                if not (isinstance(val, tuple) or
                        callable(val)):
                    raise RuntimeError(
                        "Validator for key {} in result parser {} at {} must "
                        "be a tuple or a function."
                        .format(key, name, self.path)
                    )
        self.validators = {} if validators is None else validators

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
                    "a default or choices (use the defaults or choices"
                    "argument for the result_parser init). Problem found "
                    "in {} in result parser at {}"
                    .format(elem, self.path)
                )

            if elem is MATCHES_ELEM:
                self.validators['match_type'] = MATCH_CHOICES
                if 'match_type' not in self.defaults:
                    self.defaults['match_type'] = MATCH_FIRST

        self.config_elems = config_elems
        self.priority = priority
        self.open_mode = open_mode

        super().__init__()

    def __call__(self, test, file, **kwargs):
        """This is where the result parser is actually implemented.

:param pavilion.test_run.TestRun test: The test run object.
:param file: This will be a file object or a string, depending on the
    parser's 'open_mode' setting in __init__.
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
:raises ResultParserError: When bad arguments are given.
"""

        # The presence or absence of needed args should be enforced by
        # setting 'required' in the yaml_config config items.
        args = self.defaults.copy()
        for key, val in kwargs.items():
            if val is None or (key in args and val == []):
                continue
            args[key] = kwargs[key]
        kwargs = args

        for key in ('action', 'per_file', 'files'):
            if key not in kwargs:
                raise RuntimeError(
                    "Result parser '{}' missing required attribute '{}'. These "
                    "are validated at the config level, so something is "
                    "probably wrong with plugin."
                    .format(self.name, key)
                )

            # The parser plugins don't know about these keys, as they're
            # handled at a higher level.
            del kwargs[key]

        for key, validator in self.validators.items():
            if isinstance(validator, tuple):
                if kwargs[key] not in validator:
                    raise ResultError(
                        "Invalid value for option '{}'. "
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

        return self._check_args(**kwargs)

    KEY_REGEX_STR = r'^[a-zA-Z0-9_-]+$'

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

        config_items = [
            yc.StrElem(
                "action",
                help_text=(
                    "What to do with parsed results.\n"
                    "  {STORE} - Just store the result (default).\n"
                    "  {TRUE} - Store True if there was a result.\n"
                    "  {FALSE} - Store True for no result.\n"
                    "  {COUNT} - Count the number of results.\n"
                    .format(
                        STORE=ACTION_STORE,
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
                    "  {FULLNAME} - Store the results on a per file "
                    "basis under results['fn'][<filename>][<key>]\n"
                    "  {NAME} - As '{FULLNAME}', except use the "
                    "filename minus extension (foo.bar.log -> foo.bar), and"
                    "store under the results['n'][<name>][<key>]\n"
                    "  {FULLNAME_LIST} - Save the matching file names, rather\n"
                    "than the parsed values, in a list.\n"
                    "  {NAME_LIST} - As '{FULLNAME_LIST}' except store the \n"
                    "filenames minus the extension.\n"
                    "  {LIST} - Merge all each result and result list "
                    "into a single list.\n"
                    "  {ALL} - Use only with the 'store_true' or "
                    "'store_false' action. Set true if all files had a "
                    "true result. Note that 0 is a false result.\n"
                    "  {ANY} - As '{ALL}', but set true if any file had"
                    "a true result.\n"
                    .format(
                        FIRST=PER_FIRST,
                        LAST=PER_LAST,
                        FULLNAME=PER_FULLNAME,
                        NAME=PER_NAME,
                        NAME_LIST=PER_NAME_LIST,
                        FULLNAME_LIST=PER_FULLNAME_LIST,
                        LIST=PER_LIST,
                        ALL=PER_ALL,
                        ANY=PER_ANY))
            ),
        ]

        config_items.extend(self.config_elems)
        return config_items

    @property
    def path(self):
        """The path to the file containing this result parser plugin."""

        return inspect.getfile(self.__class__)

    def doc(self):
        """Return documentation on this result parser."""

        def wrap(text: str, indent=0):

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

        for arg in self.config_elems:
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
do this in unittests.
"""

        # Remove the section from the config.
        file_format.TestConfigLoader.remove_result_parser_config(self.name)

        # Remove from list of available result parsers.
        del _RESULT_PARSERS[self.name]


def parse_results(test, results: Dict,
                  log: Callable[..., None] = None) -> None:
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

    if log is None:
        def log(*_, **__):
            """Drop the logs."""

    log("Starting result parsing.")

    parser_configs = test.config['result_parse']

    log("Got result parser configs:")
    log(pprint.pformat(parser_configs))
    log("---------------")

    # A list of keys with duplicates already reported on, so we don't
    # report such errors multiple times.
    errors = []

    # Get the results for each of the parsers specified.
    for parser_name in parser_configs.keys():
        # This is almost guaranteed to work, as the config wouldn't
        # have validated otherwise.
        parser = get_plugin(parser_name)

        defaults = parser_configs[parser_name].get(DEFAULT_KEY, {})

        log("Parsing results for parser {}".format(parser_name), lvl=1)

        # Each parser has a list of configs. Process each of them.
        for key, rconf in parser_configs[parser_name].items():
            log("Parsing value for key '{}'".format(key), lvl=2)

            rconf = set_parser_defaults(rconf, defaults)

            # Grab these for local use.
            action_name = rconf['action']
            action = ACTIONS[action_name]
            globs = rconf['files']

            per_file = rconf['per_file']

            # These config items are used here, but not expected by the
            # parsers themselves.
            args = rconf.copy()

            try:
                parser_args = parser.check_args(**args)
            except ResultError as err:
                errors.append({
                    'result_parser': parser_name,
                    'file':          str(parser.path),
                    'key':           key,
                    'msg':           err.args[0]})
                continue

            # The per-file results for this parser
            presults = OrderedDict()

            log("Looking for files that match file globs: {}".format(globs),
                lvl=2)

            # Find all the files we'll be parsing.
            paths = []
            for file_glob in globs:
                if not file_glob.startswith('/'):
                    file_glob = '{}/build/{}'.format(test.path, file_glob)

                for path in glob.glob(file_glob):
                    paths.append(Path(path))

            if not paths:
                log("No matching files found.")
                errors.append(
                    "File globs {} for key {} found no files."
                    .format(globs, key))
                continue

            log("Found {} matching files.".format(len(paths)))
            log("Results will be stored with action '{}'".format(action_name))

            # Apply the result parser to each file we're parsing.
            # Handle the results according to the 'action' config attribute.
            for path in paths:
                log("Parsing for file '{}':".format(path.as_posix()), lvl=3)
                try:
                    if parser.open_mode is None:
                        res = parser(test, path, **parser_args)
                    else:
                        with path.open(parser.open_mode) as file:
                            res = parser(test, file, **parser_args)

                    log("Raw parse result: '{}'".format(res))

                except (IOError, PermissionError, OSError) as err:
                    log("Error reading file: {}".format(err))
                    errors.append({
                        'result_parser': parser_name,
                        'file': str(path),
                        'key': key,
                        'msg': "Error reading file: {}".format(err)})
                    continue
                except Exception as err:  # pylint: disable=W0703
                    log("UnexpectedError: {}".format(err))
                    errors.append({
                        'result_parser': parser_name,
                        'file': str(path),
                        'key': key,
                        'msg': "Unexpected Error: {}".format(err)})
                    continue

                # The result key is always true/false. It's ACTION_TRUE by
                # default.
                if (key == 'result' and
                        action_name not in (ACTION_FALSE, ACTION_TRUE)):
                    action_name = ACTION_TRUE
                    log("Forcing action to '{}' for the 'result' key.")

                # We'll deal with the action later.
                presults[path] = res
                log("Stored value '{}' for file '{}'"
                    .format(presults[path], path.name))

            log("Results for each found files:", lvl=2)
            for res_path, res_value in presults.items():
                if res_path.parent == test.build_path:
                    res_path = res_path.name
                else:
                    res_path = res_path.as_posix()
                log(' - {}: {}'.format(res_path, res_value))

            log("Handling results for key '{}' on a per-file basis with "
                "per_file setting '{}'".format(key, per_file))


            presults_list = []

            class ListDict(dict):
                """Ok, this is madness, but setting an item in this
                dict actually just extends the list in our actual
                results dict."""

                def __setitem__(self, key, value):
                    presults_list.append(value)

            list_dict = ListDict()
            [actiofor key, value ]

            # Combine the results of all the files given according to the
            # 'per_file' config attribute.
            if per_file in (PER_FIRST, PER_LAST):

            elif per_file in (PER_NAME, PER_FULLNAME):
                # Store in results under the 'stem' or 'name' key as a dict
                # where each name/stem has a dict with this key and the value.

                per_key = 'n' if per_file == PER_NAME else 'fn'

                if per_key not in results:
                    results[per_key] = dict()

                per_dict = results[per_key]  # type: dict

                for fname, value in presults.items():
                    if per_file == PER_FULLNAME:
                        name = str(fname.name)
                    else:
                        name = str(fname.stem)

                    if name not in per_dict:
                        per_dict[name] = dict()

                    action(per_dict[name], key, value)

                log("Saved results under '{}' for each file {}."
                    .format(per_key, per_file))
                log(pprint.pformat(per_dict))

            elif per_file == PER_LIST:
                # Simply put all results together in a list. Values that
                # already are a list extend that list.
                # None values are ignored.

                results[key] = list()


                dummy = ListDict()
                for value in presults.values():
                    action(dummy, key, value)

                log("Saved results for all files as a list:\n{}"
                    .format(results[key]))

            elif per_file in (PER_FULLNAME_LIST, PER_NAME_LIST):

                matches = []
                for fname, value in presults.items():
                    fname = fname.stem if PER_NAME_LIST else fname.name
                    dummy = {}
                    action(dummy, key, value)
                    if dummy[key] not in EMPTY_VALUES:
                        matches.append(fname)

                log("Saved the file name for files that matched.")
                log(pprint.pformat(results[key]))

            elif per_file == PER_ALL:
                results[key] = all(presults.values())

                log("Saved the result of all() across all matched files: '{}'"
                    .format(results[key]))
            elif per_file == PER_ANY:
                results[key] = any(presults.values())
                log("Saved the result of any() across all matched files: '{}'"
                    .format(results[key]))
            else:
                raise ResultError("Invalid per_file value for result parser "
                                  "'{}' - {}"
                                  .format(parser_name, per_file))

        results['pav_result_errors'].extend(errors)
