
import hashlib
import os
import json
import urllib.parse
from pavilion import schedulers
from pavilion import lockfile
from pavilion import wget
from pavilion import utils


class PavTestError(RuntimeError):
    pass


# Keep track of files we've already hashed and updated before.
__HASHED_FILES = {}

class PavTest:
    """The central pavilion test object. Handle saving, monitoring and running tests (via a
    scheduler).

    :cvar TEST_ID_DIGITS: How many digits should be in thte test folder names.
    :cvar _BLOCK_SIZE: Blocksize for hashing files.
    """

    TEST_ID_DIGITS = 6
    _BLOCK_SIZE = 4096*1024

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

    @staticmethod
    def _find_file(pav_cfg, file):
        """Look for the given file and return a full path to it. Relative paths are searched for
        in all config directories under 'test_src'.
        :param pav_cfg: The pavilion config object>
        :param file: The path to the file.
        :returns: The full path to the found file, or None if no such file could be found.
        """

        if os.path.isabs(file):
            if os.path.exists(file):
                return file
            else:
                return None

        for config_dir in pav_cfg.config_dirs:
            path = os.path.join(config_dir, 'test_src', file)
            path = os.path.realpath(path)

            if os.path.exists(path):
                return path

        return None

    def _update_src(self, pav_cfg, build_config):
        """Retrieve and/or check the existence of the files needed for the build. This can include
            pulling from URL's.
        :param pav_cfg: The pavilion configuration object.
        :param dict build_config: The build configuration dictionary.
        :returns: src_path, extra_files
        """

        src_loc = build_config.get('source_location')
        if src_loc is None:
            return None

        # For URL's, check if the file needs to be updated, and try to do so.
        if (src_loc.startswith('http://') or
                src_loc.startswith('https://') or
                src_loc.startswith('ftp://')):

            fn = build_config.get('source_download_name')

            if fn is None:
                url_parts = urllib.parse.urlparse(src_loc)
                path_parts = url_parts.path.split('/')
                if path_parts and path_parts[-1]:
                    fn = path_parts[-1]
                else:
                    # Use a hash of the url if we can't get a name from it.
                    fn = hashlib.sha256(src_loc.encode()).hexdigest()

            fn = os.path.join(pav_cfg.working_dir, 'downloads', fn)

            wget.update(pav_cfg, src_loc, fn)

            return fn

        src_path = self._find_file(pav_cfg, src_loc)
        if src_path is None:
            raise PavTestError("Could not find and update src location '{}'".format(src_loc))

        if os.path.isdir(src_path):
            # For directories, update the directories mtime to match the latest mtime in
            # the entire directory.
            self._date_dir()
            return src_path

        elif os.path.isfile(src_loc):
            # For static files, we'll end up just hashing the whole thing.
            return src_path

        else:
            raise PavTestError("Source location '{}' points to something unusable."
                               .format(src_path))

    def _create_build_hash(self, pav_cfg, config):
        """Turn the build config, and everything the build needs, into hash.  This includes the
        build config itself, the source tarball, and all extra files. Additionally,
        system variables may be included in the hash if specified via the pavilion config."""

        # The hash order is:
        #  - The build config (sorted by key)
        #  - The src archive.
        #    - For directories, the mtime (updated to the time of the most recently updated file),
        #      is hashed instead.
        #  - All of the build's 'extra_files'
        #  - Each of the pav_cfg.build_hash_vars

        hash_obj = hashlib.sha256()

        build_config = config.get('build', {})

        # Update the hash with the contents of the build config.
        hash_obj.update(self._hash_dict(build_config))

        src_path = self._update_src(pav_cfg, build_config)

        if src_path is not None:
            if os.path.isfile(src_path):
                hash_obj.update(self._hash_file(src_path))
            elif os.path.isdir(src_path):
                hash_obj.update(self._hash_dir(src_path))
            else:
                raise PavTestError("Invalid src location {}.".format(src_path))

        for path in build_config.get('extra_files'):
            full_path = self._find_file(pav_cfg, path)

            if full_path is None:
                raise PavTestError("Could not find extra file '{}'".format(path))
            elif os.path.isfile(full_path):
                hash_obj.update(self._hash_file(full_path))
            elif os.path.isdir(full_path):
                self._date_dir(full_path)

                hash_obj.update(self._hash_dir(full_path))
            else:
                raise PavTestError("Extra file '{}' must be a regular file or directory.")

        hash_obj.update(build_config.get('specificity', ''))

        return hash_obj.hexdigest()

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

    def _hash_dict(self, mapping):
        """Create a hash from the keys and items in 'mapping'. Keys are processed in order. Can
        handle lists and other dictionaries as values.
        :param hashlib.sha1 hash_obj: The hashing object to update (doesn't necessarily have to be sha1).
        :param dict mapping: The dictionary to hash.
        """

        hash_obj = hashlib.sha256()

        for key in sorted(mapping.keys()):
            hash_obj.update(str(key))

            val = mapping[key]

            if isinstance(val, str):
                hash_obj.update(val)
            elif isinstance(val, list):
                for item in val:
                    hash_obj.update(item)
            elif isinstance(val, dict):
                hash_obj.update(self._hash_dict(val))

        return hash_obj.hexdigest()

    def _hash_file(self, path):
        """Hash the given file (which is assumed to exist).
        :param str path: Path to the file to hash.
        """

        hash_obj = hashlib.sha256()

        with open(path, 'rb') as file:
            chunk = file.read(self._BLOCK_SIZE)
            while chunk:
                hash_obj.update(chunk)
                chunk = file.read(self._BLOCK_SIZE)

        return hash_obj.hexdigest()

    def _hash_dir(self, path):
        """Instead of hashing the files within a directory, we just create a hash based on it's
        name and mtime, assuming we've run _date_dir on it before hand.
        Note: This doesn't actually produce a hash, just an arbitrary string.
        :param str path: The path to the directory.
        :returns: The 'hash'
        """

        stat = os.stat(path)
        return '{} {:0.5f}'.format(path, stat.st_mtime)

    def _date_dir(self, base_path):
        """Update the mtime of the given directory or path to the the latest mtime contained
        within.
        :param str base_path: The root of the path to evaluate.
        """

        src_stat = os.stat(base_path)
        latest = src_stat.st_mtime

        paths = utils.flatwalk(base_path)
        for path in paths:
            stat = os.stat(path)
            if stat.st_mtime > latest:
                latest = stat.st_mtime

        if src_stat.st_mtime != latest:
            os.utime(base_path, (src_stat.st_atime, latest))
