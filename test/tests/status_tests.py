from pavilion.status_file import StatusFile, STATES
from pavilion.unittest import PavTestCase
import datetime
import os
import subprocess
import tempfile
import time
import tzlocal


class StatusTests(PavTestCase):

    def test_status(self):
        """Checking status object basic functionality."""

        fn = tempfile.mktemp()

        status = StatusFile(fn)

        self.assertTrue(os.path.exists(fn))
        status_info = status.current()
        self.assertEqual(status_info.state, 'CREATED')

        # Get a non-naive timestamp, set to our local time zone.
        now = datetime.datetime.now()
        now = tzlocal.get_localzone().localize(now)

        # Make sure the timestamp is before now.
        self.assertLess(status_info.when, now)
        # Make sure the timestamp is less than a few seconds in the future.
        # If things are wrong with our timestamping code, they'll be much
        # farther off than this.
        self.assertGreater(now + datetime.timedelta(seconds=5),
                           status_info.when)
        
        self.assertEqual(status_info.note, 'Created status file.')
        
        # Dump a bunch of states to the status file.
        states = [STATES.UNKNOWN, STATES.INVALID, STATES.CREATED,
                  STATES.RUNNING, STATES.RESULTS]
        for state in states:
            status.set(state, '{}_{}'.format(state, state.lower()))
        
        self.assertEqual(len(status.history()), 6)
        self.assertEqual(status.current().state, 'RESULTS')
        self.assertEqual([s.state for s in status.history()].sort(),
                         (states + ['CREATED']).sort())

        # Make sure too long statuses are handled correctly.
        status.set("AN_EXCESSIVELY_LONG_STATE_NAME",
                   "This is " + "way "*10000 + "too long.")
        status_info = status.current()

        self.assertLessEqual(len(status_info.state), STATES.max_length)
        self.assertEqual(status_info.state, STATES.INVALID)
        self.assertLessEqual(len(status_info.note), status.NOTE_MAX)

        with open(fn, 'r') as sf:
            lines = sf.readlines()

            self.assertLessEqual(len(lines[-1]), status.LINE_MAX)

        os.unlink(fn)

    def test_atomicity(self):
        """Making sure the status file can be written to atomically."""

        proc_count = 10

        fn = tempfile.mktemp()

        fight_path = os.path.join(os.path.dirname(__file__), 'status_fight.py')

        procs = []
        for i in range(proc_count):
            procs.append(subprocess.Popen(['python3', fight_path, fn]))

        time.sleep(0.2)

        # Create the status file, which should start the procs writing.
        with open(fn, 'w'):
            pass

        for proc in procs:
            self.assertEqual(proc.wait(), 0,
                             msg="status_fight sub-test had an error.")

        # Make sure the entire history can be read sanely.
        status = StatusFile(fn)
        history = status.history()

        for entry in history:
            # All the states should be running
            # (The first is normally 'CREATED', but we bypassed the normal
            # creation of the file)
            self.assertEqual(entry.state, STATES.RUNNING)
            # Make sure the state never bled into the note, and that the
            # note was found.
            self.assert_(STATES.RUNNING not in entry.note)
            self.assertNotEqual(entry.note, '')
            # Make sure nothing else bled into the note (namely, the timestamp)
            self.assertLess(len(entry.note), 20)
            # Make sure we have a sane date on all lines. This will be None
            # if we couldn't parse
            # the date.
            self.assertIsNot(entry.when, None)

        os.unlink(fn)
