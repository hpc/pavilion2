from pavilion import result_parsers
import yaml_config as yc


class MatchCount(result_parsers.ResultParser):
    """Count matches against a word to inform success or failure."""

    PASS = result_parsers.PASS
    FAIL = result_parsers.FAIL
    ERROR = result_parsers.ERROR

    ACTION_STORE = result_parsers.ACTION_STORE
    ACTION_TRUE = result_parsers.ACTION_TRUE
    ACTION_FALSE = result_parsers.ACTION_FALSE
    ACTION_COUNT = result_parsers.ACTION_COUNT

    PER_FIRST = result_parsers.PER_FIRST
    PER_LAST = result_parsers.PER_LAST
    PER_FULLNAME = result_parsers.PER_FULLNAME
    PER_NAME = result_parsers.PER_NAME
    PER_LIST = result_parsers.PER_LIST
    PER_ANY = result_parsers.PER_ANY
    PER_ALL = result_parsers.PER_ALL

    MATCH_FIRST = result_parsers.MATCH_FIRST
    MATCH_LAST = result_parsers.MATCH_LAST
    MATCH_ALL = result_parsers.MATCH_ALL

    def __init__(self):
        # Using the default open_mode of 'r' and default priority.
        super().__init__(name='match_count')

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

    def check_args(self, file=None, search=None, threshold=None):

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

        if file is None:
            file = []

        res_dict = {}

        for res in file:
            total = 0
            for line in res.readlines():
                total += line.count(search)

        if threshold is None:
            return total
        elif total < int(threshold):
                return self.FAIL
        return self.PASS
