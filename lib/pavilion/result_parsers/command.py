"""Execute a command and get its output or return value."""
import subprocess

import yaml_config as yc
from pavilion import errors
from pavilion.result_parsers import base_classes


class Command(base_classes.ResultParser):
    """Runs a given command."""

    FORCE_DEFAULTS = ['match_select', 'files', 'per_file']

    def __init__(self):
        super().__init__(
            name='command',
            description="Runs a command, and uses it's output or return "
                        "values as a result value.",
            config_elems=[
                yc.StrElem(
                    'command', required=True,
                    help_text="Run this command in a sub-shell and collect "
                              "its return value or stdout."
                ),
                yc.StrElem(
                    'output_type',
                    help_text="Whether to return the return value or stdout."
                ),
                yc.StrElem(
                    'stderr_dest',
                    help_text="Where to redirect stderr."
                )
            ],
            validators={
                'output_type': ('return_value', 'stdout'),
                'stderr_dest': ('null', 'stdout'),
            },
            defaults={
                'output_type': 'return_value',
                'stderr_dest': 'stdout',
            }
        )

    # pylint: disable=arguments-differ
    def __call__(self, file, command=None, output_type=None,
                 stderr_dest=None):

        # where to redirect stderr
        if stderr_dest == 'null':
            err = subprocess.DEVNULL
        else:
            err = subprocess.STDOUT

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=err,
            )
        except subprocess.CalledProcessError as err:
            raise errors.ResultError(
                "Command cannot be executed: '{}'"
                .format(command), err)

        out, err = proc.communicate()

        if output_type == "stdout":
            return out
        else:
            return proc.returncode
