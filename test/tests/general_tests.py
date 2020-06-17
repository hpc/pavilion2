import grp
import copy
import os
import shutil
import subprocess as sp
from pavilion.plugins.commands import run
from pavilion import commands
import io
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
                       and def_gid != group.gr_gid)]

        if not candidates:
            self.fail("Your user must be in at least two groups (other than "
                      "the user's group) to run this test.")

        self.orig_group = grp.getgrgid(def_gid).gr_name
        self.alt_group = candidates[0]  # type: grp.struct_group
        self.alt_group2 = candidates[1]  # type: grp.struct_group
        self.umask = 0o007

    def setUp(self) -> None:

        with self.PAV_CONFIG_PATH.open() as pav_cfg_file:
            raw_cfg = yaml.load(pav_cfg_file)

        self.working_dir = self.PAV_ROOT_DIR/'test'/'working_dir'/'wd_perms'

        if self.working_dir.exists():
            shutil.rmtree(self.working_dir.as_posix())

        self.working_dir.mkdir()

        raw_cfg['shared_group'] = self.alt_group.gr_name
        raw_cfg['umask'] = self.umask
        raw_cfg['working_dir'] = self.working_dir.as_posix()

        self.config_dir = self.TEST_DATA_ROOT/'configs-permissions'
        with (self.config_dir/'pavilion.yaml').open('w') as pav_cfg_file:
            yaml.dump(raw_cfg, stream=pav_cfg_file)

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

        cmd = [(self.PAV_ROOT_DIR /'bin/pav').as_posix(),
               'run', 'perm.build_fail']

        self.check_runs(cmd, run_succeeds=False)

    def check_runs(self, cmd, run_succeeds=True):
        """Perform a run and make sure they have correct permissions."""

        env = os.environ.copy()
        env['PAV_CONFIG_DIR'] = self.config_dir.as_posix()

        proc = sp.Popen(cmd, env=env, stdout=sp.PIPE, stderr=sp.STDOUT)
        if (proc.wait(3) != 0) == run_succeeds:
            out = proc.stdout.read()
            out = out.decode()
            self.fail("Error running command.\n{}".format(out))
        self.wait_tests(self.working_dir)

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


