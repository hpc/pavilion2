from pavilion import result_parsers
import yaml_config as yc
import subprocess


class Command(result_parsers.ResultParser):
    """Runs a given command."""

    def __init__(self):
        super().__init__(
            name='command',
            description="Runs a command, and uses it's output or return "
                        "values as a result value."
        )

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'command', required=True,
                help_text="Command that will be run."
            ),
            yc.StrElem(
                'success',
                default='return_value',
                choices=['return_value','output'],
                help_text="needs to be either return_value or output"
            ),
            yc.StrElem(
                'success_value',
                default='0',
                help_text="success value"
            ),
            yc.StrElem(
                'stderr_out',
                choices=['/dev/null','stdout'],
                default='stdout',
                help_text="where to redirect stderr"
            )
        ])

        return config_items

    def _check_args(self, command=None, success=None, success_value=None, stderr_out=None):

        if not command:
            raise result_parsers.ResultParserError(
                "Command required."
            )

    def __call__(self, test, file, command=None, success=None, success_value=None, stderr_out=None):

        # run command
        cmd_result = ""

        # where to redirect stderr
        if stderr_out == "/dev/null":
            err = open('/dev/null','wb')
        else:
            err = subprocess.STDOUT

        # get output
        if success == "output":
            try:
                cmd_result = subprocess.check_output(command,
                    stderr=err,
                    shell=True).decode("utf-8")
                cmd_result = str(cmd_result)
            except:
                raise result_parsers.ResultParserError(
                    "Command cannot be executed.")
        # get return value
        else:
            try:
                cmd_result = str(subprocess.call(command, stderr=err, shell=True))
            except:
                raise result_parsers.ResultParserError(
                    "Command cannot be executed."
                )
        # compare cmd_result with success value
        if cmd_result == str(success_value):
            return True
        else:
            return False
