from pavilion.test_config import PavTest
from pavilion.lockfile import LockFile

import logging
import os

class Suite:
    def __init__(self, pav_cfg, tests):

        self.pav_cfg = pav_cfg
        self._tests = {test.id: test for test in tests}

        suites_path = os.path.join(self.pav_cfg.working_dir, 'suites')

        self.id = self._create_id(suites_path)

    def _create_id(self, suites_path):

        lockfile_path = os.path.join(suites_path, '.lockfile')
        with lockfile.LockFile(lockfile_path, timeout=1):
            tests = os.listdir(suites_path)
            # Only return the test directories that could be integers.
            tests = tuple(map(int, filter(str.isdigit, tests)))

            # Find the first unused id.
            test_id = 1
            while test_id in tests:
                test_id += 1

            self.path = self._get_test_path(tests_path, test_id)

            try:
                os.mkdir(self.path)
            except (IOError, OSError) as err:
                raise PavTestError("Failed to create test dir '{}': {}"
                                   .format(tests_path, err))

        return test_id
