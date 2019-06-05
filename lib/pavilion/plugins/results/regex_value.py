from pavilion import result_parsers
import yaml_config as yc
import re


class RegexValue(result_parsers.ResultParser):
    """Accepts a value or range of values for validation of results."""

    def __init__(self):
        self.range_re = re.compile('(-?[0-9]*\.?[0-9]*)-(-?.*)')
        super().__init__(name='regex_value', priority=10)

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
                          "or an empty list unless a value is provided for "
                          "expected. If a value is provided for expected, "
                          "the value chosen here will be compared to the "
                          "expected value(s) and/or range(s)."
            ),
            yc.ListElem('expected', sub_elem=yc.StrElem(),
                help_text="Optional expected value(s) and/or range(s). If "
                          "provided, the result will be 'PASS' if all of the "
                          "found values (determined by the 'results' value) "
                          "are within the expected range(s) or value(s).  "
                          "Otherwise, the result is 'FAIL'. Supports "
                          "integers and floats."
            )
        ])

        return config_items

    def check_args(self, test, file=None, regex=None, results=None,
                   expected=None):

        # Check for valid regex
        try:
            re.compile(regex)
        except:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(regex)
            )

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

    def __call__(self, test, file=None, regex=None, results=None,
                 expected=None):

        regex = re.compile(regex)

        matches = []

        try:
            with open(file, "r") as infile:
                for line in infile.readlines():
                    match = None
                    match = regex.search(line)

                    if match is not None:
                        matches.append(match)
        except (IOError, OSError) as err:
            raise result_parsers.ResultParserError(
                "Regex result parser could not read input file '{}': {}"
                .format(file, err)
            )

        if results in ['first', 'last'] and not matches:
            return None
        elif not matches:
            return []

        found = None

        if results == 'first':
            found = [matches[0]]
        elif results == 'last':
            found = [matches[-1]]
        else:
            found = matches

        if expected is None: # found == 'spanish-inquisition'
            for i in range(0,len(found)):
                found[i] = found[i].group(0)
            return found

        if not isinstance(expected, list):
            raise result_parsers.ResultParserError("Expected should be a list.")

        for i in range(0,len(found)):
            if len(found[i].groups()) == 0:
                found[i] = [found[i].group(0)]
            elif len(found[i].groups()) == 1:
                found[i] = [found[i].group(1)]
            else:
                found[i] = found[i].groups()
            print(">>>>>>>>>>> Found values: {}".format(found[i]))

        res = [self.FAIL for x in range(0,len(found))]

        for i in range(0,len(res)):
            for j in range(0,len(found[i])):
                for exp_set in expected:
                    if '-' not in exp_set[1:] and found[i][j] == exp_set:
                        res[i] = self.PASS
                    elif '-' in exp_set[1:]:
                        low, high = self.range_re.search(exp_set).groups()
                        print("<<<<< Testing that {} <= {} <= {}".format(
                              float(low), found[i][j], float(high)))
                        if float(low) <= float(found[i][j]) <= float(high):
                            if res[i] == self.FAIL:
                                res[i] = self.PASS
                        else:
                            if res[i] == self.PASS:
                                res[i] == self.FAIL

        if self.FAIL in res:
            return self.FAIL

        return self.PASS
