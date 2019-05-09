import fnmatch
from hashlib import sha1
import os
from pathlib import Path
import tempfile
import unittest
import types
import inspect

from pavilion import arguments
from pavilion import config
from pavilion.utils import cprint


class PavTestCase(unittest.TestCase):
    """This is a base class for other test suites."""

    PAV_LIB_DIR = Path(__file__).resolve().parent
    TEST_DATA_ROOT = PAV_LIB_DIR.parents[1]/'test'/'test_data'

    PAV_CONFIG_PATH = TEST_DATA_ROOT/'pav_config_dir'/'pavilion.yaml'

    TEST_URL = 'https://github.com/lanl/Pavilion/archive/master.zip'

    # Skip any tests that match these globs.
    SKIP = []
    # Only run tests that match these globs.
    ONLY = []

    def __init__(self, *args, **kwargs):

        with self.PAV_CONFIG_PATH.open() as cfg_file:
            raw_pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        raw_pav_cfg.config_dirs = [self.TEST_DATA_ROOT/'pav_config_dir',
                                   self.PAV_LIB_DIR]

        raw_pav_cfg.working_dir = Path('/tmp')/os.getlogin()/'pav_tests'

        cfg_dir = raw_pav_cfg.working_dir/'pav_cfgs'
        if not cfg_dir.exists():
            cfg_dir.mkdir()

        cfg_path = Path(tempfile.mktemp(
            suffix='.yaml',
            dir=str(cfg_dir)))

        with cfg_path.open('w') as pav_cfg_file:
            config.PavilionConfigLoader().dump(pav_cfg_file,
                                               raw_pav_cfg)

        with cfg_path.open() as cfg_file:
            self.pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        self.pav_cfg.pav_cfg_file = cfg_path

        # Create the basic directories in the working directory
        for path in [self.pav_cfg.working_dir,
                     self.pav_cfg.working_dir/'builds',
                     self.pav_cfg.working_dir/'tests',
                     self.pav_cfg.working_dir/'suites',
                     self.pav_cfg.working_dir/'downloads']:
            if not path.exists():
                os.makedirs(str(path), exist_ok=True)

        self.tmp_dir = tempfile.TemporaryDirectory()

        # We have to get this to set up the base argument parser before
        # plugins can add to it.
        _ = arguments.get_parser()
        super().__init__(*args, **kwargs)

    def __getattribute__(self, item):
        """When the unittest framework wants a test, check if the test
        is in the SKIP or ONLY lists, and skip it as appropriate. Only
        test methods are effected by this.
        A test is in the SKIP or ONLY list if the filename (minus extension),
        class name, .

        """
        attr = super().__getattribute__(item)

        cls = super().__getattribute__('__class__')
        cname = cls.__name__.lower()
        fname = Path(inspect.getfile(cls)).with_suffix('').name

        # Wrap our test functions in a function that dynamically wraps
        # them so they only execute under certain conditions.
        if (isinstance(attr, types.MethodType) and
                attr.__name__.startswith('test_')):

            name = attr.__name__[len('test_'):]

            if self.SKIP:
                for skip_glob in self.SKIP:
                    skip_glob = skip_glob.lower()
                    if (fnmatch.fnmatch(name, skip_glob) or
                            fnmatch.fnmatch(cname, skip_glob) or
                            fnmatch.fnmatch(fname, skip_glob)):
                        return unittest.skip("via cmdline")(attr)
                return attr

            if self.ONLY:
                for only_glob in self.ONLY:
                    only_glob = only_glob.lower()
                    if (fnmatch.fnmatch(name, only_glob) or
                            fnmatch.fnmatch(cname, only_glob) or
                            fnmatch.fnmatch(fname, only_glob)):
                        return attr
                return unittest.skip("via cmdline")(attr)

        # If it isn't altered or explicitly returned above, just return the
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

        for base_dir, cdirs, cfiles in os.walk(str(path)):
            base_dir = Path(base_dir)
            for cdir in cdirs:
                self.assert_((base_dir/cdir).is_dir(),
                             "Directory in softlink dir is a softlink (it "
                             "shouldn't be).")

            for file in cfiles:
                file_path = base_dir/file
                self.assert_(file_path.is_symlink(),
                             "File in softlink dir '{}' is not a softlink."
                             .format(file_path))

                target_path = file_path.resolve()
                self.assert_(target_path.exists(),
                             "Softlink target '{}' for link '{}' does not "
                             "exist."
                             .format(target_path, file_path))

    def _cmp_files(self, a_path, b_path):
        """Compare two files.
        :param Path a_path:
        :param Path b_path:
        """

        with a_path.open('rb') as a_file, b_path.open('rb') as b_file:
            self.assertEqual(a_file.read(), b_file.read(),
                             "File contents mismatch for {} and {}."
                             .format(a_path, b_path))

    def _cmp_tree(self, a, b):
        """Compare two directory trees, including the contents of all the
        files."""

        a_walk = list(os.walk(str(a)))
        b_walk = list(os.walk(str(b)))

        # Make sure these are in the same order.
        a_walk.sort()
        b_walk.sort()

        while a_walk and b_walk:
            a_dir, a_dirs, a_files = a_walk.pop(0)
            b_dir, b_dirs, b_files = b_walk.pop(0)
            a_dir = Path(a_dir)
            b_dir = Path(b_dir)

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
                a_path = a_dir/file
                b_path = b_dir/file

                # We know the file exists in a, does it in b?
                self.assert_(b_path.exists(),
                             "File missing from archive b '{}'".format(b_path))

                self._cmp_files(a_path, b_path)

        self.assert_(not a_walk and not b_walk,
                     "Left over directory contents in a or b: {}, {}"
                     .format(a_walk, b_walk))

    @staticmethod
    def get_hash(fn):
        """ Get a sha1 hash of the file at the given path.
        :param Path fn:
        :return:
        """
        with fn.open('rb') as file:
            sha = sha1()
            sha.update(file.read())
            return sha.hexdigest()

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



