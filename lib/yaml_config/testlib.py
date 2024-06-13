"""Provides a customized test case for unittests and colorized results."""

import os
from pathlib import Path

import yaml_config
from unittest_ex import TestCaseEx


class YCTestCase(TestCaseEx):
    """A test case class that allows for dynamically skippable tests."""

    ROOT_DIR = Path(__file__).parents[1]

    def _data_path(self, filename):
        """Return an absolute path to the given test data file."""
        path = Path(__file__).resolve()
        path = path.parents[2]/'test'/'tests'/'yaml_config_tests'/'data'
        return path/filename

    class Config(yaml_config.YamlConfigLoader):
        """A basic config to run tests against."""

        ELEMENTS = [
            yaml_config.scalars.StrElem(
                "pet", default="squirrel", required=True,
                choices=["squirrel", "cat", "dog"],
                help_text="The kind of pet."),
            yaml_config.scalars.IntElem("quantity", required=True,
                                        choices=[1, 2, 3]),
            yaml_config.scalars.FloatRangeElem("quality", vmin=0, vmax=1.0),
            yaml_config.structures.ListElem(
                "potential_names",
                help_text="What you could name this pet.",
                sub_elem=yaml_config.scalars.StrElem(help_text="Such as Fido.")),
            yaml_config.structures.KeyedElem(
                "properties", help_text="Pet properties", elements=[
                yaml_config.scalars.StrElem(
                    "description", help_text="General pet description."),
                yaml_config.scalars.StrElem(
                    'fuzzy_*', help_text="I accept all sorts of keys."),
                yaml_config.scalars.RegexElem(
                    "greeting", regex=r'hello \w+$',
                    help_text="A regex of some sort."),
                yaml_config.scalars.IntRangeElem("legs", vmin=0)
            ]),
            yaml_config.structures.CategoryElem(
                "traits", sub_elem=yaml_config.scalars.StrElem()),
        ]
