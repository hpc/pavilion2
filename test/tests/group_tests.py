from pavilion import arguments
from pavilion import commands
from pavilion import groups
from pavilion import series
from pavilion import unittest
from pavilion.errors import TestGroupError
from pavilion.series_config import generate_series_config
from pavilion.test_run import TestRun
from pavilion.test_ids import GroupID, TestID

import shutil
import uuid
import json


class TestGroupTests(unittest.PavTestCase):

    def _make_group_name(self):
        """Make a random group name."""

        _ = self

        return GroupID('grp_' + uuid.uuid4().hex[:10])

    def _make_example(self):
        """Make an example group,  and a tuple of a test, series, and sub-group."""

        tr1 = self._quick_test()
        tr2 = self._quick_test()
        tr3 = self._quick_test()
        series_cfg = generate_series_config('group_add1')
        series1 = series.TestSeries(self.pav_cfg, series_cfg)
        series1._add_tests([tr2], 'bob')
        sub_group = groups.TestGroup(self.pav_cfg, self._make_group_name())
        self.assertEqual(sub_group.add([tr3]), ([tr3.id], []))

        group = groups.TestGroup(self.pav_cfg, self._make_group_name())

        return group, (tr1, series1, sub_group)

    def assertGroupContentsEqual(self, test_group, items):
        """Verify that the group's contents match the given items ((itype, name) tuples)."""
        members = []
        for mem in test_group.members():
            members.append(mem['id'])

        item_tuples = []
        for item in items:
            if isinstance(item, groups.TestGroup):
                item_tuples.append(item.name)
            else:
                item_tuples.append(item.id)

        self.assertEqual(set(members), set(item_tuples))

    def test_member_info(self):
        """Check that member info gathering works the same if given an object or a string."""

        group, (test, series1, sub_group) = self._make_example()

        for obj, str_rep in (
                (test, test.id),
                (series1, series1.id),
                (sub_group, sub_group.name)):

            self.assertEqual(group._get_member_info(obj), group._get_member_info(str_rep))

    def test_group_add(self):
        """Test that adding items to groups works."""

        group, items = self._make_example()
        test, series1, sub_group = items
        added, errors = group.add(items)
        self.assertEqual(errors, [])
        added_answer = [test.id,
                        series1.id,
                        sub_group.name]
        added2, errors = group.add(items)
        self.assertEqual(errors, [])
        self.assertEqual(added2, [])

        # This should also do nothing - self-references are simply skipped.
        self.assertEqual(group.add([group]), ([] , []))

        # Make sure the group actually has the added items
        self.assertGroupContentsEqual(group, items)

        added, errors = group.add(
            ('does_not_exist.123441234', 'test.77262346324', 's1987234123', 'no_such_group'))
        self.assertEqual(added, [])
        self.assertEqual(len(errors), 4)

    def test_group_remove(self):
        """Check that removing items from a group works."""

        group, items = self._make_example()
        test, series1, sub_group = items
        group.add(items)

        # Remove a single item, to make sure other items are preserved
        removed, errors = group.remove([series1])
        self.assertEqual(errors, [])
        self.assertEqual(removed, [series1.id])
        self.assertGroupContentsEqual(group, [test, sub_group])

        # Remove multiple items.
        removed, errors = group.remove([test, sub_group])
        self.assertEqual(errors, [])
        self.assertEqual(removed, [test.id, sub_group.name])
        self.assertGroupContentsEqual(group, [])

        removed, errors = group.remove([GroupID('nope')])
        self.assertEqual(removed, [])
        self.assertEqual(len(errors), 1)

    def test_group_exclusions(self):
        """Check that excluded tests are handled properly."""

        group, (btest, series1, sub_group) = self._make_example()
        group.add([btest, series1, sub_group])

        # Remove the tests from the series and sub_group.
        s_test = list(series1.tests.values())[0]
        g_test = sub_group.tests()[0]
        g_test = g_test.resolve()
        g_test = TestRun.load(self.pav_cfg, g_test.parents[1], TestID(g_test.name))

        removed, warnings = group.remove([g_test, s_test])
        self.assertEqual(warnings, [])
        answer = [s_test.id, g_test.id]
        self.assertEqual(set(removed), set(answer))
        self.assertEqual(group._excluded(), {s_test.id: s_test.path,
                                             g_test.id: g_test.path})
        self.assertEqual(group.tests(), [btest.path])

        group.remove([sub_group.name])

        added, warnings = group.add([s_test, g_test])
        self.assertEqual(sorted(added), sorted([g_test.id, s_test.id]))
        self.assertEqual(warnings, [])

    def test_group_clean(self):
        """Check that cleaning works as expected."""

        group, items = self._make_example()
        test, series1, sub_group = items
        group.add(items)

        # Delete the test,
        shutil.rmtree(test.path)
        errors = group.clean()
        self.assertGroupContentsEqual(group, [series1, sub_group])

        shutil.rmtree(series1.path)
        sub_group.delete()
        errors = group.clean()
        self.assertEqual(errors, [])
        self.assertFalse(group.exists())

    def test_group_rename(self):
        """Check group renaming."""

        group, items = self._make_example()
        _, _, sub_group = items
        group.add(items)

        old_name = sub_group.name
        new_name = self._make_group_name()
        sub_group.rename(new_name)
        self.assertEqual(sub_group.name, new_name)
        self.assertEqual(GroupID(sub_group.path.name), new_name)
        self.assertTrue(sub_group.exists())
        self.assertIn(new_name, group)
        self.assertNotIn(old_name, group)

        new_name2 = self._make_group_name()
        sub_group.rename(new_name2, redirect_parents=False)
        self.assertEqual(sub_group.name, new_name2)
        self.assertEqual(GroupID(sub_group.path.name), new_name2)
        self.assertTrue(sub_group.exists())
        # The group doesn't exist under the old renaming, and we didn't rename it.
        self.assertIn(new_name, group)
        self.assertNotIn(new_name2, group)

    def test_group_commands(self):
        """Check the operation of various group command statements."""

        group_cmd = commands.get_command('group')
        run_cmd = commands.get_command('run')
        series_cmd = commands.get_command('series')

        for cmd in group_cmd, run_cmd, series_cmd:
            cmd.silence()

        group_name = self._make_group_name()
        parser = arguments.get_parser()
        # Start a series of tests two ways, each assigned to a group.

        run_args = parser.parse_args(['run', '-g', str(group_name), 'hello_world'])
        series_args = parser.parse_args(['series', 'run', '-g', str(group_name), 'basic'])

        run_cmd.run(self.pav_cfg, run_args)
        series_cmd.run(self.pav_cfg, series_args)

        try:
            run_cmd.last_series.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for series to complete after {self.series_wait_timeout} "
                "seconds.")

        try:
            series_cmd.last_series.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for series to complete after {self.series_wait_timeout} "
                "seconds.")

        group = groups.TestGroup(self.pav_cfg, group_name)
        self.assertTrue(group.exists())
        self.assertEqual(len(group.members()), 2)

        # Prep some separate tests to add
        run_args2 = parser.parse_args(['run', 'hello_world'])
        run_cmd.run(self.pav_cfg, run_args2)

        try:
            run_cmd.last_series.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for series to complete after {self.series_wait_timeout} "
                      "seconds.")

        # Create a new group with tests to add
        sub_group_name = self._make_group_name()
        run_args3 = parser.parse_args(['run', '-g', str(sub_group_name), 'hello_world'])
        run_cmd.run(self.pav_cfg, run_args3)

        try:
            run_cmd.last_series.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for series to complete after {self.series_wait_timeout} "
                "seconds.")

        add_items = [str(sub_group_name)] + [str(test.id) for test in run_cmd.last_tests]
        rm_tests = add_items[1:3]

        def run_grp_cmd(args):
            group_cmd.clear_output()
            args = parser.parse_args(args)
            ret = group_cmd.run(self.pav_cfg, args)
            self.assertEqual(ret, 0)

        members = group.members()
        # Add tests and a group via commands

        run_grp_cmd(['group', 'add', str(group_name)] + add_items)
        self.assertEqual(len(group.tests()), 10)

        # Remove a couple tests
        run_grp_cmd(['group', 'remove', str(group_name)] + rm_tests)
        self.assertEqual(len(group.tests()), 8)

        # Rename the subgroup
        new_name1 = self._make_group_name()
        new_name2 = self._make_group_name()
        run_grp_cmd(['group', 'rename', str(sub_group_name), str(new_name1)])
        self.assertEqual(len(group.tests()), 8)
        run_grp_cmd(['group', 'rename', '--no-redirect', str(new_name1), str(new_name2)])
        self.assertEqual(len(group.tests()), 5)
        run_grp_cmd(['group', 'rename', str(new_name2), str(new_name1)])
        self.assertEqual(len(group.tests()), 8)

        # Try all the list options
        for rows, args in [
                (4,    ['group', 'members', "--json", str(group_name)]),
                (1,    ['group', 'members', "--json", '--tests', str(group_name)]),
                (2,    ['group', 'members', "--json", '--series', str(group_name)]),
                (1,    ['group', 'members', "--json", '--groups', str(group_name)]),
                (4,    ['group', 'members', "--json", '--tests', '--series', '--groups', str(group_name)]),
                (5,    ['group', 'members', "--json", '--recursive', str(group_name)]),
                ]:
            run_grp_cmd(args)
            out, err_out = group_cmd.clear_output()
            self.assertEqual(
                            len(json.loads(out)),
                            rows,
                             msg="unexpected lines for {}:\n{}"
                                 .format(args, out))

        # List all groups
        group_cmd.clear_output()
        run_grp_cmd(['group', 'list', 'grp_*'])
        out, err = group_cmd.clear_output()
        self.assertEqual(err, '')


        # Delete the renamed sub-group
        run_grp_cmd(['group', 'delete', str(new_name1)])
        self.assertEqual(len(group.tests()), 5)
