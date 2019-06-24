from pavilion import result_parsers
import yaml_config as yc
import re

class Constant(result_parsers.ResultParser):
    """Set a constant as result."""

    def __init__(self):
        super().__init__(name='constant')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'result_constant', required=True, default='constant_default',
                help_text="what will show up in the result"
            )
        ])

        return config_items

    def _check_args(self, result_constant=None):
        
        if result_constant == "":
            raise result_parsers.ResultParserError(
                "constant required"
        )

    def __call__(self, test, file, result_constant=None):

        return result_constant
