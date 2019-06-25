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
            ),
            yc.StrElem(
                'success', required=True,
                default='return_value',
                help_text="needs to be either return_value or output"
            ),
            yc.StrElem(
                'success_value', required=True,
                default='0',
                help_text="success value"
            )
        ])

        return config_items

    def _check_args(self, command=None, success=None, success_value=None):

        if (command == "") or (success == "") or (success_value == ""):
            raise result_parsers.ResultParserError(
                "command, success, and success_value are required"
            )
        """
        # runs command
        else:
            cmd_result = ""
            # get output
            if success == "output":
                try:
                    cmd_result = subprocess.check_output(command, 
                        stderr=subprocess.STDOUT,
                        shell=True).decode("utf-8")
                    cmd_result = str(cmd_result)
                    print("out: " + cmd_result)
                except:
                    print("output: command did not work")
            # get return value
            else:
                try:
                    cmd_result = str(subprocess.call(command, shell=True))
                    print("return value: " + cmd_result)
                except:
                    print("return value: command did not work")
            # compare out/return_value with success value
            print("success_value: " + success_value)
            if cmd_result == str(success_value): 
                print("command success")
                success_value = "command_successful"
            else: 
                print("command unsuccessful")
                success_value = "command_unsuccessful"
        """

    def __call__(self, test, file, command=None, success=None, success_value=None):

        # run command
        cmd_result = ""
        # get output
        if success == "output":
            try:
                cmd_result = subprocess.check_output(command,
                    stderr=subprocess.STDOUT,
                    shell=True).decode("utf-8")
                cmd_result = str(cmd_result)
                print("out: " + cmd_result)
            except:
                print("output: command did not work")
        # get return value
        else:
            try:
                cmd_result = str(subprocess.call(command, shell=True))
                print("return value: " + cmd_result)
            except:
                print("return value: command did not work")
        # compare cmd_result with success value
        if cmd_result == str(success_value):
            print("command success")
            return "COMMAND SUCCESS"
        else:
            print("command unsuccessful")
            return "COMMAND UNSUCCESSFUL"


        return "success"
