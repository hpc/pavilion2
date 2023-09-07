import distutils.spawn
import os
import re
import io
import subprocess
import unittest
from pathlib import Path
from collections import defaultdict

from pavilion.unittest import PavTestCase

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

    if version.endswith(','):
        version = version[:-1]
    version = tuple(int(vpart) for vpart in version.split('.'))

    if version < _MIN_PYLINT_VERSION:
        return False

    return True


class StyleTests(PavTestCase):

    def test_has_style(self):
        """Check that we can perform style checking."""

        self.assertTrue(has_pylint(),
                        msg="Pylint is missing or has an insufficient version.")
        self.assertTrue(_PYLINT_PATH, msg="pylint3 not found.")

    @unittest.skipIf(not _PYLINT_PATH, "pylint3 not found.")
    @unittest.skipIf(not has_pylint(), "pylint version insufficient.")
    def test_style(self):
        """Perform style checking, if we can."""

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
            'raise-missing-from'
        ]

        cmd = [
            _PYLINT_PATH,
            '--disable=all',
            '--enable={}'.format(','.join(enabled)),
            '--disable={}'.format(','.join(disabled)),
            '--output-format=text',
            '--msg-template="{line},{column}:  {msg}  ({symbol} - {msg_id})"',
            '--reports=n',
            '--max-line-length=100',
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

    def test_debug_prints(self):
        """greps for unnecessary dbg_print statements."""

        matches = self.find_prints(self.PAV_ROOT_DIR/'lib'/'pavilion',
                                   excludes=['output.py'])
        test_matches = self.find_prints(
            self.PAV_ROOT_DIR/'test'/'tests',
            excludes=['style_tests.py', 'blarg.py', 'poof.py'])
        yaml_config_matches = self.find_prints(
            self.PAV_ROOT_DIR/'lib'/'yaml_config')
        test_ex_matches = self.find_prints(self.PAV_ROOT_DIR/'lib'/'unittest_ex')

        for match_set in test_matches, yaml_config_matches, test_ex_matches:
            for match, values in match_set.items():
                matches[match].extend(values)

        if matches:
            msg = io.StringIO()

            print("Found debug print statements:", file=msg)
            for match, values in matches.items():
                print('\n', match, file=msg)
                for line_num, line in values:
                    print("{:5d}: {}".format(line_num + 1, line[:60]), file=msg)

            self.fail(msg=msg.getvalue())

    # Skip a line if it has an '# ext-print: ignore' comment on it.
    SKIP_LINE_RE = re.compile(r'\S+.*#\s+ext[-_]print:\s*ignore')
    # Skip the next line if it is just an '# ext-print: ignore' comment.
    SKIP_NEXT_RE = re.compile(r'^\s*#\s+ext[-_]print:\s*ignore')

    PRINT_RE = re.compile(r'^\s*[^"\'#].*[^f]print\(')

    def test_string_continuation(self):
        """Find instances where strings continue across lines without a space
        between words."""

        bad_continuations = defaultdict(lambda: list())

        count = 0
        for search_path in (
                self.PAV_ROOT_DIR/'lib'/'pavilion',
                self.PAV_ROOT_DIR/'lib'/'yaml_config',
                self.PAV_ROOT_DIR/'lib'/'unittest_ex'):
            for path, _, filenames in os.walk(search_path):
                for fn in filenames:
                    if not fn.endswith('.py'):
                        continue

                    fn = "{}/{}".format(path, fn)
                    with open(fn) as file:
                        lines = file.readlines()
                        for i in range(len(lines)):
                            line = lines[i].strip()

                            # Skip short lines and the last line.
                            if len(line) < 2 or i+1 >= len(lines):
                                continue

                            next_line = lines[i+1].strip()
                            if not next_line:
                                continue

                            if '"hello"' in line:
                                print(line)
                                print(next_line)

                            if (line[-1] in ('"', "'") and
                                    next_line.lstrip()[0] in ('"', "'")):

                                last = line[-2]
                                first = next_line[1]
                                last_two = line[-3:-1]
                                first_two = next_line[1:3]

                                if (    last in ('-', ' ', '/', '(')  or
                                        first in (' ', '-', '/', ')') or
                                        first_two == '\\n' or
                                        last_two == '\\n' or
                                        line.endswith('"""') or
                                        line.endswith("'''") or
                                        next_line.startswith('"""') or
                                        next_line.startswith("'''")
                                        ):
                                    continue
                                count += 1

                                print("first two", first_two)

                                bad_continuations[fn].append((i, line, next_line))
        if bad_continuations:
            msg = []
            msg.append("\nFound wrapped lines with bad spacing:")
            for path, items in bad_continuations.items():
                msg.append("=> {}".format(path))
                for line_num, first, second in items:
                    msg.append("  {}: ... {} -> {} ...".format(line_num+1, first[-20:], second[:20]))

            self.fail('\n'.join(msg))

    def find_prints(self, path, excludes=None):
        """Find any code with print( statements."""

        if excludes is None:
            excludes = []

        matches = defaultdict(lambda: list())

        for path, _, filenames in os.walk(path.as_posix()):
            for fn in filenames:
                if not fn.endswith('.py'):
                    continue

                if fn in excludes:
                    continue

                fn = Path(path)/fn

                line_num = -1
                in_doc_string = None
                with fn.open() as file:
                    skip_next = False

                    for line in file:
                        line_num += 1

                        if in_doc_string:
                            if in_doc_string in line:
                                in_doc_string = None
                            continue

                        if '"""' in line and line.count('"""')%2 == 1:
                            in_doc_string = '"""'
                            continue
                        elif "'''" in line and line.count("'''")%2 == 1:
                            in_doc_string = "'''"
                            continue

                        if skip_next:
                            skip_next = False
                            continue

                        if self.SKIP_LINE_RE.search(line) is not None:
                            continue
                        if self.SKIP_NEXT_RE.match(line) is not None:
                            skip_next = True
                            continue

                        if self.PRINT_RE.match(line):
                            matches[fn.as_posix()].append((line_num,
                                                           line.strip()))

        return matches

