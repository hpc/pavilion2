"""Functions to handle the collection of results using result parsers."""

import glob
import inspect
import pprint
import re
import traceback
from collections import OrderedDict
from pathlib import Path
from typing import List, Union, Dict, Callable, Any, TextIO, Pattern

from pavilion.utils import IndentedLog
from .base import RESULT_ERRORS
from .common import ResultError
from .options import (PER_FILES, ACTIONS, MATCH_CHOICES, per_first,
                      ACTION_TRUE, ACTION_FALSE)
from .parsers import ResultParser, get_plugin


class ParseErrorMsg:
    """Standardized result parser error message."""

    def __init__(self, key: str, parser: ResultParser,
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


DEFAULT_KEY = '_defaults'


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
        if parser_configs[parser_name]:
            log("Parsing results for parser '{}'".format(parser_name))

        # Each parser has a list of configs. Process each of them.
        for key, rconf in parser_configs[parser_name].items():
            log.indent = 2
            log("Parsing value for key '{}'".format(key))

            error = parse_result(
                results=results,
                key=key,
                parser_cfg=parser.set_parser_defaults(rconf, defaults),
                parser=parser,
                test=test,
                log=log)

            if error is not None:
                results[RESULT_ERRORS].append(str(error))


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


def parse_file(path: Path, parser: ResultParser, parser_args: dict,
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
        next_pos = advance_file(file, pos_regexes)

        while next_pos is not None:
            if pos_regexes[-1].pattern != '':
                log("Found potential match at pos {} in file."
                    .format(file.tell()))
            try:
                res = parser(file, **parser_args)
            except Exception as exc:
                log("Error calling result parser {}.".format(parser.name))
                log(traceback.format_exc())
                raise

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

    # Find all the files we'll be parsing.
    paths = []
    for file_glob in globs:
        base_glob = file_glob
        if not file_glob.startswith('/'):
            file_glob = '{}/build/{}'.format(test.path, file_glob)

        paths_found = glob.glob(file_glob)
        paths_found.reverse()
        if paths_found:
            paths.extend(Path(path) for path in sorted(paths_found))
        else:
            presults[Path('_unmatched_glob_' + base_glob.split('/')[-1])] = None
            log("Setting a non match result for unmatched glob '{}'"
                .format(file_glob))
            results[RESULT_ERRORS].append(
                "No matches for glob '{}' under key '{}'"
                .format(base_glob, key))

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
