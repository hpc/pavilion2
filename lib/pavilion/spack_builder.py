
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
                            'install_tree'
                        )]
                )]
        )]

class SpackEnvBuilder:
    """Creates the spack.yaml file, so each test can spin up it's own spack
    environement."""

    def __init__(self, pav_cfg, build_dir):

        self.spack_path = pav_cfg.spack_path
        self.build_dir = build_dir

        # Set the install tree to the build dir
        config = {
            'spack': {
                'config': {
                    'install_tree': str(build_dir)
                }
            }
        }

        spack_config_path = build_dir/'spack.yaml'
        with open(spack_config_path, "w+") as spack_env_file:
            SpackConfig().dump(spack_env_file, values=config)
