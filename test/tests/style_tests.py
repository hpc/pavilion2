from pavilion.unittest import PavTestCase
import unittest
import subprocess
import distutils.spawn

_PYLINT_PATH = distutils.spawn.find_executable('pylint')
if _PYLINT_PATH is None:
    _PYLINT_PATH = distutils.spawn.find_executable('pylint3')

_MIN_PYLINT_VERSION = (2, 5, 0)


def has_pylint():
    """Check for a reasonably up-to-date pylint."""

    if _PYLINT_PATH is None:
        return False

    result = subprocess.run([_PYLINT_PATH, '--version'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in result.stdout.decode().split('\n'):
        if line.startswith('pylint'):
            version = line.split()[1]
            break
    else:
        return False

    version = tuple(int(vpart) for vpart in version.split('.'))

    if version < _MIN_PYLINT_VERSION:
        return False

    return True


class StyleTests(PavTestCase):

    @unittest.skipIf(not _PYLINT_PATH, "pylint3 not found.")
    @unittest.skipIf(not has_pylint(), "pylint version insufficient.")
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
