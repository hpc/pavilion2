from pavilion import result_parsers
import yaml_config as yc


class BadInit(result_parsers.ResultParser):
    """Set a constant as result."""

    def __init__(self):
        super().__init__(
            name='bad_init',
            description="Has an exception in init.")

        raise ValueError("I'm intentional!")

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'const', required=True,
                help_text="Constant that will be placed in result."
            )
        ])

        return config_items

    def _check_args(self, const=None):
        
        if const == "":
            raise result_parsers.ResultParserError(
                "Constant required."
        )

    def __call__(self, test, file, const=None):

        return const
