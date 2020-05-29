from pavilion.unittest import PavTestCase
import unittest
import subprocess
import distutils.spawn

_PYLINT_PATH = distutils.spawn.find_executable('pylint')
if _PYLINT_PATH is None:
    _PYLINT_PATH = distutils.spawn.find_executable('pylint3')


class StyleTests(PavTestCase):

    @unittest.skipIf(not _PYLINT_PATH, "pylint3 not found.")
    def test_style(self):

        enabled = [
            'logging',
            'format',
            'imports',
            'exceptions',
            'classes',
            'basic',
        ]

        disabled = [
            'missing-docstring',
            'consider-using-enumerate',
            'bad-builtin',
        ]

        cmd = [
            _PYLINT_PATH,
            '--disable=all',
            '--enable={}'.format(','.join(enabled)),
            '--disable={}'.format(','.join(disabled)),
            '--output-format=text',
            '--msg-template="{line},{column}:  {msg}  ({symbol} - {msg_id})"',
            '--reports=n',
            '--max-line-length=80',
            self.PAV_LIB_DIR.as_posix()
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            self.fail('\n' + stdout.decode('utf8'))
