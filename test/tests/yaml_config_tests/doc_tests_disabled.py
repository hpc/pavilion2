"""Test documentation building."""

from yaml_config.testlib import YCTestCase
import subprocess


class YCDocTest(YCTestCase):

    DOC_DIR = YCTestCase.ROOT_DIR/'doc'

    def test_doc_building(self):

        # Make sure the doc directory actually exists.
        self.assertTrue(self.DOC_DIR.exists())

        subprocess.call(
            ['make', 'clean'],
            cwd=self.DOC_DIR.as_posix(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

        stdout = subprocess.check_output(
            ['make', 'html'],
            cwd=self.DOC_DIR.as_posix(),
            stderr=subprocess.STDOUT)
        stdout = stdout.decode('utf8')

        self.assertNotIn('WARNING', stdout,
                         msg='\nWARNING found in doc build output: {}'
                             .format(stdout))
        self.assertNotIn('ERROR', stdout,
                         msg='\nERROR found in doc build output: {}'
                             .format(stdout))

