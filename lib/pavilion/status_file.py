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
import logging
import os


class TestStatusError(RuntimeError):
    """Error raised by any status file related problems."""


class TestStatesStruct:
    """A class containing the valid test state constants.

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
    # To add a state, simply add a valid class attribute, with the value set
    # to the help/usage for that state. States will end up comparing by key
    # name, as the instance values of these attributes will be changed and
    # the help stored elsewhere.
    UNKNOWN = "We can't determine the status."
    INVALID = "The status given to set was invalid."
    CREATED = "The test object/directory is being created."
    ABORTED = "The test run was aborted, through no fault of it's own."
    CREATION_ERROR = "The test object/directory could not be created."
    SCHEDULED = "The test has been scheduled with a scheduler."
    SCHED_ERROR = "There was a scheduler related error."
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


# There is one predefined, global status object defined at module load time.
STATES = TestStatesStruct()


class StatusInfo:
    """Represents a single status.

:ivar str state: A state string (from STATES).
:ivar str note: The note for this status update.
:ivar datetime when: A datetime object representing when this state was saved.
"""

    TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
    TS_LEN = 5 + 3 + 3 + 3 + 3 + 3 + 6

    LINE_MAX = 4096
    # Maximum length of a note. They can use every byte minux the timestamp
    # and status sizes, the spaces in-between, and the trailing newline.
    NOTE_MAX = LINE_MAX - TS_LEN - 1 - STATES.max_length - 1 - 1

    def __init__(self, state, note, when=None):

        self.state = state
        self.note = note.replace('\\n', '\n')

        if when is None:
            self.when = datetime.datetime.now()
        else:
            self.when = when

    def status_line(self):
        """Convert this to a line of text as it would be written to the
        status file."""

        # If we were given an invalid status, make the status invalid but add
        # what was given to the note.
        if not STATES.validate(self.state):
            note = '({}) {}'.format(self.state, self.note)
            state = STATES.INVALID
        else:
            state = self.state
            note = self.note

        when = self.when.strftime(StatusInfo.TIME_FORMAT)

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


class StatusFile:
    """The wraps the status file that is used in each test, and manages the
creation, reading, and modification of that file.

**NOTE:** The status file does not perform any locking to ensure that it's
created in an atomic manner. It does, however, limit it's writes to
appends of a size such that those writes should be atomic.
"""

    STATES = STATES

    LOGGER = logging.getLogger('pav.{}'.format(__file__))

    def __init__(self, path):
        """Create the status file object.

:param pathlib.Path path: The path to the status file.
"""

        self.path = path

        if not self.path.is_file():
            # Make sure we can open the file, and create it if it doesn't exist.
            self.set(STATES.CREATED, 'Created status file.')

        self._cached_current = None
        self._cached_current_touched = {
            'state': False,
            'when': False,
            'note': False
        }

    def _parse_status_line(self, line):
        """Parse a line of the status file. This assumes all sorts of things
could be wrong with the file format.

:rtype: StatusInfo
"""

        line = line.decode('utf-8')

        parts = line.split(" ", 2)
        state = ''
        note = ''
        when = None

        if parts:
            try:
                when = datetime.datetime.strptime(parts.pop(0),
                                                  StatusInfo.TIME_FORMAT)
            except ValueError as err:
                self.LOGGER.warning(
                    "Bad date in log line '%s' in file '%s': %s",
                    line, self.path, err)

        if parts:
            state = parts.pop(0)

        if parts:
            note = parts.pop(0).strip()

        status = StatusInfo(state, note, when=when)

        return status

    def history(self):
        """Return a list of all statuses recorded.

:rtype: list(StatusInfo)
"""
        try:
            with self.path.open('rb') as status_file:
                lines = status_file.readlines()
        except (OSError, IOError) as err:
            raise TestStatusError("Error opening/reading status file '{}': {}"
                                  .format(self.path, err))

        return [self._parse_status_line(line) for line in lines]

    def has_state(self, state):
        """Check if the given state is somewhere in the history of this
        status file."""

        return any([state == h.state for h in self.history()])

    def current(self):
        """Return the most recent status object.

:rtype: StatusInfo
"""

        # We read a bit extra to avoid off-by-one errors
        end_read_len = StatusInfo.LINE_MAX + 16

        try:
            with self.path.open('rb') as status_file:
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
                    return StatusInfo(
                        state=STATES.INVALID,
                        note="Status file was empty."
                    )

                return self._parse_status_line(line)

        except (OSError, IOError) as err:
            raise TestStatusError("Error reading status file '{}': {}"
                                  .format(self.path, err))

    def set(self, state: str, note: str) -> StatusInfo:
        """Set the status and return the StatusInfo object.

    :param state: The current state.
    :param note: A note about this particular instance of the state.
    """

        stinfo = StatusInfo(state, note, when=datetime.datetime.now())

        status_line = stinfo.status_line()

        try:
            with self.path.open('ab') as status_file:
                status_file.write(status_line)
        except (IOError, OSError) as err:
            raise TestStatusError("Could not write status line '{}' to status "
                                  "file '{}': {}"
                                  .format(status_line, self.path, err))

        return stinfo

    def __eq__(self, other):
        return (
            isinstance(self, type(other)) and
            self.path == other.path
        )
