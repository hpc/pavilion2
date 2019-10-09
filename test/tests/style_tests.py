from pavilion.unittest import PavTestCase
import unittest
import subprocess
import distutils.spawn

_PYLINT3_PATH = distutils.spawn.find_executable('pylint3')
if _PYLINT3_PATH is None:
    _PYLINT3_PATH = distutils.spawn.find_executable('pylint')


class StyleTests(PavTestCase):

    @unittest.skipIf(not _PYLINT3_PATH, "pylint3 not found.")
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
        ]

        cmd = [
            _PYLINT3_PATH,
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
