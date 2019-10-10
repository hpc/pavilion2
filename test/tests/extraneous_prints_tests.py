from pavilion import plugins
from pavilion.unittest import PavTestCase
import re
import subprocess


class ExtraPrintsTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    IGNORE_RE = re.compile(r'ext[-_]print:\s*ignore')

    def test_for_extra_prints(self):
        """greps for unnecessary dbg_print statements."""

        # looks for unnecessary dbg_prints in lib/pavilion directory
        cmd = "grep -R -I '[^f]print(' ../lib/pavilion/ " \
              "--exclude=unittest.py --exclude=utils.py"
        proc = subprocess.Popen(cmd, shell=True)
        output, _ = proc.communicate()
        # Filter out lines with a comment saying they're ok.
        output = [o for o in output.split('\n') if
                  o and self.IGNORE_RE.search(o) is None]
        self.maxDiff = None
        self.assertEqual(output, [])

        tests_root = self.PAV_ROOT_DIR/'test'/'tests'

        # looks for unnecessary dbg_prints in test directory
        cmd = ["grep", "-R", "-i", "-I", "[^f]print("]
        excludes = [
            'extraneous_prints_tests.py',
            'blarg.py',
            'poof.py']
        cmd.extend(['--exclude={}'.format(excl) for excl in excludes])
        cmd.append(str(tests_root))

        proc = subprocess.Popen(cmd)
        output, _ = proc.communicate()
        self.maxDiff = None
        self.assertEqual(output.decode("utf-8"), '')
