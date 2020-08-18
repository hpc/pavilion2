
from pathlib import Path
import subprocess
import yaml_config as yc


class SpackEnvConfig(yc.YamlConfigLoader):

    ELEMENTS = [
        yc.KeyedElem(
            'spack', elements=[
                yc.KeyedElem(
                    'config', elements=[
                        yc.StrElem('install_tree'),
                        yc.StrElem('build_jobs', default=6)
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
                        elements=[yc.StrElem('install_tree'),
                                  yc.CategoryElem('modules',
                                    sub_elem=yc.StrElem())])
                ),
            ]
        )
    ]

class SpackEnvBuilder:
    """Creates the spack.yaml file, so each test can spin up it's own spack
    environement."""

    def __init__(self, spack_config, build_dir):

        # Set the spack env file's configs based on the passed spack_config.
        config = {
            'spack': {
                'config': {
                    # Spack packages will be built in the specified build_dir.
                    'install_tree': str(build_dir),
                    'build_jobs': spack_config['build_jobs']
                },
                'mirrors': spack_config['mirrors'],
                'repos': spack_config['repos'],
                'upstreams': spack_config['upstreams']
            }
        }

        # Creates the spack environment file in the specified build_dir.
        spack_env_config = build_dir/'spack.yaml'
        with open(spack_env_config, "w+") as spack_env_file:
            SpackEnvConfig().dump(spack_env_file, values=config)
