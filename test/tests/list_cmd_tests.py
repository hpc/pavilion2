import datetime as dt
import time

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.test_run import TestAttributes
from pavilion.series import TestSeries
from pavilion.unittest import PavTestCase


class ListCmdTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_list_cmd(self):
        """Test the list command and the filters"""

        cmd = commands.get_command('list')
        cmd.silence()

        tests = []
        now = dt.datetime.now()
        for i in range(30):
            test = self._quick_test(
                name="list_cmd_tests_{}".format(i))

            # Forge some useful bits to filter by.
            test.created = now - dt.timedelta(hours=i)
            test.uuid = i
            if i % 2 == 0:
                test.result = test.PASS
            if i % 3 == 0:
                test.complete = True
            test.save_attributes()

            tests.append(test)

        series = []
        for i in range(0, 30, 5):
            time.sleep(0.01)
            series.append(TestSeries(
                pav_cfg=self.pav_cfg,
                tests=tests[i:i+5]
            ))

        parser = arguments.get_parser()

        args = parser.parse_args(['list', 'test_runs', '--limit=15',
                                  '--name=*.list_cmd_tests_*'])
        self.assertEqual(cmd.run(self.pav_cfg, args), 0)
        out, err = cmd.clear_output()
        self.assertEqual(err, '')
        self.assertEqual([int(t) for t in out.split()],
                         [t.id for t in tests[:15]])

        args = parser.parse_args(
            ['list', '--multi-line', 'test_runs', '--sort-by=created',
             '--limit=15', '--name=*.list_cmd_tests_*'])
        self.assertEqual(cmd.run(self.pav_cfg, args), 0)
        out, err = cmd.clear_output()
        # 26-30 are filtered due to the default newer-than time.
        self.assertEqual([int(t) for t in out.strip().splitlines()],
                         [t.id for t in list(reversed(tests))
                          if t.uuid < 25][:15])

        all_out_fields = ','.join(TestAttributes.list_attrs())
        args = parser.parse_args(
            ['list', '--out-fields={}'.format(all_out_fields),
             'test_runs', '--complete', '--name=*.list_cmd_tests_*'])
        self.assertEqual(cmd.run(self.pav_cfg, args), 0)
        out, err = cmd.clear_output()
        lines = out.strip().splitlines()
        ids = []
        id_idx = TestAttributes.list_attrs().index('id')
        for line in lines:
            parts = [part.strip() for part in line.split('|')]
            ids.append(int(parts[id_idx]))

        # 26-30 are filtered due to the default newer-than time.
        self.assertEqual(ids,
                         [t.id for t in tests if t.complete and t.uuid < 25])

        args = parser.parse_args(
            ['list', '--csv', '--out-fields={}'.format(all_out_fields),
             'test_runs', '--passed', '--name=*.list_cmd_tests_*'])
        self.assertEqual(cmd.run(self.pav_cfg, args), 0)
        out, err = cmd.clear_output()
        rows = [line.split(",") for line in out.strip().splitlines()]
        ids = [int(row[id_idx]) for row in rows]
        self.assertEqual(ids,
                         [t.id for t in tests if (t.uuid < 25 and
                                                  t.result == t.PASS)])

        for arglist in [
                ['list', '--long', '--header', '--vsep=$', 'runs'],
                ['list', '--csv', '--header', 'test_runs'],
                ['list', '--show-fields', 'tests'],
                ['list', 'series'],
                ['list', '--multi-line', 'series'],
                ['list', '--long', '--header', '--vsep=$', 'series'],
                ['list', '--csv', '--header', 'series'],
                ['list', '--show-fields', 'series']]:

            args = parser.parse_args(arglist)
            ret = cmd.run(self.pav_cfg, args)
            out, err = cmd.clear_output()
            self.assertEqual(ret, 0, msg=out + '\n' + err)
