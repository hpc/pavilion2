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
from ..errors import ResultError
from .options import (PER_FILES, ACTIONS, MATCH_CHOICES, per_first,
                      ACTION_TRUE, ACTION_FALSE, MATCH_ALL, MATCH_UNIQ)


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


def parse_results(pav_cfg, test, results: Dict, base_log: IndentedLog) -> None:
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
:param base_log: The logging callable from 'result.get_result_logger'.
"""

    base_log("Starting result parsing.")

    log = IndentedLog()

    parser_configs = test.config['result_parse']

    log("Got result parser configs:")
    log.indent(pprint.pformat(parser_configs))
    log("---------------")

    # For each file to parse, the list of keys and parsing configurations
    file_key_sets = defaultdict(lambda: [])
    # For each key, the list of files to parse in the order found.
    file_order = defaultdict(lambda: [])
    # Per-file values by key.
    per_file = {}
    # Action values by key
    actions = {}

    # A list of encountered error messages.
    errors = []

    for parser_name in parser_configs.keys():
        parser = get_plugin(parser_name)

        for key, rconf in parser_configs[parser_name].items():
            defaults = parser_configs[parser_name].get(DEFAULT_KEY, {})
            rconf = parser.set_parser_defaults(rconf, defaults)

            per_file[key] = rconf['per_file']
            actions[key] = rconf['action']

            for file_glob in rconf['files']:
                base_glob = file_glob
                if not file_glob.startswith('/'):
                    file_glob = '{}/build/{}'.format(test.path, file_glob)

                paths_found = glob.glob(file_glob)
                # Globbing returns the paths in a backwards order
                paths_found.sort()
                for path in paths_found:
                    path = Path(path)
                    # Only add each key/path once
                    if path not in file_order[key]:
                        # Track the order in which files are read for each key
                        file_order[key].append(path)
                        # Add our argument set for this file, so we can process all
                        # keys for a given file together.
                        file_key_sets[path].append(KeySet(parser_name, key, rconf))

                if not paths_found:
                    log("Setting a non match result for unmatched glob '{}'"
                        .format(file_glob))
                    errors.append(
                        "No files found for file glob '{}' under key '{}'"
                        .format(base_glob, key))

    log("Found these files for each key.")
    log.indent(pprint.pformat(dict(file_order)))

    # Setup up the argument tuples for mapping to multiple processes.
    file_tuples = [ProcessFileArgs((file, parse_tuples))
                   for file, parse_tuples in file_key_sets.items()]

    # Start result parsing from each file in a separate thread.
    max_cpus = min(len(file_key_sets), pav_cfg['max_cpu'])
    # Don't fork if there's only one file to muck with.
    if max_cpus > 1:
        log("Processing results with {} processes.".format(max_cpus))
        with Pool(max_cpus) as pool:
            mapped_results = pool.map(process_file, file_tuples)
    else:
        log("Processing results in a single process.")
        mapped_results = map(process_file, file_tuples)

    # Organize the results by key and file.
    filed_results = defaultdict(lambda: {})
    ordered_filed_results = defaultdict(OrderedDict)
    for mresult in mapped_results:
        parsed_results, mlog = mresult

        log.indent(mlog)

        # Errors are returned under the RESULT_ERRORS key.
        for p_result in parsed_results:
            if p_result.key == RESULT_ERRORS:
                errors.append(p_result.value)
            else:
                filed_results[p_result.key][p_result.path] = p_result.value

    # Generate the dict of filed results, this time in the order the files were given.
    for key in file_order:
        for path in file_order[key]:
            if key in filed_results and path in filed_results[key]:
                ordered_filed_results[key][path] = filed_results[key][path]

    # Transform the results for each key according to the per-file and action
    # options.
    for key, per_file_name in per_file.items():
        per_file_func = PER_FILES[per_file_name]  # type: per_first
        action_name = actions[key]
        presults = ordered_filed_results[key]

        try:
            log("Applying per-file option '{}' and action '{}' to key '{}'."
                .format(per_file_name, action_name, key))
            # Call the per-file function (which will also call the action function)
            per_file_errors = per_file_func(
                results=results,
                key=key,
                file_vals=presults,
                action=ACTIONS[action_name]
            )

            for error in per_file_errors:
                errors.append(error)
                log(error)

        except ResultError as err:
            msg = ("Error handling results with per_file and action options.\n{}"
                   .format(err.args[0]))

            errors.append(msg)
            log(msg)

    results[RESULT_ERRORS].extend(errors)

    base_log.indent(log)


class ProcessedKey:
    """A processed key result for a given file."""
    def __init__(self, key: str, path: Path, value: Any):
        self.key = key
        self.path = path
        self.value = value


def process_file(args: Tuple[Path, List[KeySet]]) -> \
        Tuple[List[ProcessedKey], IndentedLog]:
    """Given a file and list of Key/Parser items, parse the file for each
    key. Returns the list of results as a (key, file, value) tuple, and the log data."""
    path, key_sets = args

    log = IndentedLog()

    file_results = []

    log("Parsing each key for file {}".format(path.as_posix()))

    with path.open() as file:
        # If we have to go through the file more than once, just read the whole thing
        #  memory.
        if len(key_sets) > 1:
            log("Reading entire file for in-memory processing.")
            file = StringIO(file.read())

        for key_set in key_sets:
            parser = get_plugin(key_set.parser_name)

            log("Parsing results for key '{}'".format(key_set.key))

            # Seek to the beginning of the file for each parse action.
            file.seek(0)

            # Get the result for a single key and file.
            result, rlog = parse_result(key_set.key, key_set.config, file, parser)
            log.indent(rlog)

            if isinstance(result, ParseErrorMsg):
                result.path = path
                file_results.append(ProcessedKey(RESULT_ERRORS, path, str(result)))
                # Add a None/NULL result for the key on an error.
                file_results.append(ProcessedKey(key_set.key, path, None))
            else:
                file_results.append(ProcessedKey(key_set.key, path, result))

    return file_results, log


def parse_result(key: str, parser_cfg: Dict, file: TextIO, parser: ResultParser) \
        -> Tuple[Union[ParseErrorMsg, str], IndentedLog]:
    """Use a result parser and it's settings to parse a single value from a file.

    :param key: The key we're parsing.
    :param parser_cfg: The parser config dict.
    :param file: The file from which to extract the result.
    :param parser: The result parser plugin object.
    :returns: The parsed value
    """

    log = IndentedLog()

    # Grab these for local use.
    action_name = parser_cfg['action']
    if key == 'result' and action_name not in (ACTION_FALSE, ACTION_TRUE):
        parser_cfg['action'] = ACTION_TRUE
        log("Forcing action to '{}' for the 'result' key.")

    # Get the idx value from the match_select option if it's a keyword, otherwise just
    # use the value directly.
    match_select = parser_cfg['match_select']
    match_idx = MATCH_CHOICES.get(match_select, match_select)
    if match_idx is None:
        match_idx = match_select
    else:
        match_idx = int(match_idx)

    # Compile the regexes for finding the appropriate lines on which to
    # call the result parser.
    match_cond_rex = [re.compile(cond) for cond in parser_cfg['preceded_by']]
    match_cond_rex.append(re.compile(parser_cfg['for_lines_matching']))

    # Check the arguments and remove any that aren't specific to this result
    # parser.
    try:
        stripped_cfg = parser.check_args(**parser_cfg.copy())
    except ResultError as err:
        return ParseErrorMsg(parser, err.args[0], key), log

    try:
        res, elog = extract_result(
            file=file,
            parser=parser, parser_args=stripped_cfg,
            pos_regexes=match_cond_rex,
            match_idx=match_idx,
        )

        log("Got result '{}' for key '{}'".format(res, key))
        log.indent(elog)

        # Add the key information if there was an error.
        if isinstance(res, ParseErrorMsg):
            res.key = key

        return res, log
    except OSError as err:
        msg = "Error reading file: {}".format(err)
        log(msg)
        return ParseErrorMsg(parser, msg, key), log
    except Exception as err:  # pylint: disable=W0703
        msg = "UnexpectedError: {}".format(err)
        log(traceback.format_exc())
        return ParseErrorMsg(parser, msg, key), log


def extract_result(file: TextIO, parser: ResultParser, parser_args: dict,
                   match_idx: Union[int, str],
                   pos_regexes: List[Pattern]) -> Tuple[Any, IndentedLog]:
    """Parse a result from a result file.

    :return: A list of all matching results found. Will be cut short if
        we only need the first result.
    """

    log = IndentedLog()

    matches = []

    # Find the next position that matches our position regexes.
    next_pos = advance_file(file, pos_regexes)

    while next_pos is not None:
        if pos_regexes[-1].pattern != '':
            log("Found potential match at pos {} in file."
                .format(file.tell()))
        try:
            # Apply to the parser to that file starting on that line.
            res = parser(file, **parser_args)
        except (ValueError, LookupError, OSError) as err:
            log("Error calling result parser {}.".format(parser.name))
            log(traceback.format_exc())
            return ParseErrorMsg(parser, "Parser error in {} parser."
                                         .format(parser.name), err), log

        file.seek(next_pos)

        if res is not None and not (match_idx == MATCH_UNIQ and res in matches):
            matches.append(res)
            log("Parser extracted result '{}'".format(res))

        # Stop extracting when we get to the asked for match index.
        if isinstance(match_idx, int) and 0 <= match_idx < len(matches):
            log("Got needed number of results, ending search.")
            break

        next_pos = advance_file(file, pos_regexes)

    if match_idx in (MATCH_ALL, MATCH_UNIQ):
        return matches, log
    else:
        try:
            return matches[match_idx], log
        except IndexError:
            log("Match select index '{}' out of range. There were only {} "
                "matches.".format(match_idx, len(matches)))
            return None, log


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
