from pavilion import result_parsers
import yaml_config as yc


class MatchCount(result_parsers.ResultParser):
    """Count matches against a word to inform success or failure."""

    PASS = result_parsers.PASS
    FAIL = result_parsers.FAIL

    def __init__(self):
        super().__init__(name='match_count')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'match', default=None,
                help_text="A word that will be searched for in the output of "
                          "the test that will determine success or failure."
            ),
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

    def check_args(self, test, file=None, search=None, threshold=None):

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

        total = 0

        try:
            with open(file, "r") as infile:
                for line in infile.readlines():
                    total += line.count(search)
        except (IOError, OSError) as err:
            raise result_parsers.ResultParserError(
                "Match result parser could not read input file '{}': {}"
                .format(file, err)
            )

        if threshold is None:
            return total
        elif total < int(threshold):
                return self.FAIL
        return self.PASS
