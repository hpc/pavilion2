import fnmatch
import inspect
from pathlib import Path
import sys
import time
import types
import unittest
import warnings
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
LIB_DIR = THIS_FILE.parents[1]
sys.path.insert(0, str(LIB_DIR))

class TestCaseEx(unittest.TestCase):
    """A unittest.TestCase with added features."""

    # Skip any tests that match these globs.
    SKIP = []
    # Only run tests that match these globs.
    ONLY = []

    def setUp(self) -> None:
        """Moving from the old camel case names to the standard naming scheme."""
        self.set_up()

    def tearDown(self) -> None:
        self.tear_down()

    def set_up(self):
        """Dummy set up function."""
        pass

    def tear_down(self):
        """Dummy tear down function"""
        pass

    def __getattribute__(self, item):
        """Override the builtin __getattribute__ so that tests skipped via command line
        options are properly 'wrapped'."""
        attr = super().__getattribute__(item)

        cls = super().__getattribute__('__class__')
        cname = cls.__name__.lower()
        fname = Path(inspect.getfile(cls)).with_suffix('').name.lower()

        # Wrap our test functions in a function that dynamically wraps
        # them so they only execute under certain conditions.
        if (isinstance(attr, types.MethodType) and
                attr.__name__.startswith('test_')):

            name = attr.__name__[len('test_'):].lower()

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


class ColorResult(unittest.TextTestResult):
    """Provides colorized results for the python unittest library."""

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
        self.showAll = None
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        """Write out the test description (with shading)."""
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.GREY)
            self.stream.write(self.getDescription(test))
            self.stream.write(self.COLOR_RESET)
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test):
        """Write the success text in green."""
        self.stream.write(self.GREEN)
        super().addSuccess(test)
        self.stream.write(self.COLOR_RESET)

    def addFailure(self, test, err):
        """Write the Failures in magenta."""
        self.stream.write(self.MAGENTA)
        super().addFailure(test, err)
        self.stream.write(self.COLOR_RESET)

    def addError(self, test, err):
        """Write errors in red."""
        self.stream.write(self.RED)
        super().addError(test, err)
        self.stream.write(self.COLOR_RESET)

    def addSkip(self, test, reason):
        """Note skips in cyan."""
        self.stream.write(self.CYAN)
        super().addSkip(test, reason)
        self.stream.write(self.COLOR_RESET)


class BetterRunner(unittest.TextTestRunner):
    """A slightly better 'TextTestRunner' with nicer output."""

    # pylint: disable=invalid-name
    def run(self, test):
        "Run the given test case or test suite."
        result = self._makeResult()
        unittest.registerResult(result)
        result.failfast = self.failfast
        result.buffer = self.buffer
        result.tb_locals = self.tb_locals
        with warnings.catch_warnings():
            if self.warnings:
                # if self.warnings is set, use it to filter all the warnings
                warnings.simplefilter(self.warnings)
                # if the filter is 'default' or 'always', special-case the
                # warnings from the deprecated unittest methods to show them
                # no more than once per module, because they can be fairly
                # noisy.  The -Wd and -Wa flags can be used to bypass this
                # only when self.warnings is None.
                if self.warnings in ['default', 'always']:
                    warnings.filterwarnings('module',
                                            category=DeprecationWarning,
                                            message=r'Please use assert\w+ instead.')
            startTime = time.time()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()
            try:
                test(result)
            finally:
                stopTestRun = getattr(result, 'stopTestRun', None)
                if stopTestRun is not None:
                    stopTestRun()
            stopTime = time.time()
        timeTaken = stopTime - startTime
        result.printErrors()
        if hasattr(result, 'separator2'):
            self.stream.writeln(result.separator2)
        skipped = 0
        try:
            results = map(len, (result.expectedFailures,
                                result.unexpectedSuccesses,
                                result.skipped))
        except AttributeError:
            pass
        else:
            _, _, skipped = results

        run = result.testsRun - skipped

        self.stream.writeln("Ran %d test%s in %.3fs" %
                            (run, run != 1 and "s" or "", timeTaken))
        self.stream.writeln()
        failed, errored = len(result.failures), len(result.errors)
        passed = run - failed - errored
        run = 0.01 if run == 0 else run  # Deal with potential divide_by_zero errors
        self.stream.writeln(
            'Passed:  {:5d} -- {}%'
                .format(passed, round(float(passed)/run * 100)))
        self.stream.writeln(
            'Failed:  {:5d} -- {}%'
                .format(failed, round(float(failed)/run * 100)))
        self.stream.writeln(
            'Errors:  {:5d} -- {}%'
                .format(errored, round(float(errored)/run * 100)))
        self.stream.writeln(
            '\x1b[36mSkipped: {:5d} -- {}% (of run + skipped)\x1b[0m'
                .format(skipped, round(float(skipped)/(run+skipped) * 100)))

        self.stream.write('\n')
        if not result.wasSuccessful():
            self.stream.writeln("FAILED")
        else:
            self.stream.writeln("OK")

        return result
