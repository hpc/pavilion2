from pavilion import result_parsers
import yaml_config as yc
import re


class Match(result_parsers.ResultParser):
    """Match against a specific word to determine success or failure."""

    def __init__(self):
        super().__init__(name='match')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'match', default=None,
                help_text="A word that will be searched for in the output of "
                          "the test that will determine success or failure."
            ),
            yc.StrElem(
                'results', default='pass',
                choices=['pass','fail'],
                help_text="If the word is found in the output, the result "
                          "will be what is provided here.  If the word is not "
                          "found, the other choice is the result."
            )
        ])

        return config_items

    def __call__(self, test, file=None, search=None, results=None):

        matches = []

        try:
            with open(file, "r") as infile:
                for line in infile.readlines():
                    match = line if search in line else None

                    if match is not None:
                        matches.append(match.group())
        except (IOError, OSError) as err:
            raise result_parsers.ResultParserError(
                "Match result parser could not read input file '{}': {}"
                .format(file, err)
            )

        if not matches.empty():
            return results

        ret_val = 'pass' if results == 'fail' else 'pass'
        return ret_val
