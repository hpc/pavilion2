"""Pavilion Series Configuration."""

import yaml_config as yc

from pavilion.config import make_invalidator
from pavilion.test_config.file_format import \
    CondCategoryElem, EnvCatElem, TestCatElem


class SeriesConfigLoader(yc.YamlConfigLoader):
    """This class describes a series file."""

    ELEMENTS = [
        TestCatElem(
            'test_sets', sub_elem=yc.KeyedElem(
                elements=[
                    yc.ListElem('tests', sub_elem=yc.StrElem()),
                    yc.BoolElem('depends_pass', default=False),
                    yc.ListElem('depends_on', sub_elem=yc.StrElem()),
                    yc.ListElem('modes', sub_elem=yc.StrElem()),
                    yc.IntElem('simultaneous', default=None),
                    CondCategoryElem(
                        'only_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
                        key_case=EnvCatElem.KC_MIXED
                    ),
                    CondCategoryElem(
                        'not_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
                        key_case=EnvCatElem.KC_MIXED
                    ),
                ]
            ),
        ),
        yc.StrElem(
            'name', hidden=True,
            help_text="The name of this series. Typically taken from series filename."
        ),
        yc.StrElem(
            'summary', default='',
            help_text="Brief description of the test series.",
        ),
        yc.StrElem(
            'os', hidden=True,
            help_text="The operating system this series will be run on. "
                      "This is not configured, but dynamically added to the config."
        ),
        yc.StrElem(
            'host', hidden=True,
            help_text="The host this series will be run on. This is not "
                      "configured, but dynamically added to the config."
        ),
        yc.ListElem(
            'overrides', sub_elem=yc.StrElem(), hidden=True,
            help_text="Command line overrides to apply to this series. This is only "
                      "used when ad-hoc series are created from the command line."
        ),
        yc.ListElem(
            'modes', sub_elem=yc.StrElem(),
            help_text="Modes to run all tests in this series under."
        ),
        yc.ListElem(
            'overrides', sub_elem=yc.StrElem(),
            help_text="Overrides to apply to all tests in this series."
        ),
        yc.IntElem(
            'simultaneous', default=0,
            help_text="The maximum number of tests to run simultaneously. This can be"
                      " set at the full series level and/or at each test_set level. If"
                      " set at both levels then test_set will take precedence."
        ),
        yc.BoolElem(
            'ordered', default=False,
            help_text="Run test sets in the order listed."
        ),
        yc.IntElem(
            'repeat', default=1,
            help_text="Number of times to repeat this series."
        ),
        yc.BoolElem(
            'ignore_errors', default=True,
            help_text="Whether the series ignores build and/or scheduling errors."
        ),
        yc.DiscontinuedElem(
            'series',
            help_text="Series parts are now configured under the 'test_sets' key in an effort "
                      "to reduce overloading of names. The keys under 'test_sets' are the same "
                      "as they were under the 'series' key, so all you should need to do is "
                      "change 'series:' to 'test_sets:'."
        ),
        yc.DiscontinuedElem(
            'restart',
            help_text="The series config option 'restart' has been replaced with 'repeat'."
        ),
    ]
    """Describes elements in Series Config Loader."""
