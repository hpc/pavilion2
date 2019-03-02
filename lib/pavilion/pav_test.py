from pavilion import lockfile
from pavilion import scriptcomposer
from pavilion import utils
from pavilion import wget
from pavilion.status_file import StatusFile, STATES
import bz2
import gzip
import hashlib
import json
import logging
import lzma
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import zipfile


class PavTestError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a non-recoverable way."""
    pass


class PavTestNotFoundError(RuntimeError):
    """For when we try to find an existing test, but it doesn't exist."""
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
    # We have to worry about hash collisions, but we don't need all the bytes of hash most
    # algorithms give us. The birthday attack math for 64 bits (8 bytes) of hash and 10 million
    # items yields a collision probability of just 0.00027%. Easily good enough.
    BUILD_HASH_BYTES = 8

    _BLOCK_SIZE = 4096*1024

    LOGGER = logging.getLogger('pav.{}'.format(__file__))

    def __init__(self, pav_cfg, config=None, test_id=None):
        """Create an new PavTest object.
        :param pav_cfg:
        :param config:
        :param test_id:
        """

        # Just about every method needs this
        self._pav_cfg = pav_cfg

        # Compute the actual name of test, using the subtest config parameter.
        self.name = config['name']
        if 'subtest' in config and config['subtest']:
            self.name = self.name + '.' + config['subtest']

        # Create the tests directory if it doesn't already exist.
        tests_path = os.path.join(pav_cfg.working_dir, 'tests')
        if not os.path.isdir(tests_path):
            # Try to create the tests directory if it doesn't exist. This will fail with a
            # meaningful error if it exists as something other than a directory.
            try:
                os.makedirs(tests_path, exist_ok=True)
            except OSError as err:
                # There's a race condition here; if the directory was created between when we
                # checked and created it, then this isn't an error.
                if not os.path.isdir(tests_path):
                    raise PavTestError("Could not create missing test dir at '{}': {}"
                                       .format(tests_path, err))

        self._config = config

        # Get an id for the test, if we weren't given one.
        if test_id is None:
            self.id = self._create_id(tests_path)
            self._save_config()
        else:
            self.id = test_id
            self.path = self._get_test_path(tests_path, self.id)
            if not os.path.isdir(self.path):
                raise PavTestNotFoundError("No test with id '{}' could be found.".format(self.id))

        # This will be set by the scheduler
        self._job_id = None

        # Setup the initial status file.
        self.status = StatusFile(os.path.join(self.path, 'status'))
        self.status.set(STATES.CREATED, "Test directory and status file created.")

        self.build_path = None
        self.build_name = None
        self.build_hash = None
        self.build_tmpl_path = None
        self.build_script_path = None

        build_config = self._config.get('build', {})
        if build_config:
            self.build_path = os.path.join(self.path, 'build')
            if os.path.islink(self.build_path):
                build_rp = os.path.realpath(self.build_path)
                build_fn = os.path.basename(build_rp)
                self.build_hash = build_fn.split('-')[-1]
            else:
                self.build_hash = self._create_build_hash(build_config)

            self.build_name = '{name}-{hash}'.format(name=self.name,
                                                     hash=self.build_hash[:self.BUILD_HASH_BYTES*2])
            self.build_origin = os.path.join(pav_cfg.working_dir, 'builds', self.build_name)

            self.build_tmpl_path = os.path.join(self.path, 'build.tmpl')
            self.build_script_path = os.path.join(self.path, 'build.sh')
            self._write_tmpl(self.build_tmpl_path, build_config)

        run_config = self._config.get('run', {})
        if run_config:
            self.run_tmpl_path = os.path.join(self.path, 'run.tmpl')
            self.run_script_path = os.path.join(self.path, 'run.sh')
            self._write_tmpl(self.run_tmpl_path, run_config)
        else:
            self.run_tmpl_path = None
            self.run_script_path = None

        self.status.set(STATES.CREATED, "Test directory setup complete.")

    @classmethod
    def from_id(cls, pav_cfg, test_id):
        """Load a new PavTest object based on id."""

        path = os.path.join(pav_cfg[pav_cfg.working_dir], 'tests', test_id)
        if not os.path.isdir(path):
            raise PavTestError("Test directory for test id {} does not exist at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        return PavTest(pav_cfg, config, test_id)

    def _create_id(self, tests_path):
        """Figure out what the test id of this test should be.
        :side effect: Sets self.path, creates that directory.
        :param str tests_path: The path to the general tests directory.
        :returns: The allocated test id.
        :raises PavTestError: When we can't get an id or create the directory.
        :rtype: int
        """

        with lockfile.LockFile(os.path.join(tests_path, '.lockfile'), timeout=1):
            tests = os.listdir(tests_path)
            # Only return the test directories that could be integers.
            tests = tuple(map(int, filter(str.isdigit, tests)))

            # Find the first unused id.
            test_id = 1
            while test_id in tests:
                test_id += 1

            self.path = self._get_test_path(tests_path, test_id)

            try:
                os.mkdir(self.path)
            except (IOError, OSError) as err:
                raise PavTestError("Failed to create test dir '{}': {}".format(tests_path, err))

        return test_id

    def _get_test_path(self, tests_path, test_id):
        """Calculate the path to the test directory given the overall test directory and the id."""
        return os.path.join(tests_path,
                            "{id:0{digits}d}".format(id=test_id, digits=self.TEST_ID_DIGITS))

    def _find_file(self, file):
        """Look for the given file and return a full path to it. Relative paths are searched for
        in all config directories under 'test_src'.
        :param file: The path to the file.
        :returns: The full path to the found file, or None if no such file could be found.
        """

        if os.path.isabs(file):
            if os.path.exists(file):
                return file
            else:
                return None

        for config_dir in self._pav_cfg.config_dirs:
            path = os.path.join(config_dir, 'test_src', file)
            path = os.path.realpath(path)

            if os.path.exists(path):
                return path

        return None

    @staticmethod
    def _isurl(url):
        """Determine if the given path is a url."""
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme != ''

    def _download_path(self, loc, name):
        """Get the path to where a source_download would be downloaded.
        :param str loc: The url for the download, from the config's source_location field.
        :param str name: The name of the download, from the config's source_download_name field."""

        fn = name

        if fn is None:
            url_parts = urllib.parse.urlparse(loc)
            path_parts = url_parts.path.split('/')
            if path_parts and path_parts[-1]:
                fn = path_parts[-1]
            else:
                # Use a hash of the url if we can't get a name from it.
                fn = hashlib.sha256(loc.encode()).hexdigest()

        return os.path.join(self._pav_cfg.working_dir, 'downloads', fn)

    def _update_src(self, build_config):
        """Retrieve and/or check the existence of the files needed for the build. This can include
            pulling from URL's.
        :param dict build_config: The build configuration dictionary.
        :returns: src_path, extra_files
        """

        src_loc = build_config.get('source_location')
        if src_loc is None:
            return None

        # For URL's, check if the file needs to be updated, and try to do so.
        if self._isurl(src_loc):
            src_dest = self._download_path(src_loc, build_config.get('source_download_name'))

            wget.update(self._pav_cfg, src_loc, src_dest)

            return src_dest

        src_path = self._find_file(src_loc)
        if src_path is None:
            raise PavTestError("Could not find and update src location '{}'".format(src_loc))

        if os.path.isdir(src_path):
            # For directories, update the directories mtime to match the latest mtime in
            # the entire directory.
            self._date_dir(src_path)
            return src_path

        elif os.path.isfile(src_loc):
            # For static files, we'll end up just hashing the whole thing.
            return src_path

        else:
            raise PavTestError("Source location '{}' points to something unusable."
                               .format(src_path))

    def _create_build_hash(self, build_config):
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

        # Update the hash with the contents of the build config.
        hash_obj.update(self._hash_dict(build_config))

        src_path = self._update_src(build_config)

        if src_path is not None:
            if os.path.isfile(src_path):
                hash_obj.update(self._hash_file(src_path))
            elif os.path.isdir(src_path):
                hash_obj.update(self._hash_dir(src_path))
            else:
                raise PavTestError("Invalid src location {}.".format(src_path))

        for path in build_config.get('extra_files', []):
            full_path = self._find_file(path)

            if full_path is None:
                raise PavTestError("Could not find extra file '{}'".format(path))
            elif os.path.isfile(full_path):
                hash_obj.update(self._hash_file(full_path))
            elif os.path.isdir(full_path):
                self._date_dir(full_path)

                hash_obj.update(self._hash_dir(full_path))
            else:
                raise PavTestError("Extra file '{}' must be a regular file or directory.")

        hash_obj.update(build_config.get('specificity', '').encode('utf-8'))

        return hash_obj.hexdigest()[:self.BUILD_HASH_BYTES*2]

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = os.path.join(self.path, 'config')

        try:
            with open(config_path, 'w') as json_file:
                json.dump(self._config, json_file)
        except (OSError, IOError) as err:
            raise PavTestError("Could not save PavTest ({}) config at {}: {}"
                               .format(self.name, self.path, err))
        except TypeError as err:
            raise PavTestError("Invalid type in config for ({}): {}"
                               .format(self.name, err))

    def build(self):
        """Perform the build if needed, do a soft-link copy of the build directory into our
        test directory, and note that we've used the given build. Returns True if these
        steps completed successfully."""

        # Make sure another test doesn't try to do the build at the same time.
        # Note cleanup of failed builds HAS to occur under this lock to avoid a race condition,
        #   even though it would be way simpler to do it in .build()
        lock_path = '{}.lock'.format(self.build_origin)
        with lockfile.LockFile(lock_path, group=self._pav_cfg.shared_group):
            build_dir = self.build_origin + '.tmp'

            # Attempt to perform the actual build
            if not self._build(build_dir):
                # The build failed. The reason should already be set in the status file.
                self._clean_failed_build(build_dir)
                return False

            # Rename the build to it's final location.
            os.rename(build_dir, self.build_origin)

        # Perform a symlink copy of the original build directory into our test directory.
        try:
            shutil.copytree(self.build_origin,
                            self.build_path,
                            symlinks=True,
                            copy_function=utils.symlink_copy)
        except OSError as err:
            self.status.set(STATES.BUILD_FAILED,
                            "Could not perform the build directory copy: {}".format(err))

        # Touch the original build directory, so that we know it was used recently.
        try:
            now = time.time()
            os.utime(self.build_origin, (now, now))
        except OSError as err:
            self.LOGGER.warning("Could not update timestamp on build directory '{}': {}"
                                .format(self.build_origin, err))

        return True

    # A process should produce some output at least once every this many seconds.
    BUILD_SILENT_TIMEOUT = 30

    def _build(self, build_dir):
        """Perform the build. This assumes the build template is resolved and that there actually
        is a build to perform.
        :returns: True or False, depending on whether the build appears to have been successful.
        """

        if os.path.exists(self.build_origin):
            # Another test built it before this run could. We should be good to go.
            return True

        try:
            self._setup_build_dir(build_dir)
        except PavTestError as err:
            self.status.set(STATES.BUILD_FAILED,
                            "Error setting up build directory '{}': {}"
                            .format(build_dir, err))
            return False

        build_log_path = os.path.join(build_dir, 'pav_build_log')

        try:
            with open(build_log_path, 'w') as build_log:
                proc = subprocess.Popen([self.build_script_path],
                                        cwd=build_dir,
                                        stdout=build_log,
                                        stderr=build_log)

                timeout = self.BUILD_SILENT_TIMEOUT
                result = None
                while result is None:
                    try:
                        result = proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        stat = os.stat(build_log_path)
                        quiet_time = time.time() - stat.st_mtime
                        # Has the output file changed recently?
                        if self.BUILD_SILENT_TIMEOUT < quiet_time:
                            # Give up on the build, and call it a failure.
                            proc.kill()
                            self.status.set(STATES.BUILD_FAILED,
                                            "Build timed out after {} seconds."
                                            .format(self.BUILD_SILENT_TIMEOUT))
                            return False
                        else:
                            # Only wait a max of BUILD_SILENT_TIMEOUT next 'wait'
                            timeout = self.BUILD_SILENT_TIMEOUT - quiet_time
        except subprocess.CalledProcessError as err:
            self.status.set(STATES.BUILD_FAILED,
                            "Error running build process: {}".format(err))
            return False

        except (IOError, OSError) as err:
            self.status.set(STATES.BUILD_FAILED,
                            "Error that's probably related to writing the build output: {}"
                            .format(err))
            return False

        if result != 0:
            self.status.set(STATES.BUILD_FAILED,
                            "Build returned a non-zero result.")
            return False
        else:

            self.status.set(STATES.BUILD_DONE, "Build completed successfully.")
            return True

    def _setup_build_dir(self, build_path):
        """
        TODO: Write this
        :param build_path:
        :return:
        """

        build_config = self._config.get('build', {})

        src_loc = build_config.get('source_location')
        if src_loc is None:
            src_path = None
        elif self._isurl(src_loc):
            download_name = build_config.get('source_download_name')
            src_path = self._download_path(src_loc, download_name)
        else:
            src_path = self._find_file(src_loc)
            if src_path is None:
                raise PavTestError("Could not find source file '{}'".format(src_path))

        if os.path.isdir(src_path):
            # Recursively copy the src directory to the build directory.
            shutil.copytree(src_path, build_path, symlinks=True)

        elif os.path.isfile(src_path):
            # Handle decompression of a stream compressed file. The interfaces for the libs are
            # all the same; we just have to choose the right one to use. Zips are handled as an
            # archive, below.
            category, subtype = utils.get_mime_type(src_path)
            comp_lib = None
            if category == 'application' and subtype in ('gzip', 'x-bzip2', 'x-xz', 'x-tar'):

                if tarfile.is_tarfile(src_path):
                    try:
                        with tarfile.open(src_path, 'r') as tar:
                            # Filter out all but the top level items.
                            top_level = [m for m in tar.members if '/' not in m.name]
                            # If the file contains only a single directory, make that directory the
                            # build directory. This should be the default in most cases.
                            if len(top_level) == 1 and top_level[0].isdir():
                                tmpdir = '{}.tmp'.format(build_path)
                                os.mkdir(tmpdir)
                                tar.extractall(tmpdir)
                                os.rename(os.path.join(tmpdir, top_level[0].name), build_path)
                                os.rmdir(tmpdir)
                            else:
                                # Otherwise, the build path will contain the extracted contents
                                # of the archive.
                                os.mkdir(build_path)
                                tar.extractall(build_path)
                    except (OSError, IOError, tarfile.CompressionError, tarfile.TarError) as err:
                        raise PavTestError("Could not extract tarfile '{}' into '{}': {}"
                                           .format(src_path, build_path, err))

                else:
                    # If it's a compressed file but isn't a tar, extract the file into the build
                    # directory.
                    # All the python compression libraries have the same basic interface, so we can
                    # just dynamically switch between modules.
                    if subtype == 'gzip':
                        comp_lib = gzip
                    elif subtype == 'x-bzip2':
                        comp_lib = bz2
                    elif subtype == 'x-xz':
                        comp_lib = lzma
                    elif subtype == 'x-tar':
                        raise PavTestError("Test src file '{}' is a bad tar file."
                                           .format(src_path))

                decomp_fn = os.path.join(build_path, src_path.rsplit('.', 2)[0])
                os.mkdir(build_path)

                try:
                    with comp_lib.open(src_path) as infile, open(decomp_fn, 'wb') as outfile:
                        shutil.copyfileobj(infile, outfile)
                except (OSError, IOError, lzma.LZMAError) as err:
                    raise PavTestError("Error decompressing gzip compressed file "
                                       "'{}' into '{}': {}"
                                       .format(src_path, decomp_fn, err))

            elif category == 'application' and subtype == 'zip':
                try:
                    # Extract the zipfile, under the same conditions as above with tarfiles.
                    with zipfile.ZipFile(src_path) as zipped:
                        top_level = [m for m in zipped.filelist if '/' not in m.filename[:-1]]
                        if len(top_level) == 1 and top_level[0].is_dir():
                            tmpdir = '{}.tmp'.format(build_path)
                            os.mkdir(tmpdir)
                            zipped.extractall(tmpdir)
                            os.rename(os.path.join(tmpdir, top_level[0].name), build_path)
                            os.rmdir(tmpdir)
                        else:
                            os.mkdir(build_path)
                            zipped.extractall(build_path)

                except (OSError, IOError, zipfile.BadZipFile) as err:
                    raise PavTestError("Could not extract zipfile '{}' into destination '{}': {}"
                                       .format(src_path, build_path, err))

            else:
                # Finally, simply copy any other types of files into the build directory.
                dest = os.path.join(build_path, os.path.basename(src_path))
                try:
                    os.mkdir(build_path)
                    shutil.copyfile(src_path, dest)
                except OSError as err:
                    raise PavTestError("Could not copy test src '{}' to '{}': {}"
                                       .format(src_path, dest, err))

        # Now we just need to copy over all of the extra files.
        for extra in build_config['extra_files']:
            path = self._find_file(extra)
            dest = os.path.join(build_path, os.path.basename(path))
            try:
                shutil.copyfile(path, dest)
            except OSError as err:
                raise PavTestError("Could not copy extra file '{}' to dest '{}': {}"
                                   .format(path, dest, err))

        return build_path

    def _clean_failed_build(self, build_dir):
        """Clean up a failed build at 'build_dir'."""

        def handle_error(_, path, exc_info):
            self.LOGGER.error("Error removing temporary build directory '{}': {}"
                              .format(path, exc_info))

        shutil.rmtree(path=build_dir, onerror=handle_error)

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

    @property
    def job_id(self):

        path = os.path.join(self.path, 'jobid')

        if self._job_id is not None:
            return self._job_id

        try:
            with os.path.isfile(path) as job_id_file:
                self._job_id = job_id_file.read()
        except FileNotFoundError:
            return None
        except (OSError, IOError) as err:
            self.LOGGER.error("Could not read jobid file '{}': {}"
                              .format(path, err))
            return None

        return self._job_id

    @job_id.setter
    def job_id(self, job_id):

        path = os.path.join(self.path, 'jobid')

        try:
            with open(path, 'w') as job_id_file:
                job_id_file.write(job_id)
        except (IOError, OSError) as err:
            self.LOGGER.error("Could not write jobid file '{}': {}"
                              .format(path, err))

        self._job_id = job_id

    def _hash_dict(self, mapping):
        """Create a hash from the keys and items in 'mapping'. Keys are processed in order. Can
        handle lists and other dictionaries as values.
        :param dict mapping: The dictionary to hash.
        """

        hash_obj = hashlib.sha256()

        for key in sorted(mapping.keys()):
            hash_obj.update(str(key).encode('utf-8'))

            val = mapping[key]

            if isinstance(val, str):
                hash_obj.update(val.encode('utf-8'))
            elif isinstance(val, list):
                for item in val:
                    hash_obj.update(item.encode('utf-8'))
            elif isinstance(val, dict):
                hash_obj.update(self._hash_dict(val))

        return hash_obj.digest()

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

        return hash_obj.digest()

    @staticmethod
    def _hash_dir(path):
        """Instead of hashing the files within a directory, we just create a hash based on it's
        name and mtime, assuming we've run _date_dir on it before hand.
        Note: This doesn't actually produce a hash, just an arbitrary string.
        :param str path: The path to the directory.
        :returns: The 'hash'
        """

        stat = os.stat(path)
        return '{} {:0.5f}'.format(path, stat.st_mtime)

    @staticmethod
    def _date_dir(base_path):
        """Update the mtime of the given directory or path to the the latest mtime contained
        within.
        :param str base_path: The root of the path to evaluate.
        """

        src_stat = os.stat(base_path)
        latest = src_stat.st_mtime

        paths = utils.flat_walk(base_path)
        for path in paths:
            stat = os.stat(path)
            if stat.st_mtime > latest:
                latest = stat.st_mtime

        if src_stat.st_mtime != latest:
            os.utime(base_path, (src_stat.st_atime, latest))

    def _write_tmpl(self, path, tmpl_config):
        """Write a build or run template. The formats for each are identical.
        :param str path: Path to the template file to write.
        :param dict tmpl_config: Configuration dictionary for the template file.
        :return:
        """

        script = scriptcomposer.ScriptComposer(
            details=scriptcomposer.ScriptDetails(
                path=path,
                group=self._pav_cfg.shared_group,
            ))

        pav_lib_bash = os.path.join(self._pav_cfg.pav_root, 'bin', 'pav-lib.bash')

        script.add_comment('The following is added to every test build and run script.')
        script.env_change({'TEST_ID': '{}'.format(self.id)})
        script.add_command('source {}'.format(pav_lib_bash))

        for module in tmpl_config.get('modules', []):
            script.module_change(module)

        script.env_change(tmpl_config.get('env', {}))

        for line in tmpl_config.get('cmds', []):
            for split_line in line.split('\n'):
                script.add_command(split_line)

        script.write()

    TMPL_ESCAPE_RE = re.compile(r'\[\x1E((?:sched|sys)\.\w+(?:\.\w+)?)\x1E\]')

    def resolve_template(self, var_man):
        """Resolve the test deferred variables using the appropriate escape sequence."""
        try:
            with open(self.run_tmpl_path, 'r') as run_tmpl, \
                 open(self.run_script_path, 'w') as run_script:

                for line in run_tmpl.readlines():
                    outline = []
                    char_val = 0
                    match = self.TMPL_ESCAPE_RE.search(line, char_val)

                    # Walk through the line, and lookup the real value of each matched
                    # deferred variable.
                    while match is not None:
                        outline.append(line[char_val:match.start()])
                        char_val = match.end()
                        var_name = match.groups()[0]
                        outline.append(var_man.get(var_name))
                        match = self.TMPL_ESCAPE_RE.search(line, char_val)

                    # Don't forget the remainder of the line.
                    outline.append(line[char_val:])

                    run_script.write(''.join(outline))

        except(IOError, OSError) as err:
            raise PavTestError("Failed processing run template file '{}' into run script'{}': {}"
                               .format(self.run_tmpl_path, self.run_script_path, err))
