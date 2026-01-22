from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple

import yc_yaml
import yaml_config as yc
from pavilion.test_config.file_format import TestConfigLoader, TestSuiteLoader
from pavilion.micro import first
from pavilion.errors import TestConfigError


TestConfig = Dict[str, Any]


class TestSuite:
    CONFIG_NAMES = ("suite", "hosts", "platforms", "modes")

    def __init__(self, path: Path, cfg_label: str):
        self.path = path
        self.cfg_label = cfg_label
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
            return first(cfg for cfg in self.configs if cfg.stem.strip("s") == cfg_type)
        elif cfg_type == "suite":
            return self.path

        return None

    def load(self, cfg_type: str, partial: bool = False) -> yc.ConfigDict:
        """Load the config of the given type from the suite."""

        path = self.config_path(cfg_type)

        if path is None:
            return yc.ConfigDict()

        if self.is_suite_dir or cfg_type == "suite":
            loader = self._suite_loader
        else:
            loader = self._loader

        cfg = self._safe_load_config(cfg_type, path, loader)
        cfg = loader.normalize(cfg)

        if cfg_type != "suite":
            cfg["suite"] = self.name
            # TODO: Do this the right way - HW
            cfg["suite_path"] = str(self.path)
            cfg["cfg_label"] = self.cfg_label

        return cfg

    def load_platform(self, platform: str) -> yc.ConfigDict:
        """Load the plaform with the given name."""

        cfg = self.load("platform").get(platform)

        if cfg is None:
            return yc.ConfigDict()

        cfg["platform"] = platform

        return cfg

    def load_host(self, host: str) -> yc.ConfigDict:
        """Load the host with the given name."""

        cfg = self.load("host").get(host)

        if cfg is None:
            return yc.ConfigDict()

        cfg["host"] = host

        return cfg

    def load_mode(self, mode: str) -> yc.ConfigDict:
        """Load the mode with the given name."""

        cfg = self.load("mode").get(mode, {})

        if cfg is None:
            return yc.ConfigDict()

        cfg["mode+"] = [mode]

        return cfg

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

    def load_test(self, test_name: str) -> yc.ConfigDict:
        """"Get the (unresolved) test config with the specified name."""

        cfg = self.load("suite").get(test_name)

        if cfg is None:
            return yc.ConfigDict()

        cfg["name"] = test_name
        cfg["suite"] = self.name
        # TODO: Do this the right way - HW
        cfg["suite_path"] = str(self.path)
        cfg["cfg_label"] = self.cfg_label

        return cfg

    def ancestors(self,
                  test_name: str,
                  platform_cfg: yc.ConfigDict,
                  host_cfg: yc.ConfigDict) -> List[Tuple[str, str, yc.ConfigDict]]:
        """Get a list of configs of the test's ancestors, including the test itself."""

        config = self.load_test(test_name)

        configs = [("test_config", test_name, config)]
        visited = [test_name]

        parent_name = config.get("inherits_from")

        while parent_name is not None:
            parent = self.load_test(parent_name)

            try:
                configs.append(("test", parent_name, self._loader.normalize(parent)))
            except (TypeError, KeyError, ValueError) as err:
                    raise TestConfigError(
                        "Test '{}' in suite '{}' has an error.\n"
                        "See 'pav show test_config' for the pavilion test config format."
                        .format(test_name, self.path), prior_error=err)

            visited.append(parent_name)
            parent_name = parent.get("inherits_from")

            if parent_name in visited:
                raise TestConfigError(
                    "Tests in suite '{}' have dependencies on {} that could not be resolved."
                    .format(suite_path, tuple(depended_on_by.keys())))

        configs.append(("host", host_cfg.get("host"), host_cfg))
        configs.append(("platform", platform_cfg.get("platform"), platform_cfg))
        configs.append(("base", "base", self._loader.load_empty()))

        return configs

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
