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
                'regex', default='',
                help_text="The python regex to use to search the given file. "
                          "See: 'https://docs.python.org/3/library/re.html' "
                          "You can use single quotes in YAML to have the "
                          "string interpreted literally. IE '\\n' is a '\\' "
                          "and an 'n'."
            ),
            yc.StrElem(
                'rtype', default='first',
                choices=['first', 'all', 'last', 'PASS', 'FAIL'],
                help_text="This can return the first, last, or all matches. "
                          "If there are no matches the result will be null "
                          "or an empty list. For 'PASS' and 'FAIL', simply "
                          "return that value if a match was found (and the "
                          "opposite otherwise."
            )
        ])

        return config_items

    def _check_args(self, test, file=None, regex=None, rtype=None):

        try:
            re.compile(regex)
        except ValueError as err:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(err))

    def __call__(self, test, file=None, regex=None, rtype=None):

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

        if rtype == 'first':
            return matches[0] if matches else None
        elif rtype == 'last':
            return matches[-1] if matches else None
        elif rtype == 'all':
            return matches
        elif rtype in ['PASS', 'FAIL']:
            if matches:
                return rtype
            else:
                return 'PASS' if rtype == 'FAIL' else 'FAIL'
        else:
            raise RuntimeError("Invalid 'results' argument in regex parser: "
                               "'{}'".format(rtype))
