import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pavilion import wget
from pavilion.test_run import TestRunError, TestRun
from pavilion.series import TestSeries
from pavilion.status_file import STATES
from pavilion.test_config import variables, VariableSetManager
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
            self.assertEqual(t.__dict__[key], t2.__dict__[key],
                             msg="Mismatch for key {}".format(key))

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

        self.assertTrue(test.run(), msg="Test failed to run.")

        config2 = config1.copy()
        config2['run']['modules'] = ['asdlfkjae', 'adjwerloijeflkasd']

        test = TestRun(self.pav_cfg, config2)
        self.assert_(test.build())

        test.finalize(VariableSetManager())

        self.assertEqual(
            test.run(),
            False,
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
        self.assert_(test.build())
        test.finalize(VariableSetManager())
        with self.assertRaises(TimeoutError,
                               msg="Test should have failed due "
                                   "to timeout. {}"):
            test.run()

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
        suite = TestSeries(self.pav_cfg, tests)

        # Make sure we got all the tests
        self.assertEqual(len(suite.tests), 3)
        test_paths = [Path(suite.path, p)
                      for p in os.listdir(str(suite.path))]
        # And that the test paths are unique
        self.assertEqual(len(set(test_paths)),
                         len([p.resolve() for p in test_paths]))

        self._is_softlink_dir(suite.path)

        suite2 = TestSeries.from_id(self.pav_cfg, suite._id)
        self.assertEqual(sorted(suite.tests.keys()),
                         sorted(suite2.tests.keys()))
        self.assertEqual(sorted([t.id for t in suite.tests.values()]),
                         sorted([t.id for t in suite2.tests.values()]))

        self.assertEqual(suite.path, suite2.path)
        self.assertEqual(suite.id, suite2.id)
