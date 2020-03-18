from pavilion.unittest import PavTestCase
import distutils.spawn
import subprocess
import unittest

_SPHINX_PATH = distutils.spawn.find_executable('sphinx-build')


class DocTests(PavTestCase):

    @unittest.skipIf(_SPHINX_PATH is None, "Could not find sphinx.")
    def test_doc_build(self):
        """Build the documentation and check for warnings/errors."""

        subprocess.call(['make', 'clean'],
                        cwd=(self.PAV_ROOT_DIR/'docs').as_posix(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        cmd = ['make', 'html']

        proc = subprocess.Popen(
            cmd,
            cwd=(self.PAV_ROOT_DIR/'docs').as_posix(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        out, _ = proc.communicate(timeout=20)
        out = out.decode('utf8')
        result = proc.poll()

        self.assertEqual(result, 0,
                         msg="Error building docs:\n{}".format(out))

        warnings = []
        for line in out.split('\n'):
            if 'WARNING' in line:
                warnings.append(line)

        self.assertTrue(len(warnings) == 0,
                        msg='{} warnings in documentation build:\n{}\n\n{}'
                            .format(len(warnings), '\n'.join(warnings), out))
