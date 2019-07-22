from pavilion import result_parsers
import yaml_config as yc
import re


class Regex(result_parsers.ResultParser):
    """Find matches to the given regex in the given file. The matched string
    or strings are returned as the result."""

    def __init__(self):
        super().__init__(name='regex',
                         description="Find data using a basic regular "
                                     "expression.")

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'regex', required=True,
                help_text="The python regex to use to search the given file. "
                          "See: 'https://docs.python.org/3/library/re.html' "
                          "You can use single quotes in YAML to have the "
                          "string interpreted literally. IE '\\n' is a '\\' "
                          "and an 'n'."
            ),
            # Use the built-in matches element.
            result_parsers.MATCHES_ELEM
        ])

        return config_items

    def _check_args(self, regex=None, match_type=None):

        try:
            re.compile(regex)
        except ValueError as err:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(err))

    def __call__(self, test, file, regex=None, match_type=None):

        regex = re.compile(regex)

        matches = []

        for line in file.readlines():
            match = regex.search(line)

            if match is not None:
                matches.append(match.group())

        if match_type == result_parsers.MATCH_FIRST:
            return matches[0] if matches else None
        elif match_type == result_parsers.MATCH_LAST:
            return matches[-1] if matches else None
        elif match_type == result_parsers.MATCH_ALL:
            return matches
        else:
            raise result_parsers.ResultParserError(
                "Invalid 'matches' value '{}'".format('matches')
            )
