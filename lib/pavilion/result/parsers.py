"""This module contains the ResultParser plugin class, as well functions
to process result parser configurations defined by a test run."""

import glob
import inspect
import logging
import pprint
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Callable

import yaml_config as yc
from pavilion.result.base import ResultError
from pavilion.test_config import file_format
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


ACTION_STORE = 'store'
ACTION_TRUE = 'store_true'
ACTION_FALSE = 'store_false'
ACTION_COUNT = 'count'

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

MATCHES_ELEM = yc.StrElem(
    "match_type",
    default=MATCH_FIRST,
    choices=[
        MATCH_FIRST,
        MATCH_LAST,
        MATCH_ALL,
    ],
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


class ResultParser(IPlugin.IPlugin):
    """Base class for creating a result parser plugin. These are essentially
a callable that implements operations on the test or test files. The
arguments for the callable are provided automatically via the test
config. The doc string of result parser classes is used as the user help
text for that class, along with the help from the config items."""

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, description, open_mode='r', priority=PRIO_COMMON):
        """Initialize the plugin object

:param str name: The name of this plugin.
:param str description: A short description of this result parser.
:param Union[str, None] open_mode: How to open each file handed to the parser.
    None denotes that a path rather than a file object is expected.
:param int priority: The priority of this plugin, compared to plugins
    of the same name. Higher priority plugins will supersede others.
"""

        self.name = name
        self.description = description
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

    def _check_args(self, **kwargs):
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

    def check_args(self, **kwargs):
        """Check the arguments for any errors at test kickoff time, if they
don't contain deferred variables. We can't check tests with
deferred args. On error, should raise a ResultParserError.

:param dict kwargs: The arguments from the config.
:raises ResultParserError: When bad arguments are given.
"""

        # The presence or absence of needed args should be enforced by
        # setting 'required' in the yaml_config config items.

        kwargs = kwargs.copy()
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

        self._check_args(**kwargs)

    KEY_REGEX_STR = r'^[a-zA-Z0-9_-]+$'

    @staticmethod
    def get_config_items():
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

        return [
            yc.StrElem(
                "action",
                required=True, default="store",
                choices=[
                    ACTION_STORE,
                    ACTION_TRUE,
                    ACTION_FALSE,
                    ACTION_COUNT
                ],
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
                required=True,
                sub_elem=yc.StrElem(),
                defaults=['../run.log'],
                help_text="Path to the file/s that this result parser "
                          "will examine. Each may be a file glob,"
                          "such as '*.log'"),
            yc.StrElem(
                "per_file",
                default=PER_FIRST,
                required=True,
                choices=[
                    PER_FIRST,
                    PER_LAST,
                    PER_FULLNAME,
                    PER_NAME,
                    PER_NAME_LIST,
                    PER_FULLNAME_LIST,
                    PER_LIST,
                    PER_ANY,
                    PER_ALL,
                ],
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

    @property
    def path(self):
        """The path to the file containing this result parser plugin."""

        return inspect.getfile(self.__class__)

    def help(self):
        """Return a formatted help string for the parser."""

        return self.__doc__

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


NON_MATCH_VALUES = (None, [], False)
EMPTY_VALUES = (None, [])


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
    per_error_keys = []
    errors = []

    # Get the results for each of the parsers specified.
    for parser_name in parser_configs.keys():
        # This is almost guaranteed to work, as the config wouldn't
        # have validated otherwise.
        parser = get_plugin(parser_name)

        log("Parsing results for parser {}".format(parser_name), lvl=1)

        # Each parser has a list of configs. Process each of them.
        for key, rconf in parser_configs[parser_name].items():
            log("Parsing value for key '{}'".format(key), lvl=2)

            # Grab these for local use.
            action = rconf['action']
            globs = rconf['files']

            per_file = rconf['per_file']

            try:
                # These config items are used here, but not expected by the
                # parsers themselves.
                args = rconf.copy()
                for k in 'files', 'action', 'per_file':
                    del args[k]
            except KeyError as err:
                raise ResultError(
                    "Invalid config for result parser '{}': {}"
                    .format(parser_name, err))

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
            log("Results will be stored with action '{}'".format(action))

            # Apply the result parser to each file we're parsing.
            # Handle the results according to the 'action' config attribute.
            for path in paths:
                log("Parsing for file '{}':".format(path.as_posix()), lvl=3)
                try:
                    if parser.open_mode is None:
                        res = parser(test, path, **args)
                    else:
                        with path.open(parser.open_mode) as file:
                            res = parser(test, file, **args)
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
                        action not in (ACTION_FALSE, ACTION_TRUE)):
                    action = ACTION_TRUE
                    log("Forcing action to '{}' for the 'result' key.")

                if action == ACTION_STORE:
                    # Simply store the whole result.
                    presults[path] = res
                elif action == ACTION_TRUE:
                    # Any non-null/empty value is true
                    presults[path] = res not in NON_MATCH_VALUES
                elif action == ACTION_FALSE:
                    # Any null/empty value is false
                    presults[path] = res in NON_MATCH_VALUES
                elif action == ACTION_COUNT:
                    # Count the returned items.
                    if isinstance(res, (list, tuple)):
                        presults[path] = len(res)
                    elif res not in NON_MATCH_VALUES:
                        presults[path] = 1
                    else:
                        presults[path] = 0
                else:
                    raise ResultError(
                        "Invalid action for result parser '{}': {}"
                        .format(parser_name, action))

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

            # Combine the results of all the files given according to the
            # 'per_file' config attribute.
            if per_file in (PER_FIRST, PER_LAST):
                # Per first and last find the first non-empty result
                # from all the found files, and uses that.
                # Empty lists (not tuples!) and None are considered empty.
                # See the result parser docs.

                presults = list(presults.values())
                if not presults:
                    raise ResultError(
                        "No files found that matched {} for key '{}'. If "
                        "you're hoping no such files exist, use a 'per_file' "
                        "setting other than {} or {}."
                        .format(globs, key, PER_FIRST, PER_LAST))

                # Do this backwards, if we want the last one.
                if per_file == PER_LAST:
                    presults = reversed(presults)

                results[key] = presults[0]

                for pres in presults:
                    if pres in EMPTY_VALUES:
                        continue

                    # Store the first non-empty item.
                    results[key] = pres
                    break
                log("{}: Picked non-empty value '{}'"
                    .format(per_file, results[key]))

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

                    if (key in per_dict[name] and
                            name not in per_error_keys):
                        errors.append({
                            'result_parser': parser_name,
                            'file': str(fname),
                            'key': key,
                            'msg': "Duplicate file key '{}' matched by {}"
                                   .format(name, per_file)})
                        continue

                    per_dict[name][key] = value

                log("Saved results under '{}' for each file {}."
                    .format(per_key, per_file))
                log(pprint.pformat(per_dict))

            elif per_file == PER_LIST:
                # Simply put all results together in a list. Values that
                # already are a list extend that list.
                # None values are ignored.

                result_list = list()

                for value in presults.values():
                    if isinstance(value, list):
                        result_list.extend(value)
                    elif value not in EMPTY_VALUES:
                        result_list.append(value)

                results[key] = result_list

                log("Saved results for all files as a list:\n{}"
                    .format(results[key]))

            elif per_file == PER_NAME_LIST:
                # Get the name stems from the files that matched.
                results[key] = sorted([
                    fname.stem for fname, value in presults.items()
                    if value not in EMPTY_VALUES
                ])
                log("Saved the file name stems for files that matched.")
                log(pprint.pformat(results[key]))

            elif per_file == PER_FULLNAME_LIST:
                # Get the filenames from the files that matched.
                results[key] = sorted([
                    fname.name for fname, value in presults.items()
                    if value not in EMPTY_VALUES
                ])

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
