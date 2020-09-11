"""Parse regular expressions from file."""

import re
import sre_constants

import pavilion.result.base
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
                              "library/re.html'. You can use single quotes "
                              "in YAML to have the string interpreted "
                              "literally. IE '\\n' is a '\\' "
                              "and an 'n'. "
                )]
        )

    def _check_args(self, **kwargs):

        try:
            kwargs['regex'] = re.compile(kwargs['regex'])
        except (ValueError, sre_constants.error) as err:
            raise pavilion.result.base.ResultError(
                "Invalid regular expression: {}".format(err))

        return kwargs

    def __call__(self, test, file, regex=None, match_type=None):

        regex = re.compile(regex)

        matches = []

        for line in file.readlines():
            # Find all non-overlapping matches and return them as a list.
            # if more than one capture is used, list contains tuples of
            # captured strings.
            matches.extend(regex.findall(line))
