import datetime
import logging
import os
import tzlocal


class TestStatusError(RuntimeError):
    pass


class TestStatesStruct:
    """A class containing the valid test state constants.
    Rules:
      - The value should be an ascii string of the constant name.
      - The constants have a max length of 15 characters.
      - The constants are in all caps.
      - The constants must be a valid python identifier that starts with a
        letter.
    """

    # To add a state, simply add a valid class attribute, with the value set
    # to the help/usage for that state. States will end up comparing by key
    # name, as the instance values of these attributes will be changed and
    # the help stored elsewhere.
    UNKNOWN = "We can't determine the status."
    INVALID = "The status given to set was invalid."
    CREATED = "The test object/directory is being created."
    CREATION_ERROR = "The test object/directory could not be created."
    SCHEDULED = "The test has been scheduled with a scheduler."
    SCHED_ERROR = "There was a scheduler related error."
    SCHED_CANCELLED = "The job was cancelled."
    BUILDING = "The test is currently being built."
    BUILD_FAILED = "The build has failed."
    BUILD_ERROR = "An unexpected error occurred while setting up the build."
    BUILD_DONE = "The build step has completed."
    ENV_FAILED = "Unable to load the environment requested by the test."
    PREPPING_RUN = "Performing final (on node) steps before the test run."
    RUNNING = "For when we're currently running the test."
    RUN_TIMEOUT = "The test run went long without any output."
    RUN_FAILED = "The test run has failed."
    RUN_ERROR = "An unexpected error has occurred when setting up the test run."
    RUN_USER = "Jobs can report extra status using pav set_status and " \
               "this status value."
    RUN_DONE = "For when the run step is complete."
    RESULTS = "For when we're getting the results."
    RESULTS_ERROR = "A result parser raised an error."
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
        return self._help.keys()


# There is one predefined, global status object defined at module load time.
STATES = TestStatesStruct()


class StatusInfo:
    def __init__(self, state, note, when=None):

        self.state = state
        self.note = note

        if when is None:
            self.when = tzlocal.get_localzone().localize(
                datetime.datetime.now()
            )
        else:
            self.when = when

    def __str__(self):
        return 'Status: {s.when} {s.state} {s.note}'.format(s=self)

    def __repr__(self):
        return 'StatusInfo({s.when}, {s.state}, {s.note})'.format(s=self)


class StatusFile:
    """The wraps the status file that is used in each test, and manages the
    creation, reading, and modification of that file.
    NOTE: The status file does not perform any locking to ensure that it's
    created in an atomic manner. It does, however, limit it's writes to
    appends of a size such that those writes should be atomic.
    """

    STATES = STATES

    TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
    TS_LEN = 5 + 3 + 3 + 3 + 3 + 3 + 6 + 14

    LOGGER = logging.getLogger('pav.{}'.format(__file__))

    LINE_MAX = 4096
    # Maximum length of a note. They can use every byte minux the timestamp
    # and status sizes, the spaces in-between, and the trailing newline.
    NOTE_MAX = LINE_MAX - TS_LEN - 1 - STATES.max_length - 1 - 1

    def __init__(self, path):
        """Create the status file object.
        :param pathlib.Path path: The path to the status file.
        """

        if isinstance(path, str):
            raise ValueError('NOOO')

        self.path = path

        self.timezone = tzlocal.get_localzone()

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

        status = StatusInfo('', '', )

        if parts:
            try:
                status.when = datetime.datetime.strptime(parts.pop(0),
                                                         self.TIME_FORMAT)
            except ValueError as err:
                self.LOGGER.warning(
                    "Bad date in log line '%s' in file '%s': %s",
                    line, self.path, err)

        if parts:
            status.state = parts.pop(0)

        if parts:
            status.note = parts.pop(0).strip()

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

    def current(self):
        """Return the most recent status object.
        :rtype: StatusInfo
        """

        # We read a bit extra to avoid off-by-one errors
        end_read_len = self.LINE_MAX + 16

        try:
            with self.path.open('rb') as status_file:
                status_file.seek(0, os.SEEK_END)
                file_len = status_file.tell()
                if file_len < end_read_len:
                    status_file.seek(0)
                else:
                    status_file.seek(-end_read_len, os.SEEK_END)

                # Get the last line.
                line = status_file.readlines()[-1]

                return self._parse_status_line(line)

        except (OSError, IOError) as err:
            raise TestStatusError("Error reading status file '{}': {}"
                                  .format(self.path, err))

    def set(self, state, note):
        """Set the status.
        :param state: The current state.
        :param note: A note about this particular instance of the state.
        """

        when = self.timezone.localize(datetime.datetime.now())
        when = when.strftime(self.TIME_FORMAT)

        # If we were given an invalid status, make the status invalid but add
        # what was given to the note.
        if not STATES.validate(state):
            note = '({}) {}'.format(state, note)
            state = STATES.INVALID

        # Truncate the note such that, even when encoded in utf-8, it is
        # shorter than NOTE_MAX
        note = note.encode('utf-8')[:self.NOTE_MAX].decode('utf-8', 'ignore')

        status_line = '{} {} {}\n'.format(when, state, note).encode('utf-8')
        try:
            with self.path.open('ab') as status_file:
                status_file.write(status_line)
        except (IOError, OSError) as err:
            raise TestStatusError("Could not write status line '{}' to status "
                                  "file '{}': {}"
                                  .format(status_line, self.path, err))

    def __eq__(self, other):
        return (
            isinstance(self, type(other)) and
            self.path == other.path
        )
