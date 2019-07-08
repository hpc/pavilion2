from pavilion import result_parsers
import yaml_config as yc
import re
import sre_constants


class Regex(result_parsers.ResultParser):
    """Find matches to the given regex in the given file. The matched string
    or strings are returned as the result."""

    def __init__(self):
        super().__init__(name='regex')
        self.range_re = re.compile('(-?[0-9]*\.?[0-9]*)-(-?.*)')

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
            result_parsers.MATCHES_ELEM,
            yc.StrElem(
                'threshold', default='0',
                help_text="If a threshold is defined, 'True' will be returned "
                          "if greater than or equal to that many instances "
                          "of the specified word are found.  If fewer "
                          "instances are found, 'False' is returned.  The "
                          "value must be an integer greater than zero."
            ),
            yc.ListElem(
                'expected', sub_elem=yc.StrElem(),
                help_text="Expected value(s) and/or range(s).  If provided, "
                          "the result will be 'True' if all of the found "
                          "values (determined by the 'results' value) are "
                          "within the expected range(s) or value(s).  "
                          "Otherwise, the result is 'False'. Supports "
                          "integers and floats."
            )
        ])

        return config_items

    def _check_args(self, regex=None, match_type=None, threshold=None,
            expected=None):

        try:
            re.compile(regex)
        except (ValueError, sre_constants.error) as err:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(err))

        if not isinstance(expected, list):
            raise result_parsers.ResultParserError(
                "Expected should be a list.")

        if threshold is not None:
            try:
                int(threshold)
            except ValueError as err:
                raise result_parsers.ResultParserError(
                    "Non-integer value provided for 'threshold'.")

            if int(threshold) < 0:
                raise result_parsers.ResultParserError(
                    "'threshold' must be a non-negative integer.")

        for item in expected:
            test_list = []

            if '-' in item[1:]:
                test_list = list(self.range_re.search(item).groups())
                # Check for valid second part of range.
                if '-' in test_list[1][1:]:
                    raise result_parsers.ResultParserError(
                        "Invalid range: {}".format(item)
                    )
            else:
                test_list = [ item ]

            for test_item in test_list:
                # Check for values as integers.
                try:
                    float(test_item)
                except ValueError as err:
                    raise result_parsers.ResultParserError(
                        "Invalid value: {}".format(test_item)
                    )

            if len(test_list) > 1:
                # Check for range specification as
                # (<lesser value>-<greater value>)
                if float(test_list[1]) < float(test_list[0]):
                    raise result_parsers.ResultParserError(
                        "Invalid range: {}".format(item))

    def __call__(self, test, file, regex=None, match_type=None, threshold=None,
            expected=None):

        regex = re.compile(regex)

        matches = []

        for line in file.readlines():
            # Find all non-overlapping matches and return them as a list.
            # if more than one capture is used, list contains tuples of
            # captured strings.
            matches.extend(regex.findall(line))

        # Test if the number of matches meets the specified threshold
        if int(threshold) > 0:
            return (len(matches) >= int(threshold))
        elif match_type == result_parsers.MATCH_FIRST:
            matches = None if not matches else matches[0]
        elif match_type == result_parsers.MATCH_LAST:
            matches = None if not matches else matches[-1]
        elif match_type == result_parsers.MATCH_ALL:
            pass
        else:
            raise result_parsers.ResultParserError(
                "Invalid 'matches' value '{}'".format('matches')
            )

        # Test if the found values are within any of the specified expected
        # ranges.
        if not expected:
            return matches# if matches else None
        else:
            # Initially set to false for all matches.
            ret_vals = []
            for i in range(0,len(matches)):
                for j in range(0,len(expected)):
                    # Not a range, checking for exact match.
                    if '-' not in expected[j][1:] and \
                            float(matches[i]) == float(expected[j]):
                                ret_vals.append(True)
                    # Checking if found value is in this range.
                    elif '-' in expected[j][1:]:
                        low, high = self.range_re.search(expected[j]).groups()
                        if float(low) <= float(matches[i]) <= float(high):
                            ret_vals.append(True)
            return ret_vals
