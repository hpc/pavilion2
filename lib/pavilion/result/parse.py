"""Functions to handle the collection of results using result parsers."""
from collections import defaultdict, OrderedDict
import glob
import inspect
import pprint
import re
import traceback
from io import StringIO
from multiprocessing import Pool
from pathlib import Path
from typing import List, Union, Dict, Any, TextIO, Pattern, Tuple, NewType

from pavilion.result_parsers import ResultParser, get_plugin
from pavilion.utils import IndentedLog
from .base import RESULT_ERRORS
from .common import ResultError
from .options import (PER_FILES, ACTIONS, MATCH_CHOICES, per_first,
                      ACTION_TRUE, ACTION_FALSE)


class ParseErrorMsg:
    """Standardized result parser error message."""

    def __init__(self, parser: ResultParser, msg: str, key: str = '<unknown>',
                 path: str = None):
        """Initialize the message.
        :param key: The key being parsed when the error occured.
        :param parser: The result parser being handled.
        :param msg: The error message.
        :param path: The file being parsed.
        """

        self.key = key
        self.parser = parser
        self.path = path
        self.msg = msg

    def __str__(self):
        if self.path:
            return (
                "Error parsing for key '{key}' under the result parser "
                "'{parser_name}' for file {file_path}.\n"
                "Parser module path: {module_path}\n{msg}".format(
                    key=self.key,
                    parser_name=self.parser.name,
                    file_path=self.path,
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


DEFAULT_KEY = '_defaults'


class KeySet:
    """Everything needed to parse a result key from a file."""
    def __init__(self, parser_name: str, key: str, config: dict):
        self.parser_name = parser_name
        self.key = key
        self.config = config


ProcessFileArgs = NewType('ProcessFileArgs', Tuple[Path, List[KeySet]])


def parse_results(pav_cfg, test, results: Dict, log: IndentedLog) -> None:
    """Parse the results of the given test using all the result parsers
configured for that test.

- Find the result parser
- Parse results for each found file via the 'files' attr.
- Save those results (for each file) according to the 'action' attr.
- Combine file results into a single object with the 'per_file' attr
  and add them to the results dict.

:param pav_cfg: The pavilion config
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

    # For each file to parse, the list of keys and parsing configurations
    file_key_sets = defaultdict(lambda: [])
    # For each key, the list of files to parse in the order found.
    file_order = defaultdict(lambda: [])
    # Per-file values by key.
    per_file = {}
    # Action values by key
    actions = {}

    for parser_name in parser_configs.keys():
        parser = get_plugin(parser_name)
        defaults = parser_configs[parser_name].get(DEFAULT_KEY, {})

        for key, rconf in parser_configs[parser_name].items():

            rconf = parser.set_parser_defaults(rconf, defaults)

            per_file[key] = rconf['per_file']
            actions[key] = rconf['action']

            for file_glob in rconf['files']:
                base_glob = file_glob
                if not file_glob.startswith('/'):
                    file_glob = '{}/build/{}'.format(test.path, file_glob)

                paths_found = glob.glob(file_glob)
                # I don't know why this was reversed.
                #paths_found.reverse()
                for path in paths_found:
                    path = Path(path)
                    # Only add each key/path once
                    if path not in file_order[key]:
                        file_order[key].append(path)
                        file_key_sets[path].append(KeySet(parser_name, key, rconf))

                if not paths_found:
                    log("Setting a non match result for unmatched glob '{}'"
                        .format(file_glob))
                    results[RESULT_ERRORS].append(
                        "No files found for file glob '{}' under key '{}'"
                        .format(base_glob, key))

    file_tuples = [ProcessFileArgs((file, parse_tuples))
                   for file, parse_tuples in file_key_sets.items()]
    # Start result parsing from each file in a separate thread.
    max_cpus = min(len(file_key_sets), pav_cfg['max_cpus'])
    # Don't fork if there's only one file to muck with.
    if max_cpus > 1:
        with Pool() as pool:
            mapped_results = pool.map(process_file, file_tuples)
    else:
        mapped_results = map(process_file, file_tuples)

    errors = []

    # Organize the results by key and file.
    filed_results = defaultdict(lambda: {})
    ordered_filed_results = defaultdict(lambda: OrderedDict())
    for result in mapped_results:
        parsed_results, log = result

        for key, path, value in parsed_results:
            if key == RESULT_ERRORS:
                errors.append(value)
            else:
                filed_results[key][path] = value

    # Generate the dict of filed results, this time in the order the files were given.
    for key in file_order:
        for path in file_order[key]:
            if key in filed_results and path in filed_results[key]:
                ordered_filed_results[key][path] = filed_results[key][path]

    for key, per_file_name in per_file.items():
        per_file_func = PER_FILES[per_file_name]  # type: per_first

        presults = ordered_filed_results[key]

        try:
            errors = per_file_func(
                results=results,
                key=key,
                file_vals=presults,
                action=ACTIONS[actions[key]]
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
            return ParseErrorMsg(parser, msg, key, file=globs)

        return None





def process_file(args: Tuple[Path, List[Tuple[str, str, dict]]]) -> \
        (List[(str, Path, Any)], List[str]):
    """asdf"""
    path, parse_tuples = args

    log = IndentedLog()

    file_results = []

    with path.open() as file:
        # If we have to go through the file more than once, just read the whole thing
        # into memory.
        if len(parse_tuples) > 1:
            file = StringIO(file.read())

        for parser_name, key, rconf in parse_tuples:
            parser = get_plugin(parser_name)

            # Seek to the beginning of the file for each parse action.
            file.seek(0)

            # Get the result for a single key and file.
            result = parse_result(key, rconf, file, parser, log)

            if isinstance(result, ParseErrorMsg):
                result.path = path
                file_results.append((RESULT_ERRORS, path, str(result)))
            else:
                file_results.append((key, path, result))

    return file_results, log


def parse_result(key: str, parser_cfg: Dict, file: TextIO,
                 parser: ResultParser, log: IndentedLog) \
        -> Union[ParseErrorMsg, str]:
    """Use a result parser and it's settings to parse a single value from a file.

    :param key: The key we're parsing.
    :param parser_cfg: The parser config dict.
    :param file: The file from which to extract the result.
    :param parser: The result parser plugin object.
    :param log: The result log callback.
    :returns: The parsed value
    """

    # Grab these for local use.
    action_name = parser_cfg['action']

    match_idx = MATCH_CHOICES.get(parser_cfg['match_select'],
                                  parser_cfg['match_select'])
    match_idx = int(match_idx) if match_idx is not None else None

    # Compile the regexes for finding the appropriate lines on which to
    # call the result parser.
    match_cond_rex = [re.compile(cond) for cond in parser_cfg['preceded_by']]
    match_cond_rex.append(re.compile(parser_cfg['for_lines_matching']))

    # The result key is always true/false. It's ACTION_TRUE by
    # default.
    if key == 'result' and action_name not in (ACTION_FALSE, ACTION_TRUE):
        action_name = ACTION_TRUE
        log("Forcing action to '{}' for the 'result' key.")

    try:
        parser_args = parser.check_args(**parser_cfg.copy())
    except ResultError as err:
        return ParseErrorMsg(parser, err.args[0], key)

    log("Results will be stored with action '{}'".format(action_name))
    log.indent = 3

    try:
        res = extract_result(
            file=file,
            parser=parser, parser_args=parser_args,
            pos_regexes=match_cond_rex,
            match_idx=match_idx,
            log=log,
        )

        # Add the key information if there was an error.
        if isinstance(res, ParseErrorMsg):
            res.key = key

        return res
    except OSError as err:
        msg = "Error reading file: {}".format(err)
        log(msg)
        return ParseErrorMsg(parser, msg, key)
    except Exception as err:  # pylint: disable=W0703
        msg = "UnexpectedError: {}".format(err)
        log(msg)
        return ParseErrorMsg(parser, msg, key)


def extract_result(file: TextIO, parser: ResultParser, parser_args: dict,
                   match_idx: Union[int, None],
                   pos_regexes: List[Pattern],
                   log: IndentedLog) -> Any:
    """Parse a result from a result file.

    :return: A list of all matching results found. Will be cut short if
        we only need the first result.
    """

    matches = []

    next_pos = advance_file(file, pos_regexes)

    while next_pos is not None:
        if pos_regexes[-1].pattern != '':
            log("Found potential match at pos {} in file."
                .format(file.tell()))
        try:
            res = parser(file, **parser_args)
        except Exception as exc:
            log("Error calling result parser {}.".format(parser.name))
            log(traceback.format_exc(exc))
            return ParseErrorMsg(parser, "Exception when calling result parser. "
                                         "See result log for full error.")

        file.seek(next_pos)

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


def advance_file(file: TextIO, conds: List[Pattern]) -> Union[int, None]:
    """Find the next sequence of lines that satisfy, one-to-one and in order,
    the list of condition regex. Then rewind the file to the start of
    the last of these matched lines. It returns the position of the
    start of next line (from which point we will presumably look for
    matches again).

    Given a file that contains:

    .. code-block: text

         data1
         data2
         sweet spot
         data3
         data4

    and conditions (as compiled re's) ``['^data\\d+', '^sweet']``

    This would advance the file to the beginning of the 'sweet spot' line,
    and return the pos for the start of the data3 line.
    If called again on the same file with the same conditions, this would
    return None, as not further matching positions exist.

    :param file: The file to search, presumably pointing to the start of
        a line. The file cursor will be advanced to the start of the last
        of a sequence of lines that satisfy the conditions (or the end of
        the file if no such position exists).
    :param conds:
    :return: The position of the start of the line after the one advanced
        to. If None, then no matched position was found.
    """

    # Tracks the file pos that would follow a set of matches.
    next_pos = file.tell()
    # Tracks the line after the first matched line in the sequence
    # of matches. If we match 3/5 conditions, we'll want to rewind
    # to the start of the second of those lines and start matching again.
    restart_pos = None
    # The current condition we're comparing against.
    cond_idx = 0
    # After matching against all conditions against lines, we
    # rewind the file to the start of the last matched line. (this pos)
    rewind_pos = None

    while cond_idx < len(conds):
        rewind_pos = next_pos

        line = file.readline()

        # We're out of file, but haven't matched all conditions.
        if line == '':
            return None

        next_pos = file.tell()
        # We'll restart at this line on if not all conditions match.
        if cond_idx == 0:
            restart_pos = next_pos

        # When we match a condition, advance to the next one, otherwise reset.
        if conds[cond_idx].search(line) is not None:
            cond_idx += 1
        else:
            cond_idx = 0
            file.seek(restart_pos)

    # Go back to the start of the last matched line.
    file.seek(rewind_pos)

    return next_pos
