import yaml_config as yc


class SpackEnvConfig(yc.YamlConfigLoader):

    ELEMENTS = [
        yc.KeyedElem(
            'spack', elements=[
                yc.KeyedElem(
                    'config', elements=[
                        yc.StrElem('install_tree'),
                        yc.StrElem('build_jobs', default=6),
                        yc.StrElem('install_path_scheme')
                    ]
                ),
                yc.CategoryElem(
                    'mirrors', sub_elem=yc.StrElem()
                ),
                yc.ListElem(
                    'repos', sub_elem=yc.StrElem()
                ),
                yc.CategoryElem(
                    'upstreams', sub_elem=yc.KeyedElem(
                        elements=[yc.StrElem('install_tree')]
                    )
                ),
            ],
            help_text='Spack environment configuration file.'
        )
    ]
