"""Sets up a base set of pavilion arguments, and allows plugins and other
components to add sub-commands.
"""
# pylint: disable=W0603

import argparse
import textwrap

import pavilion.config

PROFILE_SORT_DEFAULT = 'cumtime'
PROFILE_COUNT_DEFAULT = 20

class WrappedFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        """Preserve newlines when splitting lines."""
        all_lines = []

        lines = text.split('\n')
        for line in lines:
            all_lines.extend(textwrap.wrap(line, width))
        return all_lines

    def _fill_text(self, text, width, indent):
        """Preserve newlines when filling text."""

        all_lines = []

        for line in text.split('\n'):
            all_lines.extend(textwrap.wrap(line, width,
                                           initial_indent=indent,
                                           subsequent_indent=indent))
        return '\n'.join(all_lines)

def get_parser():
    """Get the main pavilion argument parser. This is generally only meant to
    be used by the main pavilion command. If the main parser hasn't yet been
    defined, this defines it."""

    parser = argparse.ArgumentParser(
        prog='pav',
        # We'll add our own help option that doesn't auto-exit.
        add_help=False,
        description="Pavilion is a framework for running tests on "
                    "supercomputers.",
        formatter_class=WrappedFormatter)
    parser.add_argument('--quiet', action='store_true',
                        help='Silence warnings and stderr output.')
    parser.add_argument('--version', action='version',
                        version='Pavilion ' + pavilion.config.get_version(),
                        default=False,
                        help='Displays the current version of Pavilion.')

    parser.add_argument('--help', '-h', action='store_true',
                        help='Display help and exit.')

    parser.add_argument(
        '--profile', action='store_true', default=False,
        help="Run Pavilion within the python profiler, and "
             "report the results.")

    parser.add_argument(
        '--profile-sort', default=PROFILE_SORT_DEFAULT,
        choices=['cumtime', 'calls', 'file', 'line', 'name', 'nfl', 'time'],
        help="The sort method for the profile table. See:\n"
             "https://docs.python.org/3.5/library/profile.html#pstats.Stats.sort_stats")

    parser.add_argument(
        '--profile-count', default=PROFILE_COUNT_DEFAULT, action='store', type=int,
        help="Number of rows in the profile table.")

    parser.cmd_sub_parser = parser.add_subparsers(dest='command_name')

    return parser
