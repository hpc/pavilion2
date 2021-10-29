"""Every test run has a status file that tracks it's progress. It's
one of the first things created (after the test directory itself) when
creating a test object.

A test run will transition through several states (all available as part of the
``status_file.STATES`` object). These, along with a description and timestamp,
are saved as a 'state' in the status file. Each state is a single line of the
file with a max size of 4096 bytes to ensure atomic writes.

The state of a test run represents where that run is in its lifecycle. It
does not represent whether a test passed or failed. States are ephemeral and
asynchronous, and should generally not be used to decide to do something with a
test run. (The only exception is the 'SCHEDULED' state, which tells Pavilion
to ask the scheduler about its current state).

Usage: ::

    status_file = StatusFile('/tmp/mystatus')

    status.set(STATES.RUNNING, "I'm running!")

    state = status.current()

    state.note
"""

import datetime
import os
import pathlib
import time
from io import BytesIO
from typing import List, Union


class StatusError(RuntimeError):
    """Error raised by any status file related problems."""


class StatesStruct:
    """A class containing the valid state constants. This is meant to be inherited
from and the states added as FOO="bar" class variables.

Rules:

- The value should be an ascii string of the constant name.
- The constants have a max length of 15 characters.
- The constants are in all caps.
- The constants must be a valid python identifier that starts with a letter.
- Error states should end in '_ERROR'. They should be the result of an OS
  level problem (like missing directories), or problems with Pavilion itself.
- Failure states should end in '_FAILED'. They should be the result of trying
  something, and it just not succeeding.

**Note**: The states are written in the class as ``<state_name> = <help_text>``,
however, on class init the help text is stored separately, and the state value
is set to the name of the state itself. So STATES.ENV_FAILED will have a
value of 'ENV_FAILED' when used.

Known States:
"""
    # Base states available in all state classes
    UNKNOWN = "We can't determine the status."
    INVALID = "The status given to set was invalid."
    STATUS_ERROR = "An error with the status file itself."
    STATUS_CREATED = "The status file has been created."
    WARNING = "General warning (non-fatal error) status information."

    max_length = 15

    def __init__(self):
        """Validate all of the constants."""

        self._help = {}

        # Validate the built-in states
        for key in dir(self):
            if key.startswith('_') or key[0].islower():
                continue

            if not self.validate(key):
                raise RuntimeError("Invalid StatusFile constant '{}'."
                                   .format(key))

            # Save the help to a local dict.
            self._help[key] = getattr(self, key)

            # Set the instance values of each state to the state name.
            setattr(self, key, key)

    def validate(self, key):
        """Make sure the key conforms to the above rules."""
        return (key[0].isalpha() and
                key.isupper() and
                key.isidentifier() and
                len(key.encode('utf-8')) == len(key) and
                len(key) <= self.max_length and
                hasattr(self, key))

    def get(self, key):
        """Get the value of the status key."""
        return getattr(self, key)

    def help(self, state):
        """Get the help string for a state."""
        return self._help.get(state,
                              "Help missing for state '{}'".format(state))

    def list(self):
        """List all the known state names."""
        return self._help.keys()


class TestStatesStruct(StatesStruct):
    """Struct containing pre-defined test states."""

    # To add a state, simply add a valid class attribute, with the value set
    # to the help/usage for that state. States will end up comparing by key
    # name, as the instance values of these attributes will be changed and
    # the help stored elsewhere.
    CREATED = "The test object/directory is being created."
    ABORTED = "Aborted, through no fault of it's own."
    CREATION_ERROR = "The test object/directory could not be created."
    SCHEDULED = "The test has been scheduled with a scheduler."
    SCHED_ERROR = "There was a scheduler related error."
    SCHED_WINDUP = "The scheduler is prepping to run, but has not yet started the" \
                   "actual test."
    SCHED_CANCELLED = "The job was cancelled."
    BUILDING = "The test is currently being built."
    BUILD_CREATED = "The builder for this build was created."
    BUILD_DEFERRED = "The build will occur on nodes."
    BUILD_FAILED = "The build has failed."
    BUILD_TIMEOUT = "The build has timed out."
    BUILD_ERROR = "An unexpected error occurred while setting up the build."
    BUILD_DONE = "The build step has completed."
    BUILD_WAIT = "Waiting for the build lock."
    BUILD_REUSED = "The build was reused from a prior step."
    INFO = "This is for logging information about a test, and can occur" \
           "within any state."
    ENV_FAILED = "Unable to load the environment requested by the test."
    PREPPING_RUN = "Performing final (on node) steps before the test run."
    RUNNING = "For when we're currently running the test."
    RUN_TIMEOUT = "The test run went long without any output."
    RUN_ERROR = "An unexpected error has occurred when setting up the test run."
    RUN_USER = "Jobs can report extra status using pav set_status and " \
               "this status value."
    RUN_DONE = "For when the run step is complete."
    RESULTS = "For when we're getting the results."
    RESULTS_ERROR = "A result parser raised an error."
    SKIPPED = "The test has been skipped due to an invalid condition."
    COMPLETE = "For when the test is completely complete."


