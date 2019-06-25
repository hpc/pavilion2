from pavilion import result_parsers
import yaml_config as yc
import re
import os
import subprocess


class Command(result_parsers.ResultParser):
    """Runs a given command."""

    def __init__(self):
        super().__init__(name='command')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'command', required=True,
                help_text="Command that will be run."
            )
        ])

        return config_items

    def _check_args(self, command=None):

        if command == "":
            raise result_parsers.ResultParserError(
                "command required"
            )
        # runs command
        else:
            #os.system(command)
            subprocess.call(command, shell=True)

    def __call__(self, test, file, command=None):

        return command
