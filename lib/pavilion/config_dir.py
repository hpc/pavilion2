from pathlib import PosixPath, Path
from typing import List, Union, Optional, Iterator, Any, Dict

from pavilion.path_utils import Pathlike, path_product, exists
from pavilion.micro import set_default


class ConfigDirectory(PosixPath):

    PAV_CONFIG_FNAME = "pavilion.yaml"
    DEFAULT_PAV_ROOT = Path(__file__).resolve().parents[2]
    PAV_LIB_FN = "pav-lib.bash"

    SUITES_DIR_NAME = "suites"
    TEST_SRC_DIR_NAME = "test_src"
    # This directory is deprecated, but we'll keep it around for now
    TESTS_DIR_NAME = "tests"

    def __new__(cls, path: str, pav_config_file: Optional[Path] = None,
                pav_root: Optional[Path] = None):
        self = super().__new__(cls, path)

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
                  sub_dirs: Union[List[Pathlike], Pathlike, None] = None) -> Iterator[Path]:
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

        if subdirs is None or len(sub_dirs) == 0:
            paths = [self]
        else:
            paths = path_product([self], subdirs)

        return filter(exists, path_product(paths, [file]))

    def __deepcopy__(self, memo: Dict[str, Any]):
        if id(self) in memo:
            return memo[id(self)]

        return self.__class__.__new__(
                                self.__class__,
                                self.as_posix(),
                                self.pav_config_file,
                                self.pav_root)
