from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion.pavtest import PavTest
from pavilion.unittest import PavTestCase
import subprocess


_HAS_SLURM = None


def has_slurm():
    global _HAS_SLURM
    if _HAS_SLURM is None:
        try:
            _HAS_SLURM = subprocess.call(['sinfo', '--version']) == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            _HAS_SLURM = False

    return _HAS_SLURM


class RawSchedTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Do a default pav config, which will load from
        # the pavilion lib path.
        self.pav_config = config.PavilionConfigLoader().load_empty()

        self.test = PavTest(self.pav_cfg, {
            'name': 'raw_test',
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "Hello World."'
                ]
            },
        })

    def setUp(self):

        plugins.initialize_plugins(self.pav_config)

    def tearDown(self):

        plugins._reset_plugins()

    def test_sched_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        raw = schedulers.get_scheduler_plugin('raw')

        svars = raw.get_vars(self.test)

        for key, value in svars.items():
            self.assertNotEqual(int(value), 0)

    def test_schedule_test(self):

        raw = schedulers.get_scheduler_plugin('raw')

        raw.schedule_tests(self.pav_cfg, [self.test])

        self._cprint(self.test.job_id, self.test.path)
