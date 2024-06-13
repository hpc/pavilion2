from pathlib import Path
from typing import Dict, Union

from pavilion.status_file import TestStatusFile
from pavilion import series


def name(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "name" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "name" attribute
    """
    name_parse = re.compile(r'^([a-zA-Z0-9_*?\[\]-]+)'  # The test suite name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?'  # The test name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?$'  # The permutation name.
                            )
    test_name = attrs.get('name') or ''
    filter_match = name_parse.match(val)
    name_match = name_parse.match(test_name)

    suite = '*'
    test = '*'
    perm = '*'

    if filter_match is not None:
        suite, test, perm = filter_match.groups()

    if name_match is not None:
        _, _, test_perm = name_match.groups()

        # allows permutation glob filters to match tests without permutations
        # e.g., name=suite.test.* will match suite.test
        if not test_perm:
            test_name = test_name + '.*'

    if suite is None:
        suite = '*'

    if test is None:
        test = '*'

    if perm is None:
        perm = '*'

    new_val = '.'.join([suite, test, perm])

    return fnmatch.fnmatch(test_name, new_val)
    

FILTER_FUNCS = {
    'has_state': lambda x, y: x.has_state(y.upper()),
    'name': name,
}
