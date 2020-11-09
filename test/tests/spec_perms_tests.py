import grp
import os
import shutil
import subprocess as sp

import yc_yaml as yaml
from pavilion import config
from pavilion import dir_db
from pavilion import plugins
from pavilion import utils
from pavilion.unittest import PavTestCase


class SpecificPermsTests(PavTestCase):
    """Tests that check setting specific permissions for a test."""

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

        self.working_dir = self.PAV_ROOT_DIR/'test'/'working_dir' / \
            'wd-spec_perms'

        if self.working_dir.exists():
            shutil.rmtree(self.working_dir.as_posix())

        self.working_dir.mkdir()

        raw_cfg['umask'] = self.umask
        raw_cfg['working_dir'] = self.working_dir.as_posix()
        raw_cfg['config_dirs'] = [self.TEST_DATA_ROOT/'configs-spec_perms']

        (self.working_dir/'test_runs').mkdir()
        (self.working_dir/'series').mkdir()
        (self.working_dir/'builds').mkdir()
        (self.working_dir/'users').mkdir()

        self.config_dir = self.TEST_DATA_ROOT/'configs-spec_perms'
        with (self.config_dir/'pavilion.yaml').open('w') as pav_cfg_file:
            yaml.dump(raw_cfg, stream=pav_cfg_file)

        tmpl_path = self.config_dir/'tests/perm.yaml.tmpl'
        test_path = self.config_dir/'tests/perm.yaml'
        with tmpl_path.open() as tmpl, test_path.open('w') as test:
            test_yaml = yaml.load(tmpl)
            test_yaml['spec_perms1']['group'] = self.alt_group.gr_name
            test_yaml['spec_perms2']['group'] = self.alt_group2.gr_name
            yaml.dump(test_yaml, test)

        self.pav_cfg = config.find(target=self.config_dir/'pavilion.yaml')

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self) -> None:
        """Perform test teardown."""
        plugins._reset_plugins()

    def test_spec_perms(self):
        """Check that test specific permissions work."""

        env = os.environ.copy()

        env['PAV_CONFIG_DIR'] = self.config_dir.as_posix()

        cmd = [(self.PAV_ROOT_DIR/'bin/pav').as_posix(), 'run', 'perm.*']

        proc = sp.Popen(cmd, env=env, stdout=sp.PIPE, stderr=sp.STDOUT)
        try:
            if proc.wait(10) != 0:
                out = proc.stdout.read()
                out = out.decode()
                self.fail("Error running command.\n{}".format(out))
        except sp.TimeoutExpired:
            self.fail()
        self.wait_tests(self.working_dir)

        perms = {
            'base': (grp.getgrgid(os.getgid()), 0o007),
            'spec_perms1': (self.alt_group, 0o022),
            'spec_perms2': (self.alt_group2, 0o002),
        }

        for test_path in dir_db.select(self.working_dir / 'test_runs')[0]:
            with (test_path/'config').open() as config_file:
                test_config = yaml.load(config_file)

            name = test_config['name']

            group, umask = perms[name]

            self.check_perms(test_path, group, umask)

    def check_perms(self, path, group, umask):
        """Perform a run and make sure they have correct permissions."""

        for file in utils.flat_walk(path):
            stat = file.stat()

        for file in utils.flat_walk(path):
            stat = file.stat()
            # Make sure all files have the right group.
            grp_name = group.gr_name
            assigned_group = grp.getgrgid(stat.st_gid).gr_name
            self.assertEqual(
                stat.st_gid, group.gr_gid,
                msg="File {} had the incorrect group. Expected {}, got {}"
                    .format(file, grp_name, assigned_group))
            # Make sure all files are properly masked.
            masked_mode = oct(stat.st_mode & ~umask)
            self.assertEqual(
                masked_mode, oct(stat.st_mode),
                msg="Bad permissions for file {}. Expected {}, got {}"
                    .format(file, masked_mode, oct(stat.st_mode))
            )


