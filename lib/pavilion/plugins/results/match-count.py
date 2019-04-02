from pavilion import result_parsers
import yaml_config as yc
import re


class MatchCount(result_parsers.ResultParser):
    """Count matches against a word to inform success or failure."""

    def __init__(self):
        super().__init__(name='match-count')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'match', default=None,
                help_text="A word that will be searched for in the output of "
                          "the test that will determine success or failure."
            )
            yc.IntElem(
                'threshold', default=None,
                help_text="If a threshold is defined, 'pass' will be returned "
                          "if greater than or equal to that many instances "
                          "of the specified word are found.  If fewer "
                          "instances are found, 'fail' is returned.  If no "
                          "threshold is defined, the count will be returned."
        ])

        return config_items

    def __call__(self, test, file=None, search=None, threshold=None):

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

        if threshold is None:
            return len(matches)
        else:
            if len(matches) < threshold:
                return 'fail'
        return 'pass'
