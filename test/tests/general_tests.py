import grp
import os
import shutil
import subprocess as sp
import time
from pathlib import Path

import yc_yaml as yaml
from pavilion import utils
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase


class GeneralTests(PavTestCase):
    """Tests that apply to the whole of Pavilion, rather than some particular
    part."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Find a group that isn't the user's default group (or sudo), and
        # use that as our default group.
        login = utils.get_login()
        def_gid = os.getgid()
        candidates = [group for group in grp.getgrall() if
                      (login in group.gr_mem
                       and def_gid != group.gr_gid
                       and group.gr_name != 'sudo')]

        if not candidates:
            self.fail("Your user must be in at least two groups (other than "
                      "sudo) to run this test.")

        self.alt_group = candidates[0]  # type: grp.struct_group
        self.umask = 0o007

    def setUp(self) -> None:

        with self.PAV_CONFIG_PATH.open() as pav_cfg_file:
            raw_cfg = yaml.load(pav_cfg_file)

        self.working_dir = self.TEST_DATA_ROOT/'working_dir-permissions'

        if self.working_dir.exists():
            shutil.rmtree(self.working_dir.as_posix())

        self.working_dir.mkdir()

        raw_cfg['shared_group'] = self.alt_group.gr_name
        raw_cfg['umask'] = self.umask
        raw_cfg['working_dir'] = self.working_dir.as_posix()

        self.config_dir = self.TEST_DATA_ROOT/'configs-permissions'
        with (self.config_dir/'pavilion.yaml').open('w') as pav_cfg_file:
            yaml.dump(raw_cfg, stream=pav_cfg_file)

    def wait_tests(self, path: Path, timeout=5):
        """Wait on all the tests under the given path to complete."""

        end_time = time.time() + timeout
        while time.time() < end_time:
            runs_dir = self.working_dir/'test_runs'

            completion_files = [path/TestRun.COMPLETE_FN
                                for path in runs_dir.iterdir()]

            if not completion_files:
                time.sleep(0.1)
                continue

            if all([cfile.exists() for cfile in completion_files]):
                break
        else:
            raise TimeoutError

    def test_permissions(self):
        """Make sure all files written by Pavilion have the correct
        permissions."""

        tests = [
            'perm.base',
            'perm.tar',
            'perm.dir',
        ]

        cmd = [(self.PAV_ROOT_DIR/'bin'/'pav').as_posix(), 'run'] + tests

        self.check_runs(cmd)

    def test_build_fail_permissions(self):
        """Make sure failed builds have good permissions too."""

        cmd = [(self.PAV_ROOT_DIR /'bin'/'pav').as_posix(),
               'run', 'perm.build_fail']

        self.check_runs(cmd)

    def check_runs(self, cmd):
        """Perform a run and make sure they have correct permissions."""

        env = os.environ.copy()
        env['PAV_CONFIG_DIR'] = self.config_dir.as_posix()

        proc = sp.Popen(cmd, env=env, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        proc.wait(3)
        self.wait_tests(self.working_dir/'test_runs')

        for file in utils.flat_walk(self.working_dir):
            stat = file.stat()
            # Make sure all files have the right group.
            grp_name = grp.getgrgid(stat.st_gid).gr_name
            self.assertEqual(
                stat.st_gid, self.alt_group.gr_gid,
                msg="File {} had the incorrect group. Expected {}, got {}"
                    .format(file, self.alt_group.gr_name, grp_name))
            # Make sure all files are properly masked.
            masked_mode = oct(stat.st_mode & ~self.umask)
            self.assertEqual(
                masked_mode, oct(stat.st_mode),
                msg="Bad permissions for file {}. Expected {}, got {}"
                    .format(file, masked_mode, oct(stat.st_mode))
            )


