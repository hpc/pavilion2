"""Execute a command and get its output or return value."""
import subprocess
from pathlib import Path
from typing import Tuple, Optional

import yaml_config as yc
from pavilion import errors
from pavilion.result_parsers import base_classes
from pavilion.utils import IndentedLog


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
                ),
                yc.StrElem(
                    "working_dir",
                    help_text="Directory from which the result parser will run. "
                        "By default, the test's build directory. If a relative path is given, "
                        "it will be relative to the test's build directory."
                ),
            ],
            validators={
                'output_type': ('return_value', 'stdout'),
                'stderr_dest': ('null', 'stdout'),
                'working_dir': working_dir_validator,
            },
            defaults={
                'output_type': 'return_value',
                'stderr_dest': 'stdout',
                'working_dir': '.',
            }
        )

    # pylint: disable=arguments-differ
    def __call__(self, file: Path,
                 command: Optional[str] = None,
                 output_type: Optional[str] = None,
                 stderr_dest: Optional[str] = None,
                 working_dir: Path = None) -> Tuple[int, IndentedLog]:

        log = IndentedLog()

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
                encoding="utf-8",
                cwd=working_dir
            )
        except subprocess.CalledProcessError as err:
            raise errors.ResultError(
                "Command cannot be executed: '{}'"
                .format(command), err)

        out, err = proc.communicate()

        if output_type == "stdout":
            return out, log
        else:
            return proc.returncode, log


def working_dir_validator(working_dir: str) -> None:
    """Validate working directory."""

    try:
        Path(working_dir).resolve()
    except (OSError, TypeError):
        raise ValueError(f"Invalid path: {working_dir}.")

    if not Path(working_dir).is_dir():
        raise ValueError(f"Not a directory: {working_dir}.")
