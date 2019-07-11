"""Sets up a base set of pavilion arguments, and allows plugins and other
components to add sub-commands.
"""
# pylint: disable=W0603

import argparse

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
        description="Pavilion is a framework for running tests on "
                    "supercomputers.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False,
                        help='Log all levels of messages to stderr.')

    _PAV_PARSER = parser
    _PAV_SUB_PARSER = parser.add_subparsers(dest='command_name')

    return parser


def get_subparser():
    """Get the pavilion subparser object. This should be used by command
    plugins to add sub-commands and their arguments to Pavilion.
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
