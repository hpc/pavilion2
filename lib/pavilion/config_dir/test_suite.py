from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple, Set

import yc_yaml
import yaml_config as yc
from pavilion.test_config.file_format import TestSuiteLoader
from pavilion.micro import first, set_default, listfilter
from pavilion.errors import TestConfigError
from .utils import get_yaml_files
from .load_config import safe_load_config


TestConfig = Dict[str, Any]


class TestSuite:
    """Represents a single test suite."""

    CONFIG_NAMES = ("suite", "hosts", "platforms", "modes")

    def __init__(self, path: Path, cfg_label: str):
        self.path = path
        self.cfg_label = cfg_label
        self.is_suite_dir = path.is_dir()
        self.name = path.stem
        self._loader = TestSuiteLoader()
        self._ancestors = {} # ancestor cache

    @property
    @lru_cache(maxsize=None)
    def files(self) -> List[Path]:
        """Get a list of all files comprising the suite."""

        if not self.is_suite_dir:
            return [self.path]

        return list(self.path.iterdir())

    @property
    @lru_cache(maxsize=None)
    def configs(self) ->  List[Path]:
        """Get a list of all config paths contained within the suite, including the suite config."""

        if self.is_suite_dir:
            return listfilter(lambda x: x.stem in self.CONFIG_NAMES, get_yaml_files(self.path))

        return [self.path]

    def config_path(self, cfg_type: str) -> Optional[Path]:
        """Get the path to the config of the given type, if it exists."""

        if self.is_suite_dir:
            paths = listfilter(lambda x: x.stem.strip("s") == cfg_type, self.configs)

            if len(paths) > 1:
                raise TestConfigError(f"Multiple {cfg_type }config files found in suite "
                                      f"{self.name}: {paths}")
            return first(paths)

        elif cfg_type == "suite":
            return self.path

        return None

    @lru_cache(maxsize=None)
    def load(self, cfg_type: str, cfg_name: str) -> yc.ConfigDict:
        """Load the config of the given type from the suite."""

        if not self.is_suite_dir and cfg_type != "suite":
            return yc.ConfigDict()

        path = self.config_path(cfg_type)

        if path is None:
            return yc.ConfigDict()

        cfg = safe_load_config(cfg_type, path, self._loader)

        try:
            cfg = self._loader.normalize(cfg)
        except (TypeError, KeyError, ValueError) as err:
            raise TestConfigError(
                "Config '{}' in suite '{}' has an error.\n"
                "See 'pav show test_config' for the pavilion test config format."
                .format(cfg_name, self.path), prior_error=err)

        cfg = cfg.get(cfg_name)

        if cfg is None:
            return yc.ConfigDict()

        if cfg_type == "suite":
            cfg["name"] = cfg_name
            cfg["suite"] = self.name
            # TODO: Do this the right way - HW
            cfg["suite_path"] = str(self.path)
            cfg["cfg_label"] = self.cfg_label
        elif cfg_type == "mode":
            cfg["modes+"] = cfg_name
        else:
            cfg[cfg_type] = cfg_name

        return cfg

    @lru_cache(maxsize=None)
    def load_raw(self, cfg_type: str) -> Dict[str, Any]:
        """Load the config of the given type as raw YAML, without normalizing."""

        if not self.is_suite_dir and cfg_type != "suite":
            return {}

        path = self.config_path(cfg_type)

        if path is None:
            return {}

        return safe_load_config(cfg_type, path, self._loader)

    @property
    def test_names(self) -> List[str]:
        """Get a list of names of tests in the suite."""

        return self.get_names("suite")

    def get_names(self, cfg_type: str) -> List[str]:
        """Get a list of names of the given config type."""

        return list(self.load_raw(cfg_type).keys())

    def ancestors(self, test_name: str,
                  visited: Optional[Set[str]] = None) -> List[Tuple[str, str, yc.ConfigDict]]:
        """Get a list of configs of the test's ancestors, including the test itself, but not
        including the base config."""

        if test_name in self._ancestors:
            return self._ancestors.get(test_name)

        visited = set_default(visited, set())
        visited.add(test_name)

        config = self.load("suite", test_name)

        parent_name = config.get("inherits_from")

        if parent_name in visited:
            raise TestConfigError(f"Tests in suite '{self.path}' have a circular dependency.")

        res = [("test", test_name, config)]

        if parent_name is None:
            return res

        return res + self.ancestors(parent_name, visited)