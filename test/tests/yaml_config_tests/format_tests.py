"""These tests are meant to check for any formatting issues. """

from io import StringIO

import yaml_config as yc
import yaml_config.scalars
import yaml_config.structures
from yaml_config.testlib import YCTestCase


class YCFormatTest(YCTestCase):
    def setUp(self):
        class TestConfig(yc.YamlConfigLoader):
            ELEMENTS = [
                yaml_config.scalars.StrElem("pet", default="squirrel", required=True,
                                            choices=["squirrel",
                                    "cat", "dog"],
                                            help_text="The kind of pet."),
                yaml_config.scalars.IntElem("quantity", required=True, choices=[1, 2, 3]),
                yaml_config.scalars.FloatRangeElem("quality", vmin=0, vmax=1.0),
                yaml_config.structures.CategoryElem(
                    "traits", sub_elem=yaml_config.scalars.StrElem()),
                yaml_config.structures.ListElem(
                    name='complex',
                    sub_elem=yaml_config.structures.CategoryElem(
                        sub_elem=yaml_config.structures.KeyedElem(
                            elements=[
                                yaml_config.scalars.StrElem('da', help_text='yada'),
                                yaml_config.scalars.StrElem('gr', help_text='grda'),
                            ],
                            help_text='Keyed Help'),
                        help_text='Category Help'),
                    help_text='List Help'),
                yaml_config.structures.ListElem(
                    name='keyed_complex',
                    sub_elem=yaml_config.structures.KeyedElem(
                        elements=[
                            yaml_config.scalars.StrElem('foo', help_text='This is deep.'),
                            yaml_config.scalars.IntElem(
                                'bar',
                                help_text='And a second one, with wrapping '
                                          'text. '*5),

                        ],
                        help_text='Keyed Help'),
                    help_text='List Help'),
                yaml_config.structures.ListElem("potential_names",
                                                help_text="What you could name this pet.",
                                                sub_elem=yaml_config.scalars.StrElem()),
                yaml_config.structures.KeyedElem("properties", help_text="Pet properties",
                                                 elements=[
                                 yaml_config.scalars.StrElem("description",
                                                             help_text="General pet description."),
                                 yaml_config.scalars.RegexElem("greeting", regex=r'hello \w+$',
                                                               help_text="A regex of some sort."),
                                 yaml_config.scalars.IntRangeElem("legs", vmin=0)
                             ]),
                yaml_config.structures.ListElem(
                    name="behavior_code",
                    sub_elem=yaml_config.scalars.StrElem(),
                    help_text="Program for pet behavior. "*10),
                yaml_config.structures.KeyedElem(
                    name='depth1',
                    elements=[
                        yaml_config.scalars.StrElem(
                            'depth1a',
                            help_text='How does this work when tabbed and '
                                      'wrapping. '*10),
                        yaml_config.scalars.StrElem(
                            'depth1b',
                            help_text='How does this work with newlines.\n'*10),
                    ],
                    help_text="This is super long too. "*10
                )
            ]

        self.Config = TestConfig

    def test_cycle(self):
        """Verify that we can load and save data without corrupting it."""

        test = self.Config()
        test_file = self._data_path('test1.yaml')
        with test_file.open('r') as f:
            data = test.load(f)

        buffer = StringIO()
        test.dump(buffer, data)

        buffer.seek(0)
        data2 = test.load(buffer)

        buffer.seek(0)

        self.assertEqual(data, data2)

    def test_cformat(self):
        """Verify some basics of comment formatting."""

        test = self.Config()
        buffer = StringIO()
        test.dump(buffer, values={})

        buffer.seek(0)
        lines = buffer.readlines()

        max_len = max(*[len(line) for line in lines])
        self.assertLessEqual(max_len, 81, )
