from pavilion import unittest
from pavilion import groups
from pavilion.errors import TestGroupError
from pavilion import series
from pavilion.series_config import generate_series_config
from pavilion import commands
from pavilion import arguments

import shutil
import uuid


class TestGroupTests(unittest.PavTestCase):

    def _make_group_name(self):
        """Make a random group name."""

        _ = self

        return 'grp_' + uuid.uuid4().hex[:10]

    def _make_example(self):
        """Make an example group,  and a tuple of a test, series, and sub-group."""

        tr1 = self._quick_test()
        tr2 = self._quick_test()
        tr3 = self._quick_test()
        series_cfg = generate_series_config('group_add1')
        series1 = series.TestSeries(self.pav_cfg, series_cfg)
        series1._add_tests([tr2], 'bob')
        sub_group = groups.TestGroup(self.pav_cfg, self._make_group_name())
        self.assertEqual(sub_group.add([tr3]), ([('test', tr3.full_id)], []))

        group = groups.TestGroup(self.pav_cfg, self._make_group_name())

        return group, (tr1, series1, sub_group)

    def assertGroupContentsEqual(self, test_group, items):
        """Verify that the group's contents match the given items ((itype, name) tuples)."""
        members = []
        for mem in test_group.members():
            members.append((mem['itype'], mem['id']))

        item_tuples = []
        for item in items:
            if isinstance(item, groups.TestGroup):
                item_tuples.append(('group', item.name))
            elif isinstance(item, series.TestSeries):
                item_tuples.append(('series', item.sid))
            else:
                item_tuples.append(('test', item.full_id))

        members.sort()
        item_tuples.sort()
        self.assertEqual(members, item_tuples)

    def test_group_init(self):
        """Check that object initialization and basic status functions work."""

        group = groups.TestGroup(self.pav_cfg, 'init_test_group')

        self.assertFalse(group.exists())
        group.create()
        self.assertTrue(group.exists())

        for bad_name in ('s123', '-as3', '327bb', 'a b'):
            with self.assertRaisesRegex(TestGroupError, r'Invalid group name'):
                group = groups.TestGroup(self.pav_cfg, bad_name) # Bad group name.

    def test_member_info(self):
        """Check that member info gathering works the same if given an object or a string."""

        group, (test, series1, sub_group) = self._make_example()

        for obj, str_rep in (
                (test, test.full_id),
                (series1, series1.sid),
                (sub_group, sub_group.name)):

            self.assertEqual(group._get_member_info(obj), group._get_member_info(str_rep))

    def test_group_add(self):
        """Test that adding items to groups works."""

        group, items = self._make_example()
        test, series1, sub_group = items
        added, errors = group.add(items)
        self.assertEqual(errors, [])
        added_answer = [('test', test.full_id),
                        ('series', series1.sid),
                        ('group', sub_group.name)]
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
        self.assertEqual(removed, [('series', series1.sid)])
        self.assertGroupContentsEqual(group, [test, sub_group])

        # Remove multiple items.
        removed, errors = group.remove([test, sub_group])
        self.assertEqual(errors, [])
        self.assertEqual(removed, [('test', test.full_id), ('group', sub_group.name)])
        self.assertGroupContentsEqual(group, [])

        removed, errors = group.remove(['nope', 'a.1', 'test.982349842', 's1234981234'])
        self.assertEqual(removed, [])
        self.assertEqual(len(errors), 4)

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
        self.assertEqual(sub_group.path.name, new_name)
        self.assertTrue(sub_group.exists())
        self.assertIn(('group', new_name), group.member_tuples())
        self.assertNotIn(('group', old_name), group.member_tuples())

        new_name2 = self._make_group_name()
        sub_group.rename(new_name2, redirect_parents=False)
        self.assertEqual(sub_group.name, new_name2)
        self.assertEqual(sub_group.path.name, new_name2)
        self.assertTrue(sub_group.exists())
        # The group doesn't exist under the old renaming, and we didn't rename it.
        self.assertIn(('group', new_name), group.member_tuples())
        self.assertNotIn(('group', new_name2), group.member_tuples())

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

        run_args = parser.parse_args(['run', '-g', group_name, 'hello_world'])
        series_args = parser.parse_args(['series', 'run', '-g', group_name, 'basic'])

        run_cmd.run(self.pav_cfg, run_args)
        series_cmd.run(self.pav_cfg, series_args)

        run_cmd.last_series.wait()
        series_cmd.last_series.wait()

        group = groups.TestGroup(self.pav_cfg, group_name)
        self.assertTrue(group.exists())
        self.assertEqual(len(group.members()), 2)

        # Prep some separate tests to add
        run_args2 = parser.parse_args(['run', 'hello_world'])
        run_cmd.run(self.pav_cfg, run_args2)
        run_cmd.last_series.wait()

        # Create a new group with tests to add
        sub_group_name = self._make_group_name()
        run_args3 = parser.parse_args(['run', '-g', sub_group_name, 'hello_world'])
        run_cmd.run(self.pav_cfg, run_args3)
        run_cmd.last_series.wait()

        add_items = [sub_group_name] + [test.full_id for test in run_cmd.last_tests]
        rm_tests = add_items[1:3]

        def run_grp_cmd(args):
            group_cmd.clear_output()
            args = parser.parse_args(args)
            ret = group_cmd.run(self.pav_cfg, args)
            self.assertEqual(ret, 0)

        members = group.members()
        # Add tests and a group via commands
        run_grp_cmd(['group', 'add', group_name] + add_items)
        self.assertEqual(len(group.tests()), 10)

        # Remove a couple tests
        run_grp_cmd(['group', 'remove', group_name] + rm_tests)
        self.assertEqual(len(group.tests()), 8)

        # Rename the subgroup
        new_name1 = self._make_group_name()
        new_name2 = self._make_group_name()
        run_grp_cmd(['group', 'rename', sub_group_name, new_name1])
        self.assertEqual(len(group.tests()), 8)
        run_grp_cmd(['group', 'rename', '--no-redirect', new_name1, new_name2])
        self.assertEqual(len(group.tests()), 5)
        run_grp_cmd(['group', 'rename', new_name2, new_name1])
        self.assertEqual(len(group.tests()), 8)

        # Try all the list options
        for rows, args in [
                (7,    ['group', 'members', group_name]),
                (4,    ['group', 'members', '--tests', group_name]),
                (5,    ['group', 'members', '--series', group_name]),
                (4,    ['group', 'members', '--groups', group_name]),
                (7,    ['group', 'members', '--tests', '--series', '--groups', group_name]),
                (8,    ['group', 'members', '--recursive', group_name]),
                ]:
            run_grp_cmd(args)
            out, err_out = group_cmd.clear_output()
            self.assertEqual(len(out.split('\n')), rows,
                             msg="unexpected lines for {}:\n{}"
                                 .format(args, out))

        # List all groups
        group_cmd.clear_output()
        run_grp_cmd(['group', 'list', 'grp_*'])
        out, err = group_cmd.clear_output()
        self.assertEqual(err, '')


        # Delete the renamed sub-group
        run_grp_cmd(['group', 'delete', new_name1])
        self.assertEqual(len(group.tests()), 5)
