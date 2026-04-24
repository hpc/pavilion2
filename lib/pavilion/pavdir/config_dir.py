from itertools import chain
from pathlib import Path
from typing import List, Union, Optional, Iterator, Any, Dict

from .base_classes import PavDirectory
from pavilion.path_utils import Pathlike, path_product, exists, is_dir
from pavilion.micro import set_default
from pavilion.utils import get_yaml_fnames, is_yaml_file


class ConfigInfo:
    def __init__(self, name: str, type: str, path: Path, label: Optional[str] = None,
                 from_suite_dir: bool = False):
        self.name = name
        self.type = type
        self.label = label
        self.path = path
        self.from_suite_dir = from_suite_dir


class ConfigDirectory(PavDirectory):
    PAV_CONFIG_FNAME = "pavilion.yaml"
    DEFAULT_PAV_ROOT = Path(__file__).resolve().parents[2]
    PAV_LIB_FN = "pav-lib.bash"

    CONFIG_DIRNAMES = {
        "host": "hosts",
        "mode": "modes",
        "platform": "platforms",
        "suite": "suites",
        "test": "tests", # This directory is deprecated, but we'll keep it around for now
        "test_src": "test_src"
    }

    SUITE_CONFIG_FNAMES = {
        "host": "hosts.yaml",
        "mode": "modes.yaml",
        "platform": "platforms.yaml",
        "suite": "suite.yaml"
    }

    def __new__(cls, path: str, label: Optional[str] = None, pav_config_file: Optional[Path] = None,
                pav_root: Optional[Path] = None):
        self = super().__new__(cls, path)

        self.label = label
        self.pav_config_file = set_default(pav_config_file, self / self.PAV_CONFIG_FNAME)
        self.pav_root = set_default(pav_root, self.DEFAULT_PAV_ROOT)
        self.pav_lib_bash = self.pav_root / "bin" / self.PAV_LIB_FN

        self.suites_dir = self / self.CONFIG_DIRNAMES.get("suite")
        self.test_src_dir = self / self.CONFIG_DIRNAMES.get("test_src")
        self.tests_dir = self / self.CONFIG_DIRNAMES.get("test")

        self._test_counters = {}

        return self

    # TODO: Make cfg_type an Enum
    def find_configs(self, cfg_type: str, cfg_name: str,
                    suite_name: Optional[str] = None) -> List[ConfigInfo]:
        """This function returns a list of configs in the same order in which they should be
        applied."""

        # TODO: Rewrite to support all variants of .yaml suffix
        candidates = [self / self.CONFIG_DIRNAMES.get(cfg_type) / f"{cfg_name}.yaml"]

        if cfg_type == "suite":
            if suite_name is not None:
                # Add the suite.yaml file
                candidates.append(self / self.CONFIG_DIRNAMES.get(cfg_type) / cfg_name /
                                self.SUITE_CONFIG_FNAMES.get(cfg_type))
            else:
                # Look in the deprecated tests directory
                candidates.append(self / self.CONFIG_DIRNAMES.get("test")/ f"{cfg_name}.yaml")
        elif suite_name is not None:
            # Add the config file within the suite directory, which may or may not actually
            # contain the specified config.
            candidates.append(self / self.CONFIG_DIRNAMES.get("suite") / suite_name /
                              self.SUITE_CONFIG_FNAMES.get(cfg_type))

        configs = []

        for path in filter(exists, candidates):
            if path.name == "suites" or path.parent.name == "suites":
                from_suite_dir = True
            else:
                from_suite_dir = False

            configs.append(ConfigInfo(cfg_name, cfg_type, path, self.label, from_suite_dir))

        return configs

    def get_all_configs(self, cfg_type: str) -> Iterator[Path]:
        """Get all config files within this config directory of the specified type."""

        if cfg_type == "suite":
            bare_yaml_suites = filter(is_yaml_file, self.suites_dir.iterdir())
            suite_dirs = filter(is_dir, self.suites_dir.iterdir())
            suite_dir_suites = map(
                                append_const_file(self.SUITE_CONFIG_FNAMES.get(cfg_type)),
                                suite_dirs)
            suite_dir_suites = filter(exists, suite_dir_suites)

            return chain(self.get_all_configs("test"), bare_yaml_suites, suite_dir_suites)
        else:
            return filter(is_yaml_file, (self / self.CONFIG_DIRNAMES.get(cfg_type)).iterdir())

    def get_suite_path(self, suite_name: str) -> Iterator[Path]:
        """Given a suite name, return an iterator over all paths in this config directory to suites
        with that name. For suites organizes as suite directories, gives the path to the
        directory.

        Typically, there should only be one path, but we need to deal with the possibility that
        the suite exists in multiple locations."""

        fnames = get_yaml_fnames(suite_name)

        paths = list(path_product(self.suites_dir, fnames))
        paths.append(self.suites_dir / suite_name)
        paths.extend(path_product(self.tests_dir, fnames))

        return map(exists, paths)

    def get_suite_dir(self, suite_name: str) -> Optional[Path]:
        """Get the path to the suite directory with the given name, if it exists."""

        suite_dir = self.suites_dir / suite_name

        if suite_dir.exists():
            return suite_dir

        return None

    def find_test_src(self, fname: Pathlike, suite_name: Optional[str] = None) -> Iterator[Path]:
        """Given the name of a test source file, return the path to the file, if it exists."""

        paths = [self.test_src_dir / fname]

        if suite_name is not None:
            suite_dir = self.get_suite_dir(suite_name)

            if suite_dir is not None:
                paths.append(suite_dir / fname)

        return filter(exists, paths)

    # Create an alias just to prevent confusion due to the name
    find_extra_file = find_test_src