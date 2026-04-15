import grp
import stat
import os
import shutil
import subprocess as sp
from pathlib import Path
from typing import List

import yc_yaml as yaml
from pavilion import utils
from pavilion.unittest import PavTestCase


class PermissionsTests(PavTestCase):
    """Tests that check Pavilion's permissions."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs, make_config_dir=False)

        # Find a group that isn't the user's default group (or sudo), and
        # use that as our default group.
        login = utils.get_login()
        def_gid = os.getgid()
        candidates = [group for group in grp.getgrall() if
                      (login in group.gr_mem
                       and def_gid != group.gr_gid)]

        if not candidates:
            self.orig_group = None
            self.alt_group = None
        else:
            self.orig_group = grp.getgrgid(def_gid).gr_name
            self.alt_group = candidates[0]  # type: grp.struct_group

        self.umask = 0o007

    def set_up(self) -> None:
        """Setup the special pav config for these tests."""

        with self.DEFAULT_PAV_CONFIG_PATH.open() as pav_cfg_file:
            raw_cfg = yaml.load(pav_cfg_file)

        if raw_cfg is None:
            raw_cfg = {}

        if self.working_dir.exists():
            shutil.rmtree(self.working_dir.as_posix())

        self.working_dir.mkdir()

        if self.alt_group is None:
            self.skipTest("Your user must be in at least two groups (other than "
                      "the user's group) to run this test.")

        raw_cfg['shared_group'] = self.alt_group.gr_name
        raw_cfg['umask'] = self.umask
        raw_cfg['working_dir'] = self.working_dir.as_posix()

        self.link_file(self.TEST_DATA_DIR / "configs-permissions", link_path=self.pav_config_dir)

        with (self.pav_config_dir/'pavilion.yaml').open('w') as pav_cfg_file:
            yaml.dump(raw_cfg, stream=pav_cfg_file)

    def test_permissions(self):
        """Make sure all files written by Pavilion have the correct permissions."""

        tests = [
            'perm.base',
            'perm.tar',
            'perm.dir',
        ]

        cmd = [(self.PAV_ROOT_DIR/'bin'/'pav').as_posix(), 'run'] + tests

        self._run_test_cmd(cmd)

        builds = [p for p in (self.working_dir/'builds').iterdir()
                  if p.is_dir()]
        self._check_permissions(self.working_dir, self.alt_group, self.umask,
                               exclude=builds)
        for build in builds:
            self._check_permissions(build, self.alt_group, self.umask | 0o222)

    def _check_permissions(self, path: Path, group: grp.struct_group,
                          umask: int, exclude: List[Path] = None):
        """Perform a run and make sure they have correct permissions."""

        if exclude is None:
            exclude = []
        else:
            exclude = [ex_path for ex_path in exclude]

        dir_umask = umask & ~0o222

        for file in utils.flat_walk(path):
            excluded = False
            for parent in file.parents:
                if parent in exclude:
                    excluded = True

            if excluded:
                continue

            fstat = file.stat()
            # Make sure all files have the right group.
            grp_name = grp.getgrgid(fstat.st_gid).gr_name
            self.assertEqual(
                fstat.st_gid, group.gr_gid,
                msg="File {} had the incorrect group. Expected {}, got {}"
                    .format(file, self.alt_group.gr_name, grp_name))

            mode = fstat.st_mode

            if file.is_symlink():
                mode = file.lstat().st_mode
                self.assertEqual(
                    mode, 0o120777,
                    msg="Expected symlink {} to have permissions {} but "
                        "got {}".format(file, stat.filemode(0o120777),
                                        stat.filemode(mode)))
            elif (file.name.startswith('binfile') or
                  file.name in ('kickoff', 'build.sh', 'run.sh',
                                'run.tmpl')):
                expected = (~umask) & 0o100775
                # Binfiles should have owner/group execute.
                self.assertEqual(
                    mode, expected,
                    msg="Expected {} to have perms {}, but had {}"
                        .format(file, stat.filemode(expected),
                                stat.filemode(mode)))
            elif file.is_file():
                expected = (~umask) & 0o100664
                self.assertEqual(
                    oct(mode), oct(expected),
                    msg="Expected regular file {} to have permissions {} "
                        "but got {}"
                        .format(file, stat.filemode(expected),
                                stat.filemode(mode)))
            elif file.is_dir():
                expected = 0o40775 & (~dir_umask)
                self.assertEqual(
                    mode, expected,
                    msg="Expected dir {} to have permissions {} but "
                        "got {}".format(file, stat.filemode(expected),
                                        stat.filemode(mode)))
            else:
                self.fail("Found unhandled file {}.".format(file))

    def _run_test_cmd(self, cmd, run_succeeds=True):
        """Run the given test command and check that it succeeds."""

        env = os.environ.copy()
        env['PAV_CONFIG_DIR'] = self.pav_config_dir.as_posix()

        proc = sp.Popen(cmd, env=env, stdout=sp.PIPE, stderr=sp.STDOUT)
        if (proc.wait(3) != 0) == run_succeeds:
            out = proc.stdout.read().decode()
            self.fail("Error running command.\n{}".format(out))
        self.wait_tests(self.working_dir)