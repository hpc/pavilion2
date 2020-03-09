import io
import os
import pavilion

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.status_file import STATES
from pavilion.test_config import file_format, setup, variables
from pavilion.test_run import TestRun, TestRunError
from pavilion import unittest


class conditionalTest(unittest.PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_success(self):  # this method runs some conditional successes
        # using the variables to test logic of not_if and only if
        test_list = []
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "Goodbye World"']

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'not_if': {'person': ['bleh', 'notcalvin'],
                               'machine': ['notbieber', 'foo']},
                    'only_if': {'machine': ['notbieber', 'bieber'],
                                'person': ['notcalvin', 'calvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin']},
                    'only_if': {'person': ['nivlac', 'calvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['bob'],
                                  'machine': ['bieber']},
                    'only_if': {'person': ['meh', 'bob']},
                    'only_if': {'machine': ['goblin', 'bieber']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'not_if': {'person': ['nivlac', 'notcalvin'],
                               'machine': ['blurg']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        for test_cfg in test_list:
            test = self._quick_test(cfg=test_cfg)
            test.build()
            test.run()
            self.assertFalse(test.skipped)

    def test_failure(self):  # this method runs skip conditions
        # using the variables to test logic of not_if and only_if
        test_list = []
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "Goodbye World"']

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'not_if': {'person': ['bleh', 'notcalvin'],
                               'machine': ['notbieb']},
                    'only_if': {'machine': ['notbieber', 'bleh'],
                                'person': ['calvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'only_if': {'person': ['nivlac', 'notcalvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['bob'],
                                  'machine': ['bieber']},
                    'only_if': {'person': ['meh', 'bob']},
                    'only_if': {'machine': ['goblin', 'notbieber']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin']},
                    'not_if': {'person': ['notcalvin', 'calvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'not_if': {'person': ['notcalvin', 'definitelynotcalvin']},
                    'not_if': {'machine': ['hello', 'bieber']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        test_cfg = {'variables': {'person': ['calvin'],
                                  'machine': ['bieber']},
                    'only_if': {'person': ['nivlac', 'calvin'],
                                'machine': ['bieber']},
                    'not_if': {'machine': ['nivlac', 'notbieber'],
                               'person': ['calvin']},
                    'scheduler': 'raw',
                    'suite': 'unittest',
                    'build': {'verbose': 'false', 'timeout': '30'},
                    'run': {'cmds': ['echo "Goodbye World"'],
                            'verbose': 'false', 'timeout': '300'},
                    'slurm': {}}

        test_list.append(test_cfg)

        for test_cfg in test_list:
            test = self._quick_test(cfg=test_cfg)
            test.build()
            test.run()
            self.assertTrue(test.skipped)
