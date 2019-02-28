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
      - The constants must be a valid python identifier that starts with a letter.
    """

    UNKNOWN = 'UNKNOWN'         # For when we can't determine the status.
    INVALID = 'INVALID'         # For when the status given was invalid.
    CREATED = 'CREATED'         # Always the initial status of the status file.
    BUILDING = 'BUILDING'       # For when we're currently building the test.
    BUILD_DONE = 'BUILD_DONE'   # For when the build step has completed.
    RUNNING = 'RUNNING'         # For when we're currently running the test.
    RUN_DONE = 'RUN_DONE'       # For when the run step is complete.
    RESULTS = 'RESULTS'         # For when we're getting the results.
    COMPLETE = 'COMPLETE'       # For when the test is completely complete.

    MAX_LENGTH = 15

    def __init__(self):
        """Validate all of the constants."""

        for key in self.__class__.__dict__.keys():
            if key.startswith('_') or key in ['get', 'validate', 'MAX_LENGTH']:
                continue

            if not self.validate(key):
                raise RuntimeError("Invalid StatusFile constant '{}'.".format(key))

    def validate(self, key):
        """Make sure the key conforms to the above rules."""
        return (key[0].isalpha() and
                key.isupper() and
                key.isidentifier() and
                len(key.encode('utf-8')) == len(key) and
                len(key) <= self.MAX_LENGTH and
                hasattr(self, key) and
                getattr(self, key) == key)

    def get(self, key):
        """Get the value of the status key."""
        return getattr(self, key)


# There is one predefined, global status object defined at module load time.
STATES = TestStatesStruct()


class StatusInfo:
    def __init__(self, when=None, state='', note=''):
        self.when = None
        self.state = state
        self.note = note


class StatusFile:
    """The wraps the status file that is used in each test, and manages the creation, reading,
    and modification of that file.
    NOTE: The status file does not perform any locking to ensure that it's created in an
    atomic manner. It does, however, limit it's writes to appends of a size such that those
    writes should be atomic.
    """

    TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
    TS_LEN = 5 + 3 + 3 + 3 + 3 + 3 + 6 + 14

    LOGGER = logging.getLogger('pav.{}'.format(__file__))

    LINE_MAX = 4096
    # Maximum length of a note. They can use every byte minux the timestamp and status sizes,
    # the spaces in-between, and the trailing newline.
    NOTE_MAX = LINE_MAX - TS_LEN - 1 - TestStatesStruct.MAX_LENGTH - 1 - 1

    def __init__(self, path):
        """Create the status file object.
        :param path: The path to the status file.
        """

        self.path = path

        self.tz = tzlocal.get_localzone()

        if not os.path.isfile(self.path):
            # Make sure we can open the file, and create it if it doesn't exist.
            self.set(STATES.CREATED, '')

    def _parse_status_line(self, line):
        line = line.decode('utf-8')

        parts = line.split(" ", 2)

        status = StatusInfo(None, '', '')

        if parts:
            try:
                status.when = datetime.datetime.strptime(parts.pop(0), self.TIME_FORMAT)
            except ValueError as err:
                self.LOGGER.warning("Bad date in log line '{}' in file '{}': {}"
                                    .format(line, self.path, err))

        if parts:
            status.state = parts.pop(0)

        if parts:
            status.note = parts.pop(0).strip()

        return status

    def history(self):
        try:
            with open(self.path, 'rb') as status_file:
                lines = status_file.readlines()
        except (OSError, IOError) as err:
            raise TestStatusError("Error opening/reading status file '{}': {}"
                                  .format(self.path, err))

        return [self._parse_status_line(line) for line in lines]

    def current(self):

        # We read a bit extra to avoid off-by-one errors
        end_read_len = self.LINE_MAX + 16

        try:
            with open(self.path, 'rb') as status_file:
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

    def set(self, status, note):
        """Set the status.
        :param status:
        :param note:
        :return:
        """

        when = self.tz.localize(datetime.datetime.now())
        when = when.strftime(self.TIME_FORMAT)

        # If we were given an invalid status, make the status invalid but add what was given to
        # the note.
        if not STATES.validate(status):
            status = STATES.INVALID
            note = '({}) {}'.format(status, note)

        # Truncate the note such that, even when encoded in utf-8, it is shorter than NOTE_MAX
        note = note.encode('utf-8')[:self.NOTE_MAX].decode('utf-8', 'ignore')

        status_line = '{} {} {}\n'.format(when, status, note).encode('utf-8')
        try:
            with open(self.path, 'ab') as status_file:
                status_file.write(status_line)
        except (IOError, OSError) as err:
            raise TestStatusError("Could not write status line '{}' to status file '{}': {}"
                                  .format(status_line, self.path, err))
