"""Pavilion Series Configuration."""

import yaml_config as yc

from pavilion.config import make_invalidator
from pavilion.test_config.file_format import \
    CondCategoryElem, EnvCatElem, TestCatElem


class SeriesConfigLoader(yc.YamlConfigLoader):
    """This class describes a series file."""

    ELEMENTS = [
        TestCatElem(
            'series', sub_elem=yc.KeyedElem(
                elements=[
                    yc.ListElem('tests', sub_elem=yc.StrElem()),
                    yc.BoolElem('depends_pass', default=False),
                    yc.ListElem('depends_on', sub_elem=yc.StrElem()),
                    yc.ListElem('modes', sub_elem=yc.StrElem()),
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
            'modes', sub_elem=yc.StrElem()
        ),
        yc.IntElem(
            'simultaneous', default=0,
        ),
        yc.BoolElem(
            'ordered', default=False,
        ),
        yc.IntElem(
            'repeat', default=1,
            help_text="Number of times to repeat this series. Use 0 when running "
                      "a series in the background to repeat forever."
        ),
        yc.StrElem(
            'restart', post_validator=make_invalidator(
                "The series config option 'restart' has been replaced with 'repeat'.")
        )
    ]
    """Describes elements in Series Config Loader."""
