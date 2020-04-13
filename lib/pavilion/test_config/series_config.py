import yaml_config as yc


class SeriesConfigLoader(yc.YamlConfigLoader):
    """This class describes a series file."""

    ELEMENTS = [
        yc.CategoryElem(
            'series', sub_elem=yc.KeyedElem(
                elements=[
                    yc.ListElem('test_names', sub_elem=yc.StrElem()),
                    yc.ListElem('modes', sub_elem=yc.StrElem()),
                    yc.CategoryElem(
                        'only_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem())
                    ),
                    yc.CategoryElem(
                        'not_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem())
                    )
                ]
            ),
        ),
        yc.ListElem(
            'modes', sub_elem=yc.StrElem()
        ),
        yc.ListElem(
            'on_complete', sub_elem=yc.StrElem()
        ),
    ]
