"""Tests for the test_set module."""

from pavilion.series.test_set import TestSet
from pavilion.errors import TestSetError
from pavilion.unittest import PavTestCase
from pavilion.enums import Verbose


class TestSetTests(PavTestCase):

    def test_init(self):
        """Check the init function."""

        # It's ok if a set is empty. It might end up empty from skips anyway.
        TestSet(self.pav_cfg, "test_deps", [])
        TestSet(self.pav_cfg, "test_deps", ['foo'])

    def test_dependencies(self):
        """Check dependency functions."""

        ts1 = TestSet(self.pav_cfg, "ts1", ['foo'])
        ts2 = TestSet(self.pav_cfg, "ts2", ['bar1', 'bar2', 'bar3'])
        ts3 = TestSet(self.pav_cfg, "ts3", ['baz'])

        ts2.add_parents(ts1)
        ts3.add_parents(ts2)
        ts3.add_parents(ts1)

        self.assertEqual(ts1.child_sets, {ts2, ts3})
        self.assertEqual(ts1.parent_sets, set())
        self.assertEqual(ts2.parent_sets, {ts1})
        self.assertEqual(ts2.child_sets, {ts3})
        self.assertEqual(ts3.parent_sets, {ts1, ts2})
        self.assertEqual(ts3.child_sets, set())

        # TODO: Ordered split is no longer used, but may be some day.
        # ts2a, ts2b, ts2c = ts2.ordered_split()

        # self.assertEqual(ts2c, ts2)  # These should be the same object.
        # self.assertEqual(ts1.parent_sets, set())
        # Anything with ts2 as a child should now have ts2a instead
        # self.assertEqual(ts1.child_sets, {ts2a, ts3})
        # self.assertEqual(ts2a.parent_sets, {ts1})
        # self.assertEqual(ts2a.child_sets, {ts2b})
        # self.assertEqual(ts2b.parent_sets, {ts2a})
        # self.assertEqual(ts2b.child_sets, {ts2c})
        # self.assertEqual(ts2c.parent_sets, {ts2b})
        # self.assertEqual(ts2c.child_sets, {ts3})
        # self.assertEqual(ts3.parent_sets, {ts1, ts2c})

    def test_make(self):
        """Check that TestRun creation works and throws the correct errors."""

        ts1 = TestSet(self.pav_cfg, "test_make1", ['pass_fail'])
        ts1.make()

        ts1 = TestSet(self.pav_cfg, "test_make2", ['invalid'])
        with self.assertRaises(TestSetError):
            ts1.make()

        ts3 = TestSet(self.pav_cfg, "test_make3", ['invalid_results'])
        with self.assertRaises(TestSetError):
            ts3.make()

    def test_make_iter(self):
        """Check that test creation batching works."""

        ts2 = TestSet(self.pav_cfg, "test_make_iter", ['build_parallel']*2,
                      simultaneous=8)

        # The second set is small because of a skipped test.
        sizes = [4, 3, 1]

        # Make sure we make batches of half the simultanious limit.
        for batch in ts2.make_iter():
            self.assertEqual(len(batch), sizes.pop(0))

        self.assertFalse(sizes)


    def test_build(self):
        """Check that building works as expected."""

        ts1 = TestSet(self.pav_cfg, "test_build1", ['build_parallel'])
        ts1.make()
        ts1.build()

        ts1 = TestSet(self.pav_cfg, "test_build2", ['build_fail'])
        tests1 = ts1.make()
        self.assertEqual(len(tests1), 6)
        with self.assertRaises(TestSetError):
            ts1.build()

        # Building an empty set should be fine.
        ts3 = TestSet(self.pav_cfg, "test_build3", [])
        ts3.make()
        ts3.build()

    def test_rebuild(self):
        """Check that rebuilds are handled properly."""

        ts1 = TestSet(self.pav_cfg, "test_rebuild1", ['build_rebuild'])
        ts1.make()
        ts1.build()

        # Build the remote builds too.
        for test in ts1.tests:
            if not test.build_local:
                test.build()

        build_names = set([test.build_name for test in ts1.tests])
        dep_builds = set()

        ts2 = TestSet(self.pav_cfg, "test_rebuild2", ['build_rebuild']*2,
                      simultaneous=4)

        ts2.make(rebuild=True)
        ts2.build(deprecated_builds=dep_builds)

        # Ensure that all the builds got deprecated.
        self.assertEqual(dep_builds, build_names)

        # Check that none of the new builds are in the deprecated builds
        for test in ts2.tests:
            self.assertNotIn(test.builder.name, dep_builds)

    def test_build_verbosity(self):
        """Check for errors in different verbosity levels."""

        for vbs in Verbose.QUIET, Verbose.MAX, Verbose.HIGH, Verbose.DYNAMIC:
            ts = TestSet(self.pav_cfg, "test_build_verbosity", ['build_parallel'],
                         verbosity=vbs)
            ts.make()
            ts.build()

    def test_ignore_errors(self):
        """Make sure build errors are handled properly when ignore_errors=True"""

        ts1 = TestSet(self.pav_cfg, "test_set_errors", ["test_set_errors"],
                      ignore_errors=True, verbosity=Verbose.MAX)
        ts1.make()
        self.assertEqual(len(ts1.ready_to_build), 4,
                         msg=', '.join(t.name for t in ts1.ready_to_build))
        ts1.build()
        for test in ts1.tests:
            if 'bad_build' in test.name:
                self.assertTrue(test.complete, msg=test.name)
            else:
                self.assertFalse(test.complete, msg=test.name)

        ts1.kickoff()
        self.assertEqual(len(ts1.started_tests), 1)
        self.assertEqual(ts1.started_tests[0].name, 'test_set_errors.good')


    def test_kickoff(self):
        """Check kickoff functionality."""

        ts1 = TestSet(self.pav_cfg, "test_kickoff1", ["pass_fail"] * 5)
        ts1.make()
        ts1.build()
        self.assertEqual(len(ts1.kickoff()[0]), 10)
        ts1.wait(wait_for_all=True)

        # It shouldn't hurt to kickoff when there aren't any tests.
        ts1.kickoff()


        expected = [
            ['pass_fail.fail', 'pass_fail.pass', 'pass_fail.pass'],
            ['pass_fail.fail', 'pass_fail.fail', 'pass_fail.pass'],
            ['pass_fail.fail', 'pass_fail.pass', 'pass_fail.pass'],
            ['pass_fail.fail'],
        ]

        ts2 = TestSet(self.pav_cfg, "test_kickoff2", ["pass_fail"] * 5,
                      simultaneous=6)
        for _ in ts2.make_iter():
            ts2.build()
            exp_names = expected.pop(0)
            started_tests, jobs = ts2.kickoff()
            start_names = [test.name for test in started_tests]
            start_names.sort()
            exp_names.sort()
            self.assertEqual(start_names, exp_names)
            ts2.wait(wait_for_all=True)

        self.assertEqual(expected, [])

        # Empty set kickoff is fine.
        ts3 = TestSet(self.pav_cfg, "test_kickoff3", [])
        ts3.make()
        ts3.build()
        self.assertEqual(len(ts3.kickoff()[0]), 0)
        ts3.wait(wait_for_all=True)

    def test_wait(self):
        """Checking that we can wait for partial results."""

        ts1 = TestSet(self.pav_cfg, "test_kickoff1", ["varied_time"])
        ts1.make()
        ts1.build()
        ts1.kickoff()
        self.assertNotEqual(ts1.wait(), 3)

    def test_all_passed(self):
        """Make sure we properly verify pass/fail status."""

        ts1 = TestSet(self.pav_cfg, "test_all_passed1", ["pass_fail"] * 2)
        ts1.make()
        ts1.build()
        ts1.kickoff()
        ts1.wait(wait_for_all=True)
        self.assertFalse(ts1.all_passed)

        ts2 = TestSet(self.pav_cfg, "test_all_passed2", ["pass_fail.pass"] * 2)
        ts2.make()
        ts2.build()
        ts2.kickoff()
        ts2.wait(wait_for_all=True)
        self.assertTrue(ts2.all_passed, msg=[test.result for test in ts2.tests])

    def test_cancel(self):
        """Check test set cancellation."""
        ts1 = TestSet(self.pav_cfg, "test_cancel", ["varied_time"] * 2)
        ts1.make()
        ts1.build()
        ts1.kickoff()
        ts1.cancel("Testing cancelation.")
        ts1.wait(wait_for_all=True)
        for test in ts1.tests:
            self.assertEqual(test.status.current().state,
                             test.status.states.CANCELLED,
                             msg="Test {} should be aborted".format(test.full_id))
        self.assertFalse(ts1.all_passed)

    def test_should_run(self):
        """Make sure test_sets properly understand when they should and shouldn't
        run."""

        # A Test set should only run if all of it's parents should run.
        #       ts1        - Will fail
        #      /   \
        #    ts2    ts2_pmp  - ts2 should run, but ts2_pmp should not
        #     |  \ /   |
        #     |  / \   |
        #     ts3   ts3_pmp  - Neither should run, because they both depend on a test
        #     |                set (ts2_pmp) that shouldn't run.
        #     ts4            - Shouldn't run, because t3 shouldn't.

        ts1 = TestSet(self.pav_cfg, "test_should", ["pass_fail"])
        ts2_pmp = TestSet(self.pav_cfg, "test_should2_pmp", ["varied_time"],
                          parents_must_pass=True)
        ts2 = TestSet(self.pav_cfg, "test_should2", ["varied_time"])
        ts3_pmp = TestSet(self.pav_cfg, "test_should3_pmp", ["varied_time"],
                          parents_must_pass=True)
        ts3 = TestSet(self.pav_cfg, "test_should3", ["varied_time"])
        ts4 = TestSet(self.pav_cfg, "test_should4", ["pass_fail"])

        ts2.add_parents(ts1)
        ts2_pmp.add_parents(ts1)
        ts3.add_parents(ts2, ts2_pmp)
        ts3_pmp.add_parents(ts2, ts2_pmp)
        ts4.add_parents(ts3)
        ts1.make()
        ts1.build()
        ts1.kickoff()
        ts1.wait(wait_for_all=True)
        self.assertTrue(ts2.should_run)
        self.assertFalse(ts2_pmp.should_run)
        self.assertFalse(ts3.should_run)
        self.assertFalse(ts3_pmp.should_run)
        self.assertFalse(ts4.should_run)

        # Do this again, but this time ts1 should pass and all but a one 'should_run'.
        ts1 = TestSet(self.pav_cfg, "test_should", ["pass_fail.pass"])
        ts2_pmp = TestSet(self.pav_cfg, "test_should2_pmp", ["varied_time"],
                          parents_must_pass=True)
        ts2 = TestSet(self.pav_cfg, "test_should2", ["varied_time"])
        ts3_pmp = TestSet(self.pav_cfg, "test_should3_pmp", ["varied_time"],
                          parents_must_pass=True)
        ts3 = TestSet(self.pav_cfg, "test_should3", ["varied_time"])
        ts4 = TestSet(self.pav_cfg, "test_should4", ["pass_fail"])

        ts2.add_parents(ts1)
        ts2_pmp.add_parents(ts1)
        ts3.add_parents(ts2, ts2_pmp)
        ts3_pmp.add_parents(ts2, ts2_pmp)
        ts4.add_parents(ts3)
        ts1.make()
        ts1.build()
        ts1.kickoff()
        ts1.wait(wait_for_all=True)
        self.assertTrue(ts2.should_run)
        self.assertTrue(ts2_pmp.should_run)
        self.assertTrue(ts3.should_run)
        # This should be None in this case because we can't know if it should run
        # until all of its parents tests have run.
        self.assertIsNone(ts3_pmp.should_run)
        self.assertTrue(ts4.should_run)
