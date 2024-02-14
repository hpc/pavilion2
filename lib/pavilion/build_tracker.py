"""Tracks builds across multiple threads, including their output."""

import datetime
import threading
from collections import defaultdict
from typing import List, ContextManager
from contextlib import contextmanager

from pavilion.status_file import STATES
from .lockfile import NFSLock


class MultiBuildTracker:
    """Allows for the central organization of multiple build tracker objects.

    :ivar {StatusFile} status_files: The dictionary of status files by build."""

    def __init__(self):
        """Setup the build tracker."""

        # A map of build tokens to build names
        self.messages = {}
        self.status = {}
        self.status_files = {} # type: Dict[TestBuilder, TestStatusFile]
        self.trackers = {}
        self.lock = threading.Lock()

    def register(self, test: 'TestRun') -> 'BuildTracker':
        """Register a builder, and get your own build tracker.

        :param test: The TestRun object to track.
        :return: A build tracker instance that can be used by builds directly."""

        tracker = BuildTracker(test, self)

        with self.lock:
            # Test may actually be a TestRun object rather than a TestBuilder object,
            # which has no builder attribute
            self.status_files[test.builder] = test.status
            self.status[test.builder] = None
            self.messages[test.builder] = []
            self.trackers[test.builder] = tracker

        return tracker

    def get_build_lock(self, builder: 'TestBuilder', timeout: float = -1) -> 'NFSLock':
        """Get the NFSLock object associated with a particular build.

        :param hash: the hash of the build whose lock will be returned
        :return: the NFSLock for the build
        """

        return NFSLock(builder.path.parent, builder.name, timeout=timeout)

    def update(self, builder, note, state=None):
        """Add a message for the given builder without changes the status.

        :param TestBuilder builder: The builder object to set the message.
        :param note: The message to set.
        :param str state: A status_file state to set on this builder's status
            file.
        """

        if state is not None:
            self.status_files[builder].set(state, note)

        now = datetime.datetime.now()

        with self.lock:
            self.messages[builder].append((now, state, note))
            if state is not None:
                self.status[builder] = state

    def get_notes(self, builder):
        """Return all notes for the given builder.

        :param TestBuilder builder: The test builder object to get notes for.
        :rtype: [str]
        """

        return self.messages[builder]

    def state_counts(self):
        """Return a dictionary of the states across all builds and the number
        of occurrences of each."""
        counts = defaultdict(lambda: 0)
        for state in self.status.values():
            if state is not None:
                counts[state] += 1

        return counts

    def failures(self) -> List['BuildTracker']:
        """Returns a list of builders that have failed."""
        return [self.trackers[builder] for builder in self.trackers
                if self.trackers[builder].failed]


class BuildTracker:
    """Tracks the status updates for a single build."""

    def __init__(self, test: 'TestRun', tracker: MultiBuildTracker):
        self.test = test
        if test is None:
            self.builder = None
        else:
            self.builder = test.builder
        self.tracker = tracker
        self.failed = False

    def update(self, note, state=None):
        """Update the tracker for this build with the given note."""

        self.tracker.update(self.builder, note, state=state)

    def warn(self, note, state=None):
        """Add a note and warn via the logger."""
        self.update(note, state=state)

    def error(self, note, state=STATES.BUILD_ERROR):
        """Add a note and error via the logger denote as a failure."""
        self.update(note, state=state)

        self.failed = True

    def fail(self, note, state=STATES.BUILD_FAILED):
        """Denote that the test has failed."""
        self.error(note, state=state)

    def notes(self):
        """Return the notes for this tracker."""
        return self.tracker.get_notes(self.builder)


class DummyTracker(BuildTracker):
    """A tracker that does nothing."""

    def __init__(self):
        """Initalize the parent with dummy info."""

        super().__init__(None, None)

    def update(self, note, state=None):
        """Do nothing."""
