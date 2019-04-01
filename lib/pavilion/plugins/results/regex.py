from pavilion import result_parsers
import yaml_config as yc
import re


class Regex(result_parsers.ResultParser):
    """Find matches to the given regex in the given file. The matched string
    or strings are returned as the result."""

    def __init__(self):
        super().__init__(name='regex')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'regex', default=None,
                help_text="The python regex to use to search the given file. "
                          "See: 'https://docs.python.org/3/library/re.html' "
                          "You can use single quotes in YAML to have the string"
                          "interpreted literally. IE '\\n' is a '\\' and an 'n'"
            ),
            yc.StrElem(
                'results', default='first',
                choices=['first', 'all', 'last'],
                help_text="This can return the first, last, or all matches. "
                          "If there are no matches the result will be null"
                          "or an empty list."
            )
        ])

        return config_items

    def check_args(self, test, file=None, regex=None, results=None):

        try:
            re.compile(regex)
        except ValueError as err:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(err)
            )

    def __call__(self, test, file=None, regex=None, results=None):

        regex = re.compile(regex)

        matches = []

        try:
            with open(file, "r") as infile:
                for line in infile.readlines():
                    match = regex.search(line)

                    if match is not None:
                        matches.append(match.group())
        except (IOError, OSError) as err:
            raise result_parsers.ResultParserError(
                "Regex result parser could not read input file '{}': {}"
                .format(file, err)
            )

        if results in ['first', 'last'] and not matches:
            return None

        if results == 'first':
            return results[0]
        elif results == 'last':
            return results[-1]
        else:
            return results