class SeriesStatesStruct(StatesStruct):
    """States for series objects."""

    # To add a state, simply add a valid class attribute, with the value set
    # to the help/usage for that state. States will end up comparing by key
    # name, as the instance values of these attributes will be changed and
    # the help stored elsewhere.
    ABORTED = "Aborted, through no fault of it's own."
    CREATED = "The series object/directory is being created."
    CREATION_ERROR = "The test object/directory could not be created."
    SET_CREATED = "For when test sets are created."
    SET_MAKE = "For when test runs are created in the test set."
    SET_BUILD = "For when test sets are building."
    SET_KICKOFF = "For when test sets are being kicked off."
    SKIPPED = "For logging when tests are skipped."
    RUN = "Running the series."
    ERROR = "General (fatal) error status."
    COMPLETE = "For when the test is completely complete."


# There is one predefined, global status object defined at module load time.
STATES = TestStatesStruct()
SERIES_STATES = SeriesStatesStruct()


class TestStatusInfo:
    """Represents a single status.

:ivar str state: A state string (from STATES or SERIES_STATES).
:ivar str note: The note for this status update.
:ivar datetime when: A datetime object representing when this state was saved.
"""

    TS_FORMAT = '{:0.6f}'
    TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
    MAX_TS = datetime.datetime(9999, 12, 31, 1, 1, 1, 123456).timestamp()
    TS_LEN = max([5 + 3 + 3 + 3 + 3 + 3 + 6, len(TS_FORMAT.format(MAX_TS))])

    LINE_MAX = 4096
    # Maximum length of a note. They can use every byte minux the timestamp
    # and status sizes, the spaces in-between, and the trailing newline.
    NOTE_MAX = LINE_MAX - TS_LEN - 1 - StatesStruct.max_length - 1 - 1

    states_obj = STATES

    def __init__(self, state: str, note: str, when: float = None):

        self.state = state
        self.note = note.replace('\\n', '\n')

        if when is None:
            self.when = time.time()
        else:
            self.when = when

    def status_line(self):
        """Convert this to a line of text as it would be written to the
        status file."""

        # If we were given an invalid status, make the status invalid but add
        # what was given to the note.
        if not self.states_obj.validate(self.state):
            note = '({}) {}'.format(self.state, self.note)
            state = self.states_obj.INVALID
        else:
            state = self.state
            note = self.note

        # There could be a large negative time, I guess, but it's unlikely.
        when = self.TS_FORMAT.format(min([self.when, self.MAX_TS]))

        note = note.replace('\n', '\\n')

        # Truncate the note such that, even when encoded in utf-8, it is
        # shorter than NOTE_MAX
        note = note.encode()[:self.NOTE_MAX].decode('utf-8', 'ignore')

        return '{} {} {}\n'.format(when, state, note).encode()

    def __str__(self):
        return 'Status: {s.when} {s.state} {s.note}'.format(s=self)

    def __repr__(self):
        return 'StatusInfo({s.when}, {s.state}, {s.note})'.format(s=self)

    def as_dict(self):
        """Convert to a dictionary.

:rtype: dict
"""
        status_dict = {"state": self.state, "note": self.note,
                       "time": self.when}

        return status_dict


class SeriesStatusInfo(TestStatusInfo):
    """A status info object, except for series."""

    states_obj = SERIES_STATES


