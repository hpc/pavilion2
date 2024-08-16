from pavilion.unittest import PavTestCase


class SuitesTests(PavTestCase):

    def test_suite_directory_created(self):
        config = {
            'name': 'suite_dir_test',
            'scheduler': 'raw',
            'build': {
                'cmds': ['echo', 'Hello']
            }
        }

        test = self._quick_test(config, 'suite_dir_test', build=False)
        test.build()

        cfg_dir = test.working_dir / 'pav_cfgs'
        configs = list(cfg_dir.iterdir())
