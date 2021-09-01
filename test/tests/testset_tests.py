from pavilion import plugins
from pavilion.test_set import TestSet, TestSetError
from pavilion.unittest import PavTestCase


class SeriesFileTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_init(self):
        """Check the init function."""

        # It's ok if a set is empty. It might end up empty from skips anyway.
        TestSet(self.pav_cfg, "test_deps", [])
        TestSet(self.pav_cfg, "test_deps", ['foo'])

    def test_dependencies(self):
        """Check dependency functions."""

        ts1 = TestSet(self.pav_cfg, "ts1", ['foo'])
        ts2= TestSet(self.pav_cfg, "ts2", ['bar1', 'bar2', 'bar3'])
        ts3 = TestSet(self.pav_cfg, "ts3", ['baz'])

        ts1.add_parent(ts2)
        ts3.add_parent(ts1)
        ts3.add_parent(ts1)

        self.assertEqual(ts1.child_sets, {ts2, ts3})
        self.assertEqual(ts1.parent_sets, {ts2})
        self.assertEqual(ts1.child_sets, {ts3})
        self.assertEqual(ts3.parent_sets, {ts1, ts2})

        ts2a, ts2b, ts2c = ts2.ordered_split()

        for ts in ts1, ts2a, ts2b, ts2c, ts3:
            print(ts.name, ts.parent_sets, ts.child_sets)

        self.assertEqual(ts2c, ts2)  # These should be the same object.
        # Anything with ts1 as a child should now have ts2a instead
        self.assertEqual(ts1.child_sets, {ts2a, ts3})
        self.assertEqual(ts2a.parent_sets, {ts2})
        self.assertEqual(ts2a.child_sets, {ts2b})
        self.assertEqual(ts2b.parent_sets, {ts2a})
        self.assertEqual(ts2b.child_sets, {ts2c})
        self.assertEqual(ts2c.parent_sets, {ts2b})
        self.assertEqual(ts2c.child_sets, {ts3})
        self.assertEqual(ts3.parent_sets, {ts1, ts2c})

    def test_make(self):
        """Check that TestRun creation works and throws the correct errors."""

        ts1 = TestSet(self.pav_cfg, "test_make1", ['pass_fail'])
        ts1.make()

        with self.assertRaises(RuntimeError):
            ts1.make()

        ts1 = TestSet(self.pav_cfg, "test_make2", ['invalid'])
        with self.assertRaises(TestSetError):
            ts1.make()

        ts3 = TestSet(self.pav_cfg, "test_make3", ['invalid_results'])
        with self.assertRaises(TestSetError):
            ts3.make()

    def test_build(self):
        """Check that building works as expected."""

        ts0 = TestSet(self.pav_cfg, "test_build0", [])
        with self.assertRaises(RuntimeError):
            ts0.build()

        ts1 = TestSet(self.pav_cfg, "test_build1", ['build_parallel'])
        ts1.make()
        ts1.build()

        ts1 = TestSet(self.pav_cfg, "test_build2", ['build_fail'])
        ts1.make()
        self.assertEqual(len(ts1.tests), 6)
        with self.assertRaises(TestSetError):
            ts1.build()

        # Building an empty set should be fine.
        ts3 = TestSet(self.pav_cfg, "test_build3", [])
        ts3.make()
        ts3.build()

    def test_rebuild(self):
        """Check that rebuilds are handled properly."""

        ts1 = TestSet(self.pav_cfg, "test_rebuild1", ['build_parallel'])
        ts1.make()
        ts1.build()

        for test in ts1.tests:
            # Build all the tests that would have been built remotely
            if not test.build_local:
                test.build()

        build_names = [test.build_name for test in ts1.tests]

        ts1 = TestSet(self.pav_cfg, "test_rebuild2", ['build_parallel'])
        ts1.make(rebuild=True)
        ts1.build()
        for test in filter(lambda test: not test.skipped, ts1.tests):
            self.assertNotIn(test.build_name, build_names)

    def test_build_verbosity(self):
        """Check for errors in different verbosity levels."""

        for i in 0, 1, 2:
            ts = TestSet(self.pav_cfg, "test_build_verbosity", ['build_parallel'])
            ts.make()
            ts.build(verbosity=i)

    def test_kickoff(self):
        """oh no"""

        ts1 = TestSet(self.pav_cfg, "test_kickoff1", ["pass_fail"] * 5)
        ts1.make()
        ts1.build()
        self.assertEqual(ts1.kickoff(), 10)
        ts1.wait(wait_for_all=True)

        # It shouldn't hurt to kickoff when there aren't any tests.
        ts1.kickoff()

        ts1 = TestSet(self.pav_cfg, "test_kickoff2", ["pass_fail"] * 5)
        ts1.make()
        ts1.build()
        remain = 10
        for i in range(4):
            expected = min(remain, 3)
            self.assertEqual(ts1.kickoff(start_max=3), expected)
            remain -= 3
            ts1.wait(wait_for_all=True)
            if remain > 0:
                self.assertFalse(ts1.done)
            else:
                self.assertTrue(ts1.done)

        # Empty set kickoff is fine.
        ts3 = TestSet(self.pav_cfg, "test_kickoff3", [])
        ts3.make()
        ts3.build()
        self.assertEqual(ts3.kickoff(), 0)
        ts3.wait(wait_for_all=True)

    def test_wait(self):
        """Checking that we can wait for partial results."""

        ts1 = TestSet(self.pav_cfg, "test_kickoff1", ["varied_time"])
        ts1.make()
        ts1.build()
        ts1.kickoff()
        finished = ts1.wait()
        print("finished", finished)

    def test_all_passed(self):
        """Make sure we properly verify pass/fail status."""






