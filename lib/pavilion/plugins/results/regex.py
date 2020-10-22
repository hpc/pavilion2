"""Parse regular expressions from file."""

import re
import sre_constants

from pavilion.result import ResultError
import yaml_config as yc
from pavilion.result import parsers


class Regex(parsers.ResultParser):
    """Find matches to the given regex in the given file. The matched string
    or strings are returned as the result."""

    def __init__(self):
        super().__init__(
            name='regex',
            description="Find data using a basic regular expressions.",
            config_elems=[
                yc.StrElem(
                    'regex', required=True,
                    help_text="The python regex to use to search the given "
                              "file. See: 'https://docs.python.org/3/"
                              "library/re.html'.\n"
                              "You can use single quotes "
                              "in YAML to have the string interpreted "
                              "literally. IE '\\n' is a '\\' "
                              "and an 'n'.\n"
                              "If you include no matching groups, "
                              "(ie '^my regex.*') all matched text will be "
                              "the result. \n"
                              "With a single matching group, "
                              "(ie '^my field: (\\d+)') the "
                              "result will be the value in that group.\n"
                              "With multiple matching groups, "
                              "(ie '^(\\d+) \\d+ (\\d+)') the result value "
                              "will be a list of all matched values. You "
                              "can use a complex key like 'speed, flops' "
                              "to store each value in a different result field "
                              "if desired."
                )]
        )

    def _check_args(self, **kwargs):

        try:
            kwargs['regex'] = re.compile(kwargs['regex'])
        except (ValueError, sre_constants.error) as err:
            raise ResultError(
                "Invalid regular expression: {}".format(err))

        return kwargs

    def __call__(self, file, regex=None):

        cregex = re.compile(regex)

        line = file.readline()
        match = cregex.search(line)

        if match is None:
            return None

        if cregex.groups == 0:
            return match.group()
        elif cregex.groups == 1:
            return match.groups()[0]
        else:
            return list(match.groups())
