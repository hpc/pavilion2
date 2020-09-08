import io
import io
import os
from pathlib import Path

from pavilion import plugins
from pavilion.series import TestSeries
from pavilion.test_config import VariableSetManager
from pavilion.test_run import TestRunError, TestRun
from pavilion.unittest import PavTestCase


class TestRunTests(PavTestCase):

    def test_obj(self):
        """Test pavtest object initialization."""

        # Initializing with a mostly blank config
        config = {
            # The only required param.
            'name': 'blank_test',

            'scheduler': 'raw',
        }

        # Making sure this doesn't throw errors from missing params.
        TestRun(self.pav_cfg, config)

        config = {
            'subtest': 'st',
            'name': 'test',
            'scheduler': 'raw',
            'build': {
                'modules': ['gcc'],
                'cmds': ['echo "Hello World"'],
                'timeout': '30',
            },
            'run': {
                'modules': ['gcc', 'openmpi'],
                'cmds': ['echo "Running dis stuff"'],
                'env': {'BLARG': 'foo'},
                'timeout': '30',
            }
        }

        # Make sure we can create a test from a fairly populated config.
        t = TestRun(self.pav_cfg, config)
        t.build()

        # Make sure we can recreate the object from id.
        t2 = TestRun.load(self.pav_cfg, t.id)

        # Make sure the objects are identical
        # This tests the following functions
        #  - from_id
        #  - save_config, load_config
        #  - get_test_path
        #  - write_tmpl
        for key in set(t.__dict__.keys()).union(t2.__dict__.keys()):
            val1 = t.__dict__[key]
            val2 = t2.__dict__[key]
            self.assertEqual(
                val1, val2,
                msg="Mismatch for key {}.\n{}\n{}".format(key, val1, val2))

    def test_run(self):
        config1 = {
            'name': 'run_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '30',
                },
            'run': {
                'timeout': None,
                'env': {
                    'foo': 'bar',
                },
                #
                'cmds': ['echo "I ran, punks"'],
            },
        }

        test = TestRun(self.pav_cfg, config1)
        self.assert_(test.build())
        test.finalize(VariableSetManager())

        self.assertEqual(test.run(), 0, msg="Test failed to run.")

        config2 = config1.copy()
        config2['run']['modules'] = ['asdlfkjae', 'adjwerloijeflkasd']

        test = TestRun(self.pav_cfg, config2)
        self.assert_(test.build())

        test.finalize(VariableSetManager())

        self.assertEqual(
            test.run(), 1,
            msg="Test should have failed because a module couldn't be "
                "loaded. {}".format(test.path))
        # TODO: Make sure this is the exact reason for the failure
        #   (doesn't work currently).

        # Make sure the test fails properly on a timeout.
        config3 = {
            'name': 'sleep_test',
            'scheduler': 'raw',
            'run': {
                'timeout': '1',
                'cmds': ['sleep 10']
            }
        }

        test = TestRun(self.pav_cfg, config3)
        self.assertTrue(test.build())
        test.finalize(VariableSetManager())
        with self.assertRaises(TimeoutError,
                               msg="Test should have failed due "
                                   "to timeout. {}"):
            test.run()

    def test_create_file(self):
        """Ensure runtime file creation is working correctly."""

        plugins.initialize_plugins(self.pav_cfg)
        files_to_create = {
            'runtime_0': ['line_0', 'line_1'],
            'wild/runtime_1': ['line_0', 'line_1'],  # dir exists
            'wild/dir2/runtime_2': ['line_0', 'line_1'], # dir2 does not exist
            'real.txt': ['line_0', 'line_1'],  # file exists; overwrite
            'runtime_variable': ['{{var1}}',
                                 '{{var2.0}}', '{{var2.1}}', '{{var2.2}}',
                                 '{{var3.subvar_1}}', '{{var3.subvar_2}}',
                                 '{{var4.0.subvar_3}}', '{{var4.0.subvar_4}}',
                                 '{{var4.1.subvar_3}}', '{{var4.1.subvar_4}}']
        }
        variables = {
            'var1': 'val_1',
            'var2': ['val_2', 'val_3', 'val_4'],
            'var3': {'subvar_1': 'val_5',
                     'subvar_2': 'val_6'},
            'var4': [{'subvar_3': 'val_7',
                      'subvar_4': 'val_8'},
                     {'subvar_3': 'val_9',
                      'subvar_4': 'val_10'}]
        }
        config = self._quick_test_cfg()
        config['variables'] = variables
        config['build']['source_path'] = 'file_tests.tgz'
        config['run']['create_files'] = files_to_create
        test = self._quick_test(config)

        for file, lines in files_to_create.items():
            file_path = test.path / 'build' / file
            self.assertTrue(file_path.exists())

            # Stage file contents for comparison.
            original = io.StringIO()
            created_file = open(str(file_path), 'r', encoding='utf-8')
            if file == 'runtime_variable':
                original.write('val_1\nval_2\nval_3\nval_4\nval_5\nval_6'
                               '\nval_7\nval_8\nval_9\nval_10\n')
            else:
                for line in lines:
                    original.write("{}\n".format(line))

            self.assertEquals(original.getvalue(), created_file.read())
            original.close()
            created_file.close()

    def test_files_create_errors(self):
        """Ensure runtime file creation expected errors occur."""

        plugins.initialize_plugins(self.pav_cfg)

        # Ensure a file can't be written outside the build context.
        files_to_fail = ['../file', '../../file', 'wild/../../file']
        for file in files_to_fail:
            file_arg = {file: []}
            config = self._quick_test_cfg()
            config['build']['source_path'] = 'file_tests.tgz'
            config['build']['create_files'] = file_arg
            with self.assertRaises(TestRunError) as context:
                self._quick_test(config)
            self.assertTrue('outside build context' in str(context.exception))

        # Ensure a file can't overwrite existing directories.
        files_to_fail = ['wild', 'rec']
        for file in files_to_fail:
            file_arg = {file: []}
            config = self._quick_test_cfg()
            config['build']['source_path'] = 'file_tests.tgz'
            config['build']['create_files'] = file_arg
            test = TestRun(self.pav_cfg, config)
            self.assertFalse(test.build())

    def test_suites(self):
        """Test suite creation and regeneration."""

        config1 = {
            'name': 'run_test',
            'scheduler': 'raw',
            'run': {
                'env': {
                    'foo': 'bar',
                },
                #
                'cmds': ['echo "I ran, punks"'],
            },
        }

        tests = []
        for i in range(3):
            tests.append(TestRun(self.pav_cfg, config1))

        # Make sure this doesn't explode
        series = TestSeries(self.pav_cfg, tests)

        # Make sure we got all the tests
        self.assertEqual(len(series.tests), 3)
        test_paths = [Path(series.path, p)
                      for p in os.listdir(str(series.path))]
        # And that the test paths are unique
        self.assertEqual(len(set(test_paths)),
                         len([p.resolve() for p in test_paths]))

        self._is_softlink_dir(series.path)

        series2 = TestSeries.from_id(self.pav_cfg, series.sid)
        self.assertEqual(sorted(series.tests.keys()),
                         sorted(series2.tests.keys()))
        self.assertEqual(sorted([t.id for t in series.tests.values()]),
                         sorted([t.id for t in series2.tests.values()]))

        self.assertEqual(series.path, series2.path)
        self.assertEqual(series.sid, series2.sid)
