from pathlib import PosixPath, Path
from typing import List, Union, Optional, Iterator, Any, Dict

from pavilion.path_utils import Pathlike, path_product, exists
from pavilion.micro import set_default


class ConfigInfo:
    def __init__(self, name: str, type: str, path: Path, label: str = None,
        from_suite_dir: bool = False):

        self.name = name
        self.type = type
        self.label = label
        self.path = path
        self.from_suite_dir = from_suite_dir


class ConfigDirectory(PosixPath):
    PAV_CONFIG_FNAME = "pavilion.yaml"
    DEFAULT_PAV_ROOT = Path(__file__).resolve().parents[2]
    PAV_LIB_FN = "pav-lib.bash"

    SUITES_DIR_NAME = "suites"
    TEST_SRC_DIR_NAME = "test_src"
    # This directory is deprecated, but we'll keep it around for now
    TESTS_DIR_NAME = "tests"

    CONFIG_DIRNAMES = {
        "host": "hosts",
        "mode": "modes",
        "platform": "platforms",
        "suite": "suites",
        "test": "tests"
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

        self.suites_dir = self / self.SUITES_DIR_NAME
        self.test_src_dir = self / self.TEST_SRC_DIR_NAME
        self.tests_dir = self / self.TESTS_DIR_NAME

        self._test_counters = {}

        return self

    def find_file(self,
                  file: Pathlike,
                  subdirs: Union[List[Pathlike], Pathlike, None] = None) -> Iterator[Path]:
        """Look for the given file and return a full path to it. Relative paths
        are searched for under each element of 'sub_dirs', if it exists.

        :param file: The path to the file.
        :param sub_dirs: The subdirectory (or list of subdirectories) in which to
            search in each directory.
        :returns: An iterator over all matching files in the searched subdirectories.
        """

        file = Path(file)

        if file.is_absolute():
            if file.exists():
                return file
            else:
                return None

        if subdirs is None or len(subdirs) == 0:
            paths = [self]
        else:
            paths = path_product([self], subdirs)

        return filter(exists, path_product(paths, [file]))

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
