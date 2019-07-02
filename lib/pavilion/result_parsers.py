import glob
import inspect
import logging
import re
from collections import OrderedDict
from pathlib import Path

import yaml_config as yc
from yapsy import IPlugin
from .test_config import format
from .test_config import variables

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

    global _RESULT_PARSERS

    # Remove all existing parsers.
    for parser in list(_RESULT_PARSERS.values()):
        parser.deactivate()


class ResultParserError(RuntimeError):
    pass


# These are the base result constants
PASS = 'PASS'
FAIL = 'FAIL'
ERROR = 'ERROR'

ACTION_STORE = 'store'
ACTION_TRUE = 'store_true'
ACTION_FALSE = 'store_false'
ACTION_COUNT = 'count'

PER_FIRST = 'first'
PER_LAST = 'last'
PER_FULLNAME = 'fullname'
PER_NAME = 'name'
PER_LIST = 'list'
PER_ANY = 'any'
PER_ALL = 'all'

MATCH_FIRST = 'first'
MATCH_LAST = 'last'
MATCH_ALL = 'all'

# This is to use in any result parser plugin that can match multiple items.
# It's provided here for consistency between plugins.
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


class ResultParser(IPlugin.IPlugin):
    """Base class for creating a result parser plugin. These are essentially
    a callable that implements operations on the test or test files. The
    arguments for the callable are provided automatically via the test
    config. The doc string of result parser classes is used as the user help
    text for that class, plus the help on the config items."""

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, open_mode='r', priority=PRIO_COMMON):
        """Initialize the plugin object
        :param str name: The name of this plugin.
        :param open_mode: How to open each file handed to the parser.
        :param int priority: The priority of this plugin, compared to plugins
            of the same name. Higher priority plugins will supersede others.
        """

        self.name = name
        self.priority = priority
        self.open_mode = open_mode

        super().__init__()

    def __call__(self, test, file, **kwargs):
        """This is where the result parser is actually implemented.
        :param pavilion.pav_test.PavTest test: The test run object.
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
        raises ResultParserError: If there are bad arguments.
        """

        pass

    def check_args(self, **kwargs):
        """Check the arguments for any errors at test kickoff time, if they
        don't contain deferred variables. We can't check tests with
        deferred args. On error, should raise a ResultParserError.
        :param dict args: The arguments from the config.
        """

        # The presence or absence of needed args should be enforced by
        # setting 'required' in the yaml_config config items.

        # Don't check args if they have deferred values.
        if variables.VariableSetManager.has_deferred(kwargs):
            return

        self._check_args(**kwargs)

    KEY_REGEX_STR = r'^[a-zA-Z0-9_-]+$'

    def get_config_items(self):
        """Get the config for this result parser. This should be a list of
        yaml_config.ConfigElement instances that will be added to the test
        config format at plugin activation time. The simplest format is a
        list of yaml_config.StrElem objects, but any structure is allowed
        as long as the leaf elements are StrElem type.

        The config values will be passed as the keyword arguments to the
        result parser when it's run and when it's arguments are checked. Those
        values listed below are handled by the base class, and won't be passed,
        however.

        Example:
            config_items = super().get_config_items()
            config_items.append(
                yaml_config.StrElem('token', default='PASSED',
                    help="The token to search for in the file."
            )
            return config_items
        """

        return [
            yc.RegexElem("key", required=True,
                         regex=self.KEY_REGEX_STR,
                         help_text="The key value in the result json for this"
                                   "result component."),
            yc.StrElem(
                "action",
                required=True, default="store",
                choices=[
                    ACTION_STORE,
                    ACTION_TRUE,
                    ACTION_FALSE,
                    ACTION_COUNT
                ],
                help_text="What to do with parsed results.\n"
                          "  {STORE} - Just store the result (default).\n"
                          "  {TRUE} - Store True if there was a result.\n"
                          "  {FALSE} - Store True for no result.\n"
                          "  {COUNT} - Count the number of results.\n"
                          .format(
                                STORE=ACTION_STORE,
                                TRUE=ACTION_TRUE,
                                FALSE=ACTION_FALSE,
                                COUNT=ACTION_COUNT)
            ),
            # The default for the file is handled by the test object.
            yc.ListElem(
                "files",
                sub_elem=yc.StrElem(),
                defaults=['../run.log'],
                help_text="Path to the file/s that this result parser "
                          "will examine. Each may be a file glob,"
                          "such as '*.log'"),
            yc.StrElem(
                "per_file",
                default=PER_FIRST,
                choices=[
                    PER_FIRST,
                    PER_LAST,
                    PER_FULLNAME,
                    PER_NAME,
                    PER_LIST,
                    PER_ANY,
                    PER_ALL,
                ],
                help_text="How to save results for multiple file matches.\n"
                          "  {FIRST} - The result from the first file with a "
                          "result. (default)\n"
                          "  {LAST} - As '{FIRST}', but reversed.\n"
                          "  {FULLNAME} - Store the results on a per file "
                          "basis under results[<filename>][<key>]\n"
                          "  {NAME} - As '{FULLNAME}', except use the "
                          "filename minux extension (foo.bar.log -> foo.bar)\n"
                          "  {LIST} - Merge all each result and result list "
                          "into a single list.\n"
                          "  {ALL} - Use only with the 'store_true' or "
                          "'store_false' action. Set true if all files had a "
                          "true result.\n"
                          "  {ANY} - As '{ALL}', but set true if any file had"
                          "a true result.\n"
                          .format(
                            FIRST=PER_FIRST,
                            LAST=PER_LAST,
                            FULLNAME=PER_FULLNAME,
                            NAME=PER_NAME,
                            LIST=PER_LIST,
                            ALL=PER_ALL,
                            ANY=PER_ANY)
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

        config_items = self.get_config_items()

        format.TestConfigLoader.add_result_parser_config(self.name,
                                                         config_items)
        global _RESULT_PARSERS

        if self.name in _RESULT_PARSERS:
            other = _RESULT_PARSERS[self.name]
            if self.priority > other.priority:
                LOGGER.info("Result parser '{}' at {} is superseded by {}."
                            .format(self.name, other.path, self.path))
                _RESULT_PARSERS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info("Result parser '{}' at {} is ignored in lieu of "
                            "{}.".format(self.name, self.path, other.path))
            else:
                raise RuntimeError("Result parser conflict. Parser '{}' at {}"
                                   "has the same priority as {}"
                                   .format(self.name, other.path, self.path))
        else:
            _RESULT_PARSERS[self.name] = self

    def deactivate(self):

        # Remove the section from the config.
        format.TestConfigLoader.remove_result_parser_config(self.name)

        # Remove from list of available result parsers.
        del _RESULT_PARSERS[self.name]


RESERVED_RESULT_KEYS = [
    'name',
    'id',
    'created',
    'started',
    'finished',
    'duration',
]


def check_args(parser_configs):
    """Make sure the result parsers are sensible.
     - No duplicated key names.
     - Sensible keynames: /[a-z0-9_-]+/
     - No reserved key names.

    :raises PavTestError: When a config breaks the rules.
    """

    key_names = []

    for rtype in parser_configs:
        for rconf in parser_configs[rtype]:
            key = rconf.get('key')

            if key is None:
                raise RuntimeError(
                    "ResultParser config for parser '{}' missing key. "
                    "This is an error with the result parser itself,"
                    "probably.".format(rtype)
                )

            regex = re.compile(ResultParser.KEY_REGEX_STR)

            if regex.match(key) is None:
                raise RuntimeError(
                    "ResultParser config for parser '{}' has invalid key."
                    "Key does not match the required format. "
                    "This is an error with the result parser itself, "
                    "probably.".format(rtype)
                )

            if key in key_names:
                raise ResultParserError(
                    "Duplicate result parser key name '{}' under parser '{}'"
                    .format(key, rtype)
                )

            if key in RESERVED_RESULT_KEYS:
                raise ResultParserError(
                    "Result parser key '{}' under parser '{}' is reserved."
                    .format(key, rtype)
                )

            key_names.append(key)

            parser = get_plugin(rtype)
            # The parser's don't know about the 'key' config item.
            args = rconf.copy()
            for key in ('key', 'action', 'per_file', 'files'):
                del args[key]

            parser.check_args(**args)


def parse_results(test, results):
    """
    :param pavilion.pav_test.PavTest test: The pavilion test run to gather
    results for.
    :param dict results: The dictionary of default result values.
    :return: The final results dictionary.
    """

    parser_configs = test.config['results']

    # A list of keys with duplicates already reported on, so we don't
    # report such errors multiple times.
    per_error_keys = []
    errors = []

    # Get the results for each of the parsers specified.
    for parser_name in parser_configs.keys():
        # This is almost guaranteed to work, as the config wouldn't
        # have validated otherwise.
        parser = get_plugin(parser_name)

        # Each parser has a list of configs. Process each of them.
        for rconf in parser_configs[parser_name]:

            # Grab these for local use.
            action = rconf['action']
            key = rconf['key']
            globs = rconf['files']
            per_file = rconf['per_file']

            try:
                # These config items are used here, but not expected by the
                # parsers themselves.
                args = rconf.copy()
                for k in 'key', 'files', 'action', 'per_file':
                    del args[k]
            except KeyError as err:
                raise ResultParserError(
                    "Invalid config for result parser '{}': {}"
                    .format(parser_name, err))

            # The per-file results for this parser
            presults = OrderedDict()

            # Find all the files we'll be parsing.
            paths = []
            for file_glob in globs:
                if not file_glob.startswith('/'):
                    file_glob = '{}/build/{}'.format(test.path, file_glob)

                for path in glob.glob(file_glob):
                    paths.append(Path(path))

            # Apply the result parser to each file we're parsing.
            # Handle the results according to the 'action' config attribute.
            for path in paths:
                try:
                    if parser.open_mode is None:
                        res = parser(test, path, **args)
                    else:
                        with path.open(parser.open_mode) as file:
                            res = parser(test, file, **args)
                except (IOError, PermissionError, OSError) as err:
                    errors.append({
                        'result_parser': parser_name,
                        'file': path,
                        'key': key,
                        'msg': "Error reading file: {}".format(path, err)})
                    continue
                except Exception as err:
                    errors.append({
                        'result_parser': parser_name,
                        'file': path,
                        'key': key,
                        'msg': "Unexpected Error: {}".format(err)})
                    continue

                # The result key is always true/false. It's ACTION_TRUE by
                # default.
                if (key == 'result' and
                        action not in (ACTION_FALSE, ACTION_TRUE)):
                    action = ACTION_TRUE

                if action == ACTION_STORE:
                    # Simply store the whole result.
                    presults[path] = res
                elif action == ACTION_TRUE:
                    # Any value that evaluates to python True is True
                    presults[path] = bool(res)
                elif action == ACTION_FALSE:
                    # Any value that evaluates to python True is False
                    presults[path] = not bool(res)
                elif action == ACTION_COUNT:
                    # Count the returned items.
                    if isinstance(res, (list, tuple)):
                        presults[path] = len(res)
                    elif res is not None:
                        presults[path] = 1
                    else:
                        presults[path] = 0
                else:
                    raise ResultParserError(
                        "Invalid action for result parser '{}': {}"
                        .format(parser_name, action))

            # Combine the results of all the files given according to the
            # 'per_file' config attribute.
            if per_file in (PER_FIRST, PER_LAST):
                # Per first and last find the first non-empty result
                # from all the found files, and uses that.
                # Empty lists (not tuples!) and None are considered empty.
                # See the result parser docs.

                presults = presults.values()

                # Do this backwards, if we want the last one.
                if per_file == PER_LAST:
                    presults = reversed(presults)

                results[key] = None

                for pres in presults:
                    if pres == [] or pres is None:
                        continue

                    # Store the first non-empty item.
                    results[key] = pres

            elif per_file in (PER_NAME, PER_FULLNAME):
                # Store in results under the 'stem' or 'name' key as a dict
                # where each name/stem has a dict with this key and the value.

                if per_file not in results:
                    results[per_file] = dict()

                per_dict = results[per_file]  # type: dict

                for fname, value in presults.items():
                    if per_file == PER_FULLNAME:
                        name = fname.name
                    else:
                        name = fname.stem

                    if name not in per_dict:
                        per_dict[name] = dict()

                    if (key in per_dict[name] and
                            name not in per_error_keys):
                        errors.append({
                            'result_parser': parser_name,
                            'file': fname,
                            'key': key,
                            'msg': "Duplicate file key '{}' matched by {}"
                                   .format(name, per_file)})
                        continue

                    per_dict[name][key] = value

            elif per_file == PER_LIST:
                # Simply put all results together in a list. Values that
                # already are a list extend that list.
                # None values are ignored.

                result_list = list()

                for value in presults.values():
                    if isinstance(value, list):
                        result_list.extend(value)
                    elif value is not None:
                        result_list.append(value)

                results[key] = result_list

            elif per_file == PER_ALL:
                results[key] = all(presults.values())
            elif per_file == PER_ANY:
                results[key] = any(presults.values())
            else:
                raise ResultParserError("Invalid per_file value: {}"
                                        .format(per_file))

    if results['result'] not in (PASS, FAIL):
        if results['result'] is True:
            results['result'] = PASS
        elif results['result'] is False:
            results['result'] = FAIL
        else:
            errors.append({
                'result_parser': None,
                'file': None,
                'key': 'result',
                'msg': "A result parser set the 'result' key to {}, but it must"
                       "be strictly set to True/False (PASS/FAIL)."
                       .format(results['result'])
            })

    results['errors'] = errors

    return results
