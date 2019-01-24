import os


class TestStatusError(RuntimeError):
    pass


class TestStatusStruct:
    """A class containing the test status constants.
    Rules:
      - The value should be a string of the constant name.
      - The constants have a max length of 15 characters.
      - The constants should be in all caps.
      - The constants must be a valid python identifier that starts with a letter.
    """
    UNKNOWN     = 'UNKNOWN'
    BUILDING    = 'BUILDING'
    RUNNING     = 'RUNNING'

    _MAX_LENGTH = 15

    def __init__(self):
        """Validate all of the constants."""

        for key in self.__class__.__dict__.keys():
            if key.startswith('_'):
                continue

            if not (key[0].isalpha() and
                    key.isupper() and
                    key.isidentifier() and
                    len(key) <= self._MAX_LENGTH and
                    getattr(self, key) == key):
                raise RuntimeError("Invalid TestStatus constant '{}'.".format(key))


# There is one predefined, global status object defined at module load time.
STATUS = TestStatusStruct()


class TestStatus:
    def __init__(self, path):
        """Create the status file object.
        :param path: The path to the status file.
        """

        self.path = path

        # Make sure we can open the file, and that it's permissions are set correctly.
        try:
            open(path, 'ab')
            os.close()


        except:
