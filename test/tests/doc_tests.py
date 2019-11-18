from pavilion import unittest
import subprocess


class DocTests(unittest.PavTestCase):

    def test_doc_build(self):
        """Build the documentation and check for warnings/errors."""

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

        import pickle
        data = pickle.load(
            (self.PAV_ROOT_DIR/'docs'/'_build'/
             'doctrees'/'environment.pickle').open('rb'))

        self.dbg_print('labels')
        for k,v in data.domaindata['std']['labels'].items():
            self.dbg_print(k, v)

        self.assertTrue(len(warnings) == 0,
                        msg='{} warnings in documentation build:\n{}\n\n{}'
                            .format(len(warnings), '\n'.join(warnings), out))