class TestStatusFile:
    """The wraps the status file that is used in each test, and manages the
creation, reading, and modification of that file.

**NOTE:** The status file does not perform any locking to ensure that it's
created in an atomic manner. It does, however, limit it's writes to
appends of a size such that those writes should be atomic.
"""

    states = STATES
    info_class = TestStatusInfo

    def __init__(self, path: Union[pathlib.Path, None]):
        """Create the status file object.

    :param path: The path to the status file. If Path is None, use a StringIO object.
    """

        self.path = path
        self._dummy = BytesIO() if path is None else None

        if self.path is not None and not self.path.is_file():
            # Make sure we can open the file, and create it if it doesn't exist.
            self.set(self.states.STATUS_CREATED, 'Created status file.')

        self._cached_current = None
        self._cached_current_touched = {
            'state': False,
            'when': False,
            'note': False
        }

    def _parse_status_line(self, line) -> TestStatusInfo:
        """Parse a line of the status file. This assumes all sorts of things
could be wrong with the file format."""

        line = line.decode('utf-8')

        parts = line.split(" ", 2)
        state = ''
        note = ''
        when = None

        if parts:
            time_part = parts.pop(0)
            try:
                when = float(time_part)
            except ValueError:
                try:
                    when = datetime.datetime.strptime(
                        parts.pop(0), self.info_class.TIME_FORMAT).timestamp()
                except ValueError:
                    # Use the beginning of time on errors
                    when = datetime.datetime(0, 0, 0)

        if parts:
            state = parts.pop(0)

        if parts:
            note = parts.pop(0).strip()

        status = self.info_class(state, note, when=when)

        return status

    def history(self) -> List[TestStatusInfo]:
        """Return a list of all statuses recorded."""

        if self.path is not None:
            try:
                with self.path.open('rb') as status_file:
                    return self._read_history(status_file)
            except OSError as err:
                return [self.info_class(self.states.STATUS_ERROR,
                                        "Could open status file at '{}': {}"
                                        .format(self.path, err.args[0]))]
        else:
            return self._read_history(self._dummy)

    def _read_history(self, status_file):
        """Read the history file and return all statuses."""

        lines = []

        try:
            for line in status_file:
                lines.append(line)
        except OSError as err:
            lines.append(TestStatusInfo(
                self.states.STATUS_ERROR,
                "Error reading status file '{}': {}".format(self.path, err)))

        return [self._parse_status_line(line) for line in lines]

    def has_state(self, state) -> bool:
        """Check if the given state is somewhere in the history of this
        status file."""

        return any([state == h.state for h in self.history()])

    def current(self) -> TestStatusInfo:
        """Return the most recent status object."""

        if self.path is not None:
            try:
                with self.path.open('rb') as status_file:
                    return self._current(status_file)
            except OSError as err:
                return self.info_class(self.states.STATUS_ERROR,
                                       "Could open status file at '{}': {}"
                                       .format(self.path, err.args[0]))
        else:
            return self._current(self._dummy)

    def _current(self, status_file):

        # We read a bit extra to avoid off-by-one errors
        end_read_len = self.info_class.LINE_MAX + 16

        try:
            status_file.seek(0, os.SEEK_END)
            file_len = status_file.tell()
            if file_len < end_read_len:
                status_file.seek(0)
            else:
                status_file.seek(-end_read_len, os.SEEK_END)

            lines = status_file.readlines()
            if lines:
                # Get the last line.
                line = lines[-1]
            else:
                return self.info_class(
                    state=self.states.INVALID,
                    note="Status file was empty."
                )

            return self._parse_status_line(line)

        except OSError as err:
            return self.info_class(self.states.STATUS_ERROR,
                                   "Error reading status file '{}': {}"
                                   .format(self.path, err))

    def set(self, state: str, note: str) -> TestStatusInfo:
        """Set the status and return the StatusInfo object. Well return a
        'STATUS_ERROR' status on write failures.

    :param state: The current state.
    :param note: A note about this particular instance of the state.
    """

        stinfo = self.info_class(state, note, when=time.time())

        return self.add_status(stinfo)

    def add_status(self, status: TestStatusInfo) -> TestStatusInfo:
        """Add the status object as a status for the test."""

        if self.path is not None:
            try:
                with self.path.open('ab') as status_file:
                    return self._set(status_file, status)
            except OSError as err:
                return self.info_class(self.states.STATUS_ERROR,
                                       "Could open status file at '{}': {}"
                                       .format(self.path, err.args[0]))
        else:
            return self._set(self._dummy, status)

    def _set(self, status_file, stinfo) -> TestStatusInfo:
        """Do the actual status setting step, given a file and the status object."""

        status_line = stinfo.status_line()

        try:
            status_file.write(status_line)
        except OSError as err:
            stinfo = self.info_class(self.states.STATUS_ERROR,
                                     "Could not write to status file at '{}': {}"
                                     .format(self.path, err.args[0]))

        return stinfo

    def __eq__(self, other):
        return (
            isinstance(self, type(other)) and
            self.path == other.path
        )


class SeriesStatusFile(TestStatusFile):
    """A status file for series."""

    states = SERIES_STATES
    info_class = SeriesStatusInfo
