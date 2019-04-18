import fnmatch
import os
import tempfile
import unittest
import types

from pavilion import config
from pavilion.utils import cprint


class PavTestCase(unittest.TestCase):
    """This is a base class for other test suites."""

    TEST_DATA_ROOT = os.path.realpath(__file__)
    for i in range(3):
        TEST_DATA_ROOT = os.path.dirname(TEST_DATA_ROOT)
    TEST_DATA_ROOT = os.path.join(TEST_DATA_ROOT, 'test', 'test_data')

    PAV_CONFIG_PATH = os.path.join(TEST_DATA_ROOT,
                                   'pav_config_dir',
                                   'pavilion.yaml')
    PAV_LIB_DIR = os.path.dirname(__file__)

    TEST_URL = 'https://github.com/lanl/Pavilion/archive/2.0.zip'

    # Skip any tests that match these globs.
    SKIP = []
    # Only run tests that match these globs.
    ONLY = []

    def __init__(self, *args, **kwargs):

        with open(self.PAV_CONFIG_PATH) as cfg_file:
            self.pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        self.pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT,
                                                 'pav_config_dir'),
                                    self.PAV_LIB_DIR]

        self.tmp_dir = tempfile.TemporaryDirectory()

        self.pav_cfg.working_dir = '/tmp/{}/pav_tests/'.format(os.getlogin())

        # Create the basic directories in the working directory
        for path in [self.pav_cfg.working_dir,
                     os.path.join(self.pav_cfg.working_dir, 'builds'),
                     os.path.join(self.pav_cfg.working_dir, 'tests'),
                     os.path.join(self.pav_cfg.working_dir, 'suites'),
                     os.path.join(self.pav_cfg.working_dir, 'downloads')]:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

        super().__init__(*args, **kwargs)

    def __getattribute__(self, item):
        attr = super().__getattribute__(item)

        # Wrap our test functions in a function that dynamically wraps
        # them so they only execute under certain conditions.
        if (isinstance(attr, types.MethodType) and
                attr.__name__.startswith('test_')):

            name = attr.__name__[len('test_'):]

            if self.SKIP:
                for skip_glob in self.SKIP:
                    if fnmatch.fnmatch(name, skip_glob):
                        return unittest.skip("via cmdline")(attr)
                return attr

            if self.ONLY:
                for only_glob in self.ONLY:
                    if fnmatch.fnmatch(name, only_glob):
                        return attr
                return unittest.skip("via cmdline")(attr)

        # If it isn't altered or explicitely returned above, just return the
        # attribute.
        return attr

    @classmethod
    def set_skip(cls, globs):
        """Skip tests whose names match the given globs."""

        cls.SKIP = globs

    @classmethod
    def set_only(cls, globs):
        """Only run tests whos names match the given globs."""
        cls.ONLY = globs

    def _is_softlink_dir(self, path):
        """Verify that a directory contains nothing but softlinks whose files
        exist. Directories in a softlink dir should be real directories
        though."""

        for base_dir, cdirs, cfiles in os.walk(path):
            for cdir in cdirs:
                self.assert_(os.path.isdir(os.path.join(base_dir, cdir)),
                             "Directory in softlink dir is a softlink (it shouldn't be).")

            for file in cfiles:
                file_path = os.path.join(base_dir, file)
                self.assert_(os.path.islink(file_path),
                             "File in softlink dir '{}' is not a softlink."
                             .format(file_path))

                target_path = os.path.realpath(file_path)
                self.assert_(os.path.exists(target_path),
                             "Softlink target '{}' for link '{}' does not exist."
                             .format(target_path, file_path))

    def _cmp_files(self, a_path, b_path):
        """Compare two files."""

        with open(a_path, 'rb') as a_file, open(b_path, 'rb') as b_file:
            self.assertEqual(a_file.read(), b_file.read(),
                             "File contents mismatch for {} and {}."
                             .format(a_path, b_path))

    def _cmp_tree(self, a, b):
        """Compare two directory trees, including the contents of all the
        files."""

        a_walk = list(os.walk(a))
        b_walk = list(os.walk(b))

        # Make sure these are in the same order.
        a_walk.sort()
        b_walk.sort()

        while a_walk and b_walk:
            a_dir, a_dirs, a_files = a_walk.pop(0)
            b_dir, b_dirs, b_files = b_walk.pop(0)

            self.assertEqual(
                sorted(a_dirs), sorted(b_dirs),
                "Extracted archive subdir mismatch for '{}' {} != {}"
                .format(a, a_dirs, b_dirs))

            # Make sure these are in the same order.
            a_files.sort()
            b_files.sort()

            self.assertEqual(a_files, b_files,
                             "Extracted archive file list mismatch. "
                             "{} != {}".format(a_files, b_files))

            for file in a_files:
                # The file names have are been verified as the same.
                a_path = os.path.join(a_dir, file)
                b_path = os.path.join(b_dir, file)

                # We know the file exists in a, does it in b?
                self.assert_(os.path.exists(b_path),
                             "File missing from archive b '{}'".format(b_path))

                self._cmp_files(a_path, b_path)

        self.assert_(not a_walk and not b_walk,
                     "Left over directory contents in a or b: {}, {}"
                     .format(a_walk, b_walk))

    _cprint = staticmethod(cprint)


class ColorResult(unittest.TextTestResult):

    COLOR_BASE = '\x1b[{}m'
    COLOR_RESET = '\x1b[0m'
    BLACK = COLOR_BASE.format(30)
    RED = COLOR_BASE.format(31)
    GREEN = COLOR_BASE.format(32)
    YELLOW = COLOR_BASE.format(33)
    BLUE = COLOR_BASE.format(34)
    MAGENTA = COLOR_BASE.format(35)
    CYAN = COLOR_BASE.format(36)
    GREY = COLOR_BASE.format(2)
    BOLD = COLOR_BASE.format(1)

    def __init__(self, *args, **kwargs):
        self.stream = None
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.GREY)
            self.stream.write(self.getDescription(test))
            self.stream.write(self.COLOR_RESET)
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test):
        self.stream.write(self.GREEN)
        super().addSuccess(test)
        self.stream.write(self.COLOR_RESET)

    def addFailure(self, test, err):
        self.stream.write(self.MAGENTA)
        super().addFailure(test, err)
        self.stream.write(self.COLOR_RESET)

    def addError(self, test, err):
        self.stream.write(self.RED)
        super().addError(test, err)
        self.stream.write(self.COLOR_RESET)

    def addSkip(self, test, reason):
        self.stream.write(self.CYAN)
        super().addSkip(test, reason)
        self.stream.write(self.COLOR_RESET)



