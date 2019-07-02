from pavilion import result_parsers
import yaml_config as yc

import collections


class Match(result_parsers.ResultParser):
    """Collects matches against a word to inform success or failure."""

    def __init__(self):
        # Using the default open_mode of 'r' and default priority.
        super().__init__(name='match')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'match', default=None,
                help_text="A word that will be searched for in the output of "
                          "the test that will determine success or failure."
            ),
            result_parsers.MATCHES_ELEM,
            yc.StrElem(
                'threshold', default=None,
                help_text="If a threshold is defined, 'pass' will be returned "
                          "if greater than or equal to that many instances "
                          "of the specified word are found.  If fewer "
                          "instances are found, 'fail' is returned.  If no "
                          "threshold is defined, the count will be returned."
            )
        ])

        return config_items

    def check_args(self, files=None, search=None, threshold=None, action=None):

        if threshold is not None:
            try:
                int(threshold)
            except:
                raise result_parsers.ResultParserError(
                    "Invalid value for threshold: {}".format(threshold)
                )

            if int(threshold) < 0:
                raise result_parsers.ResultParserError(
                    "Threshold must be greater than or equal to zero. "
                    "Received {}".format(threshold)
                )

    def __call__(self, test, file=None, search=None, threshold=None):

        line_list = []

        for line in file:
            if search in line:
                line_list.append(line)

        if threshold is None:
            return line_list

        return (len(line_list) >= threshold)
