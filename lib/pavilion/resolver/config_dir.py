from pathlib import Path
from typing import List, Iterator, Optional

from .test_suite import TestSuite
from .utils import get_yaml_files, is_yaml_file, is_suite_dir, yaml_fnames
from pavilion.test_config.file_format import TestConfigLoader
from pavilion.errors import TestConfigError
from pavilion.micro import listmap
from pavilion.path_utils import append_suffix, exists


class ConfigDirectory:
    """Represents a single configuration directory."""

    DIRNAMES = {
                "test": "tests",
                "suite", "suites",
                "platform": "platforms",
                "host": "hosts",
                "mode": "modes",
                "series": "series"
                }

    def __init__(self, path: Path, label: str):
        self.path = path
        self.label = label
        self._loader = TestConfigLoader()

    @property
    def suites(self) -> List[TestSuite]:
        """Get a list of all test suites in this config directory."""

        tests_dir = self.path / self.DIRNAMES.get("test")
        suites_dir = self.path / self.DIRNAMES.get("suite")

        paths = get_yaml_files(tests_dir)
        paths.extend(filter(lambda x: is_yaml_file(x) or is_suite_dir(x), suites_dir.iterdir()))

        return listmap(lambda x: TestSuite(x, self.label), paths)

    def get_config_path(self, cfg_type: str, cfg_name: str) -> Optional[Path]:
        """Get the path to specified config, if it exists."""

        cfg_dir = self.path / self.DIRNAMES.get(cfg_type)
        possible_files = listmap(append_suffix(cfg_dir), yaml_fnames(cfg_name))

        if cfg_type == "suite":
            possible_files.append(cfg_dir / cfg_name)

        paths = listmap(exists, possible_files)

        if len(paths) > 1:
            raise TestConfigError(f"Multiple config files found for {cfg_type} config with name "
                                  f"{cfg_name}: {paths}")
        if len(paths) == 0:
            return None

        return paths[0]

    def get_config_paths(self, cfg_type: str) -> List[Path]:
        """Get a list of paths to all configs of the specified type (not including suite-specific)
        configs."""

        dirname = self.path / self.DIRNAMES.get(cfg_type)

        if not dirname.exists() or not dirname.is_dir():
            return []

        return get_yaml_files(dirname)

    def get_config_names(self, cfg_type: str) -> List[str]:
        """Get a list of all configs of the specified type contained within the config directory
        (not including suite-specific platforms)."""

        return listmap(lambda x: x.stem, self.get_config_paths(cfg_type))

    def load(self, cfg_type: str, cfg_name: str) -> yc.ConfigDict:
        """Load the config of the given type. Does not load auxiliary configs from within suites."""

        path = self.get_config_path(cfg_type, cfg_name)

        if path is None:
            return yc.ConfigDict()

        return self.load_from_path(path, cfg_type, cfg_name)

    def load_from_path(cfg_path: Path, cfg_type: str, cfg_name: str) -> yc.ConfigDict:
        """Load the config of the given type from the given path. Does not load auxiliary configs
        from within suites."""

        if cfg_type == "suite":
            return TestSuite(cfg_path, self.label).load(cfg_type, cfg_name)

        cfg = safe_load_config(cfg_type, cfg_path, self._loader)
        cfg = self._loader.normalize(cfg)

        if cfg_type == "mode":
            cfg["modes+"] = cfg_name
        else:
            cfg[cfg_type] = cfg_name

        return cfg
