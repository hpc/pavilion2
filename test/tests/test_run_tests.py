import io

from pavilion import plugins
from pavilion.test_config import VariableSetManager, TestConfigResolver
from pavilion.test_run import TestRun
from pavilion.exceptions import TestRunError
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
        orig = TestRun(self.pav_cfg, config)
        orig.save()
        orig.build()

        # Make sure we can recreate the object from id.
        loaded = TestRun.load(self.pav_cfg, orig.working_dir, orig.id)

        # Make sure the objects are identical
        # This tests the following functions
        #  - from_id
        #  - save_config, load_config
        #  - get_test_path
        #  - write_tmpl
        for key in set(orig.__dict__.keys()).union(loaded.__dict__.keys()):
            orig_val = orig.__dict__[key]
            loaded_val = loaded.__dict__[key]
            self.assertEqual(
                orig_val, loaded_val,
                msg="Mismatch for key {}.\n{}\n{}".format(key, orig_val, loaded_val))

    def test_run(self):
        config1 = {
            'name': 'run_test',
            'scheduler': 'raw',
            'cfg_label': 'test',
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
        test.save()
        self.assert_(test.build())

        TestConfigResolver.finalize(test, VariableSetManager())

        self.assertEqual(test.run(), 0, msg="Test failed to run.")

        config2 = config1.copy()
        config2['run']['modules'] = ['asdlfkjae', 'adjwerloijeflkasd']

        test = TestRun(self.pav_cfg, config2)
        test.save()
        self.assert_(test.build())

        TestConfigResolver.finalize(test, VariableSetManager())

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
        test.save()
        self.assertTrue(test.build())
        TestConfigResolver.finalize(test, VariableSetManager())
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
            test.save()
            self.assertFalse(test.build())
