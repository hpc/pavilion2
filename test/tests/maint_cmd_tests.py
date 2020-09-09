import json
import shutil
import tempfile
from pathlib import Path

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class MaintCmdTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_pruning(self):
        """Check that we only prune what we expect to, and that the result
        log remains valid."""

        tmp_path = Path(tempfile.mktemp())
        shutil.copy(self.pav_cfg.result_log.as_posix(), tmp_path.as_posix())

        tests = [self._quick_test() for i in range(20)]

        for test in tests:
            results = test.gather_results(test.run())
            test.save_results(results)

        prune = [str(test.id) for test in tests if test.id % 3 == 0]
        prune.extend([test.uuid for test in tests if test.id % 4 == 0])

        maint_cmd = commands.get_command('maint')
        maint_cmd.silence()

        parser = arguments.get_parser()

        args = parser.parse_args(['maint', 'prune_results', '--json'] + prune)

        maint_cmd.run(self.pav_cfg, args)
        out, err = maint_cmd.clear_output()
        self.assertEqual(err, '')
        pruned = json.loads(out)
        for presult in pruned:
            self.assertTrue(str(presult['id']) in prune
                            or presult['uuid'] in prune)

        pruned_ids = [str(pr['id']) for pr in pruned]
        pruned_uuids = [pr['uuid'] for pr in pruned]
        for prune_id in prune:
            self.assertTrue(
                prune_id in pruned_ids or prune_id in pruned_uuids,
                msg="Missing expected prune_id {} in {} or {}"
                    .format(prune_id, pruned_ids, pruned_uuids))

        # Prune id multiples of 5 + 1
        prune2 = [str(test.id) for test in tests]
        args2 = parser.parse_args(['maint', 'prune_results'] + prune2)
        maint_cmd.run(self.pav_cfg, args2)
        out, err = maint_cmd.clear_output()
        self.assertEqual(err, '')

        self._cmp_files(tmp_path, self.pav_cfg.result_log)
