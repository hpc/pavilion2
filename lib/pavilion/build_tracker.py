"""Tracks builds across multiple threads, including their output."""

import datetime
import logging
import threading
from collections import defaultdict

from pavilion.status_file import STATES


class MultiBuildTracker:
    """Allows for the central organization of multiple build tracker objects.

    :ivar {StatusFile} status_files: The dictionary of status files by build."""

    def __init__(self, log=True):
        """Setup the build tracker.
       :param bool log: Whether to also log messages in some instances.
        """

        # A map of build tokens to build names
        self.messages = {}
        self.status = {}
        self.status_files = {}
        self.lock = threading.Lock()

        self.logger = None
        if log:
            self.logger = logging.getLogger(__name__)

    def register(self, builder, test_status_file):
        """Register a builder, and get your own build tracker.

    :param TestBuilder builder: The builder object to track.
    :param status_file.StatusFile test_status_file: The status file object
        for the corresponding test.
    :return: A build tracker instance that can be used by builds directly.
    :rtype: BuildTracker"""

        with self.lock:
            self.status_files[builder] = test_status_file
            self.status[builder] = None
            self.messages[builder] = []

        tracker = BuildTracker(builder, self)
        return tracker

    def update(self, builder, note, state=None, log=None):
        """Add a message for the given builder without changes the status.

        :param TestBuilder builder: The builder object to set the message.
        :param note: The message to set.
        :param str state: A status_file state to set on this builder's status
            file.
        :param int log: A log level for the python logger. If set, also
            log the message to the Pavilion log.
        """

        if state is not None:
            self.status_files[builder].set(state, note)

        now = datetime.datetime.now()

        with self.lock:
            self.messages[builder].append((now, state, note))
            if state is not None:
                self.status[builder] = state

        if log is not None and self.logger:
            self.logger.log(level=log, msg=note)

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
            counts[state] += 1

        return counts

    def failures(self):
        """Returns a list of builders that have failed."""
        return [builder for builder in self.status.keys()
                if builder.tracker.failed]


class BuildTracker:
    """Tracks the status updates for a single build."""

    def __init__(self, builder, tracker):
        self.builder = builder
        self.tracker = tracker
        self.failed = False

    def update(self, note, state=None, log=None):
        """Update the tracker for this build with the given note."""

        self.tracker.update(self.builder, note, log=log, state=state)

    def warn(self, note, state=None):
        """Add a note and warn via the logger."""
        self.tracker.update(self.builder, note, log=logging.WARNING,
                            state=state)

    def error(self, note, state=STATES.BUILD_ERROR):
        """Add a note and error via the logger denote as a failure."""
        self.tracker.update(self.builder, note, log=logging.ERROR, state=state)

        self.failed = True

    def fail(self, note, state=STATES.BUILD_FAILED):
        """Denote that the test has failed."""
        self.error(note, state=state)

    def notes(self):
        """Return the notes for this tracker."""
        return self.tracker.get_notes(self.builder)
