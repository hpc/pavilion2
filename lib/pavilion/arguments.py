"""Sets up a base set of pavilion arguments, and allows plugins and other
components to add sub-commands.
"""
# pylint: disable=W0603

import argparse

import pavilion.config

_PAV_PARSER = None
_PAV_SUB_PARSER = None


def get_parser():
    """Get the main pavilion argument parser. This is generally only meant to
    be used by the main pavilion command. If the main parser hasn't yet been
    defined, this defines it."""

    global _PAV_PARSER
    global _PAV_SUB_PARSER

    if _PAV_PARSER is not None:
        return _PAV_PARSER

    parser = argparse.ArgumentParser(
        prog='pav',
        description="Pavilion is a framework for running tests on "
                    "supercomputers.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False,
                        help='Log all levels of messages to stderr.')
    parser.add_argument('--version', action='version',
                        version='Pavilion ' + pavilion.config.get_version(),
                        default=False,
                        help='Displays the current version of Pavilion.')

    parser.add_argument(
        '--profile', action='store_true', default=False,
        help="Run Pavilion within the python profiler, and "
             "report the results.")

    parser.add_argument(
        '--profile-sort', default='cumtime',
        choices=['cumtime', 'calls', 'file', 'line', 'name', 'nfl', 'time'],
        help="The sort method for the profile table. See:\n"
             "https://docs.python.org/3.5/library/profile.html"
             "#pstats.Stats.sort_stats")

    parser.add_argument(
        '--profile-count', default=20, action='store', type=int,
        help="Number of rows in the profile table.")

    _PAV_PARSER = parser
    _PAV_SUB_PARSER = parser.add_subparsers(dest='command_name')

    return parser


def get_subparser():
    """Get the pavilion subparser object. This should be used by command
plugins to add sub-commands and their arguments to Pavilion. (If you're
writing a command, use the ``_setup_arguments`` method on automatically
provided sub-command parser.)

See https://docs.python.org/3/library/argparse.html#sub-commands

:rtype: argparse._SubParsersAction
"""

    if _PAV_PARSER is None:
        raise RuntimeError("get_parser() must be called to setup the base "
                           "argument parser before calling get_subparser.")

    return _PAV_SUB_PARSER


def reset_parser():
    """Reset back to the base parser. This is for unittests only."""

    global _PAV_PARSER

    _PAV_PARSER = None

    get_parser()
