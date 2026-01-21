from pathlib import Path
from typing import Any, Optional

import yaml_config as yc
from pavilion.test_config.file_format import TestConfigLoader, TestSuiteLoader
from pavilion.micro import first


TestConfig = Dict[str, Any]


class TestSuite:
    CONFIG_NAMES = ("suite", "hosts", "platforms", "modes")

    def __init__(self, path: Path):
        self.path = path
        self.is_suite_dir = path.is_dir()
        self.name = path.stem
        self._loader = TestConfigLoader()
        self._suite_loader = TestSuiteLoader()

    @property
    def files(self) -> List[Path]:
        """Get a list of all files comprising the suite."""

        return self.path.iterdir()

    @property
    def configs(self) ->  List[Path]:
        """Get a list of all configs contained within the suite, including the suite config."""

        if self.is_suite_dir:
            return [path for path in self.path.iterdir() if path.stem in self.CONFIG_NAMES]

        return [self.path]

    def config_path(self, cfg_type: str) -> Optional[Path]:
        """Get the path to the config of the given type, if it exists."""

        if self.is_suite_dir:
            return first(cfg in self.configs if cfg.stem.strip("s") == cfg_type)
        elif cfg_type == "suite":
            return self.path

        return None

    def load(self, cfg_type: str) -> TestConfig:
        """Load the config of the given type from the suite."""

        path = self.config_path(cfg_type)

        if path is None:
            return {}

        if self.is_suite_dir and cfg_type != "suite":
            loader = self._suite_loader
        else:
            loader = self._loader

        return self._safe_load_config(cfg_type, path, loader)

    @property
    def test_names(self) -> List[str]:
        """Get a list of names of tests in the suite."""

        return list(self.load("suite").keys())

    @property
    def hosts(self) -> List[str]:
        """Get a list of hosts in the suite."""

        return list(self.load("host").keys())

    @property
    def platforms(self) -> List[str]:
        """Get a list of platforms in the suite."""

        return list(self.load("platform").keys())

    @property
    def modes(self) -> List[str]:
        """Get a list of modes in the suite."""

        return list(self.load("mode").keys())

    @staticmethod
    def _safe_load_config(cfg_type: str, path: Path, loader: yc.YamlConfigLoader) -> TestConfig:
        """Given a path to a config, load the config, and raise an appropriate
        error if it can't be loaded"""

        try:
            with path.open() as cfg_file:
                raw_cfg = loader.load_raw(cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open {} config '{}'"
                                  .format(cfg_type, path), prior_error=err)
        except ValueError as err:
            raise TestConfigError(
                "{} config '{}' has invalid value."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except KeyError as err:
            raise TestConfigError(
                "{} config '{}' has an invalid key."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "{} config '{}' has a YAML Error"
                .format(cfg_type.capitalize(), path), prior_error=err)
        except TypeError as err:
            raise TestConfigError(
                "Structural issue with {} config '{}'"
                .format(cfg_type, path), prior_error=err)

        return raw_cfg
