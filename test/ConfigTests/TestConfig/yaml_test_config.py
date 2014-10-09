#!/usr/bin/env python

import unittest
import sys
import os

base = os.path.abspath("../../../")
sys.path.append(base)
sys.path.append(base + "/PAV/special_pkgs")
sys.path.append(base + "/PAV/modules")

from testConfig import YamlTestConfig

class YamlTestConfigTest(unittest.TestCase):
    def test_invalid_default_file(self):
        with self.assertRaises(SystemExit):
            YamlTestConfig('invalid_default.yaml')

    def test_malformed_default_file(self):
        with self.assertRaises(SystemExit):
            YamlTestConfig('malformed_default.yaml')

    def test_invalid_yaml_file(self):
        with self.assertRaises(SystemExit):
            YamlTestConfig('invalid_yaml.yaml')
if __name__ == '__main__':
    unittest.main(verbosity=2)
