import os
from io import StringIO
from re import sub

from yaml_config.testlib import YCTestCase

import yaml_config as yc


class YCExtendTest(YCTestCase):

    def test_extend_lists(self):
        """Check that extending lists works as expected."""

        data = {
            'list_a': ['la_1', 'la_2', 'la_3'],
            'list_c': ['lc_1', 'lc_2', 'lc_3'],
            'cat': {
                'item1': ['i1_1', 'i1_2', 'i1_3'],
            }
        }

        data2 = {
            'list_a+': ['la_4', 'la_5', 'la_6'],
            'list_b+': ['lb_1', 'lb_2', 'lb_3'],
            'list_c': ['lc_4', 'lc_5', 'lc_6'],
            'cat': {
                'item1+': ['i1_4', 'i1_5'],
                'item2+': ['i2_1', 'i2_2'],
                'item3': ['i3_4', 'i3_5'],
            }
        }

        expected_result = {
            'list_a': ['la_1', 'la_2', 'la_3', 'la_4', 'la_5', 'la_6'],
            'list_b': ['lb_1', 'lb_2', 'lb_3'],
            'list_c': ['lc_4', 'lc_5', 'lc_6'],
            'cat': {
                'item1': ['i1_1', 'i1_2', 'i1_3', 'i1_4', 'i1_5'],
                'item2': ['i2_1', 'i2_2'],
                'item3': ['i3_4', 'i3_5'],
            }
        }

        config = yc.KeyedElem('base', elements=[
            yc.ListElem('list_a', sub_elem=yc.StrElem()),
            yc.ListElem('list_b', sub_elem=yc.StrElem()),
            yc.ListElem('list_c', sub_elem=yc.StrElem()),
            yc.CategoryElem('cat', sub_elem=yc.ListElem(sub_elem=yc.StrElem())),
        ])

        ndata = config.normalize(data)
        vdata = config.validate(ndata)

        ndata2 = config.normalize(data2)
        final_data = config.merge(ndata, ndata2)

        self.assertDictEqual(final_data, expected_result)

        import pprint
        pprint.pprint(final_data)
