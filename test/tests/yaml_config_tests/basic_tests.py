import os
from io import StringIO

from yaml_config.testlib import YCTestCase


class YCBasicTest(YCTestCase):

    def _data_path(self, filename):
        """Return an absolute path to the given test data file."""
        path = os.path.abspath(__file__)
        path = os.path.dirname(path)
        return os.path.join(path, 'data', filename)

    def test_instantiate(self):
        """Verify that we can instantiate the a test config class without errors."""
        self.Config()

    def test_load(self):
        """Verify that we can load data without errors."""
        test = self.Config()
        with open(self._data_path('test1.yaml'), 'r') as f:
            test.load(f)

    def test_dump(self):
        """Verify that the data loaded is equal to the data if dumped and loaded again."""
        test = self.Config()
        with open(self._data_path('test1.yaml'), 'r') as f:
            data = test.load(f)

        dest_stream = StringIO()
        test.dump(dest_stream, values=data)
        dest_stream.seek(0)

        data2 = test.load(dest_stream)

        self.assertEqual(data, data2)

        dest_stream.close()


if __name__ == '__main__':
    unittest.main()
