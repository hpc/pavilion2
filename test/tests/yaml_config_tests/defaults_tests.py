import yaml_config as yc
import yaml_config.scalars
import yaml_config.structures
from yaml_config.testlib import YCTestCase


class YCSetDefaultTest(YCTestCase):
    def test_set_default1(self):
        class DessertConfig(yc.YamlConfigLoader):
            ELEMENTS = [
                yaml_config.structures.KeyedElem('pie', elements=[
                    yaml_config.scalars.StrElem('fruit')
                ])
            ]

        config = DessertConfig()

        # Set the 'fruit' element of the 'pie' element to have a default
        # of 'apple'.
        config.set_default('pie.fruit', 'apple')

    def test_set_default2(self):
        class Config2(yc.YamlConfigLoader):
            ELEMENTS = [
                yaml_config.structures.ListElem('cars', sub_elem=yaml_config.structures.KeyedElem(elements=[
                    yaml_config.scalars.StrElem('color'),
                    yaml_config.scalars.StrElem('make'),
                    yaml_config.structures.ListElem('extras', sub_elem=yaml_config.scalars.StrElem())
                ]))
            ]

            def __init__(self, default_color):
                super(Config2, self).__init__()

                # The Config init is a good place to do this.
                # Set all the default color for all cars in the 'cars' list to
                # red.
                self.set_default('cars.*.color', default_color)
                self.set_default('cars.*.extras',
                                 ['rhoomba', 'heated sunshades'])

        raw = {
            'cars': [
                {'color': 'green',
                 'make':  'Dodge'
                 },
                {'make':   'Honda',
                 'extras': ['flaming wheels']}
            ]
        }

        config = Config2('red')

        data = config.validate(raw)

        expected_result = {'cars': [{'make':   'Dodge', 'color': 'green',
                                     'extras': ['rhoomba', 'heated sunshades']},
                                    {'make':   'Honda', 'color': 'red',
                                     'extras': ['flaming wheels']}]}

        self.assertEqual(data, expected_result)


if __name__ == '__main__':
    unittest.main()
