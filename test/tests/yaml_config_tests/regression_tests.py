import os

import yaml_config.scalars
import yaml_config.structures
import yc_yaml
from yaml_config.testlib import YCTestCase


class YCBasicTest(YCTestCase):

    def test_duplicates(self):
        """Duplicates are not allowed in mappings."""

        with self.assertRaises(yc_yaml.YAMLError):
            with open(self._data_path('duplicates.yaml')) as f:
                self.Config().load(f)

    def test_string_conv_limits(self):
        """We should only auto-convert scalars into strings."""

        with self.assertRaises(ValueError):
            with open(self._data_path('string_conv_limits.yaml')) as f:

    def test_regex_val_type(self):
        """Make sure parsed values end up being the correct type by the
        time we check them. Regex elements will assume this."""

        with self.assertRaises(ValueError):
            with open(self._data_path('regex_val_type.yaml')) as f:
                self.Config().load(f)

    def test_bad_default(self):
        """Defaults should normalize to the appropriate type as well."""

        el = yaml_config.scalars.RegexElem(
            'num', default=5, regex=r'\d+')
        self.assertTrue(el.validate(None) == '5')

    def test_extra_keyedelem_key(self):
        """KeyedElements should not allow for keys that aren't defined in
        their element list."""

        with self.assertRaises(KeyError):
            self.Config().validate(
                {
                    'not_defined': 'nope',
                }
            )

    def test_merge_null_dict(self):
        """Make sure undefined dictionaries don't override the original."""

        with open(self._data_path('test1.yaml')) as f:
            base = self.Config().load(f)

        with open(self._data_path('nulls.yaml')) as f:
            self.Config().load_merge(base, f)
