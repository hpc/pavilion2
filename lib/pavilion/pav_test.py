import os
import json
from pavilion import schedulers
from pavilion import lockfile


class PavTestError(RuntimeError):
    pass


class PavTest:
    TEST_ID_DIGITS = 6

    def __init__(self, pav_cfg, config, id=None):
        """Create an new PavTest object.
        :param pav_cfg:
        :param config:
        :param id:
        """

        self.name = config['name']
        if 'subtest' in config and config['subtest']:
            self.name = self.name + '.' + config['subtest']

        tests_path = os.path.join(pav_cfg.working_dir, 'tests')
        if not os.path.isdir(tests_path):
            # Try to create the tests directory if it doesn't exist. This will fail with a
            # meaningful error if it exists as something other than a directory.
            try:
                os.mkdir(tests_path)
            except OSError as err:
                # There's a race condition here; if the directory was created between when we
                # checked and created it, then this isn't an error.
                if not os.path.isdir(tests_path):
                    raise PavTestError("Could not create missing test dir at '{}': {}"
                                       .format(tests_path, err))

        if id is None:
            self.id = self._create_id(pav_cfg, tests_path)
            self._save_config()
        else:
            self.id = str(id)

        self.path = os.path.join(tests_path, self.id)

        self._config = config
        self._scheduler = self._get_scheduler(pav_cfg, config)

        self.build_hash = self._get_build_hash()
        self.build_path = os.path.join(self.path, 'build')

    def _create_id(self, pav_cfg, tests_path):
        """Figure out what the test id of this test should be."""

        with lockfile.LockFile(tests_path, pav_cfg.shared_group, 1):
            tests = os.listdir(tests_path)
            # Only return the test directories that could be integers.
            tests = tuple(map(int, filter(str.isdigit, tests)))

            # Find the first unused id.
            id = 1
            while id in tests:
                id += 1

            test_path = os.path.join(tests_path,
                                     "{id:0{digits}d}".format(id=id, digits=self.TEST_ID_DIGITS))

            try:
                os.mkdir(tests_path)
            except (IOError, OSError) as err:
                raise PavTestError("Failed to create test dir '{}': {}".format(test_path, err))

        return str(id)

    def _get_build_components(self, pav_cfg, config):
        """Retrieve all the files needed for the build. This can include pulling from URL's.
        :returns: A dictionary of name->path
        """

        files = []

        if 'build' not in config:
            return {}

        build_config = config['build']

        if build_config.get('source_location'):
            files.append(build_config.get('source_location'))

        files.extend(build_config.get('extra_files', []))

        for file in files:
            if (file.startswith('http://') or
                    file.startswith('https://') or
                    file.startswith('ftp://')):










    def _get_build_hash(self, config, files):
        """Turn the build config, and everything the build needs, into hash.  This includes the
        build config string itself, the source tarball (or a tarball of the repo), """

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = os.path.join(self.path, 'config')

        try:
            with open(config_path, 'w') as file:
                json.dump(file, self._config)
        except (OSError, IOError) as err:
            raise PavTestError("Could not save PavTest ({}) config at {}: {}"
                               .format(self.name, self.path, err))
        except TypeError as err:
            raise PavTestError("Invalid type in config for ({}): {}"
                               .format(self.name, err))

    @classmethod
    def _load_config(cls, test_path):
        config_path = os.path.join(test_path, 'config')

        if not os.path.isfile(config_path):
            raise PavTestError("Could not find config file for test at {}.".format(test_path))

        try:
            with open(config_path, 'r') as config_file:
                return json.load(config_file)
        except TypeError as err:
            raise PavTestError("Bad config values for config '{}': {}".format(config_path, err))
        except (IOError, OSError) as err:
            raise PavTestError("Error reading config file '{}': {}".format(config_path, err))

    @classmethod
    def from_id(cls, pav_cfg, id):
        """Load a new PavTest object based on id."""

        path = os.path.join(pav_cfg[pav_cfg.working_dir], 'tests', id)
        if not os.path.isdir(path):
            raise PavTestError("Test directory for test id {} does not exist at '{}' as expected."
                               .format(id, path))

        config = cls._load_config(path)

        return PavTest(pav_cfg, config, id)

    @classmethod
    def _get_scheduler(cls, pav_cfg, config):
        sched_name = config.get('scheduler')
        return schedulers.get(sched_name)(pav_cfg,
                                          config.get(sched_name),
                                          config.get(sched_name + '_limits'))

    @property
    def is_built(self):
        """Whether the build for this test exists.
        :returns: True if the build exists (or the test doesn't have a build), False otherwise.
        """

        if 'build' not in self._config:
            return True

        if os.path.islink(self.build_path):
            # The file is expected to be a softlink, but we need to make sure the path it points
            # to exists. The most robust way is to check it with stat, which will throw an exception
            # if it doesn't exist (an OSError in certain weird cases like symlink loops).
            try:
                os.stat(self.build_path)
            except (OSError, FileNotFoundError):
                return False

            return True
