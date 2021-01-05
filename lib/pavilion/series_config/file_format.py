"""Pavilion Series Configuration."""

import yaml_config as yc

from pavilion.test_config.file_format import \
    CondCategoryElem, EnvCatElem, TestCatElem


class SeriesConfigLoader(yc.YamlConfigLoader):
    """This class describes a series file."""

    ELEMENTS = [
        TestCatElem(
            'series', sub_elem=yc.KeyedElem(
                elements=[
                    yc.ListElem('tests', sub_elem=yc.StrElem()),
                    yc.StrElem('depends_pass',
                               choices=['True', 'true', 'False', 'false'],
                               default='False'),
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
        yc.ListElem(
            'modes', sub_elem=yc.StrElem()
        ),
        yc.IntElem(
            'simultaneous',
        ),
        yc.StrElem(
            'ordered', choices=['True', 'true', 'False', 'false'],
            default='False'
        ),
        yc.StrElem(
            'restart', choices=['True', 'true', 'False', 'false'],
            default='False'
        )
    ]
    """Describes elements in Series Config Loader."""
