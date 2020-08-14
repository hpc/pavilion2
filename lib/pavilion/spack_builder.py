
from pathlib import Path
import subprocess
import yaml_config as yc


class SpackConfig(yc.YamlConfigLoader):

    ELEMENTS = [
        yc.KeyedElem(
            'spack', elements=[
                yc.KeyedElem(
                    'config', elements=[
                        yc.StrElem(
                            'install_tree')
                    ]
                ),
                yc.CategoryElem(
                    'mirrors', sub_elem=yc.StrElem()
                ),
                yc.ListElem(
                    'repos', sub_elem=yc.StrElem()
                ),
            ]
        )
    ]

class SpackEnvBuilder:
    """Creates the spack.yaml file, so each test can spin up it's own spack
    environement."""

    def __init__(self, pav_cfg, spack_config, build_dir):

        self.build_dir = build_dir

        # Set the install tree to the build dir
        config = {
            'spack': {
                'config': {
                    'install_tree': str(build_dir),
                },
                'mirrors': spack_config['mirrors'],
                'repos': spack_config['repos']
            }
        }

        spack_config_path = build_dir/'spack.yaml'
        with open(spack_config_path, "w+") as spack_env_file:
            SpackConfig().dump(spack_env_file, values=config)
