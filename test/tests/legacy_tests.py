import grp
import stat
import os
import shutil
import subprocess as sp
from pathlib import Path
from typing import List

import yc_yaml as yaml
from pavilion.test_run import TestRun
from pavilion import utils
from pavilion.test_ids import TestID
from pavilion.unittest import PavTestCase


class LegacyTests(PavTestCase):
    """Tests that apply to legacy versions of Pavilion."""

    def test_legacy_runs(self):
        """Check loading of legacy run dirs."""

        legacy_path = self.TEST_DATA_DIR/'legacy'
        runs_path = legacy_path/'runs.txt'

        runs = []
        with runs_path.open() as runs_file:
            for line in runs_file:
                line = line.strip()
                if line and not line.startswith('#'):
                    runs.append(line)

        for run in runs:
            run_path = legacy_path / run
            dst_path = self.working_dir / 'test_runs' / run
            shutil.copytree(run_path.as_posix(), dst_path.as_posix(),
                            symlinks=True)

            run_id = TestID(run)

            # Move the build directory into place
            build_dst = Path(os.readlink((run_path/'build_origin').as_posix()))
            build_dst = dst_path / build_dst
            (dst_path / 'build_dir').rename(build_dst)

            test = TestRun.load(self.pav_cfg, run_id)
            self.assertTrue(test.results)
            self.assertTrue(test.complete)