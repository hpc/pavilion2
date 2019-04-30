from . import variables
from pathlib import Path
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
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.parse
import zipfile


class PavTestError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""
    pass


class PavTestNotFoundError(RuntimeError):
    """For when we try to find an existing test, but it doesn't exist."""
    pass


# Keep track of files we've already hashed and updated before.
__HASHED_FILES = {}


class PavTest:
    """The central pavilion test object. Handle saving, monitoring and running
    tests.

    :cvar TEST_ID_DIGITS: How many digits should be in the test folder names.
    :cvar _BLOCK_SIZE: Blocksize for hashing files.
    """

    # By default we support up to 10 million tests.
    TEST_ID_DIGITS = 7

    # We have to worry about hash collisions, but we don't need all the bytes
    # of hash most algorithms give us. The birthday attack math for 64 bits (
    # 8 bytes) of hash and 10 million items yields a collision probability of
    # just 0.00027%. Easily good enough.
    BUILD_HASH_BYTES = 8

    _BLOCK_SIZE = 4096*1024

    LOGGER = logging.getLogger('pav.PavTest')

    def __init__(self, pav_cfg, config, test_id=None):
        """Create an new PavTest object. If loading an existing test instance,
        use the PavTest.from_id method.
        :param pav_cfg: The pavilion configuration.
        :param config: The test configuration dictionary.
        :param test_id: The test id (for an existing test).
        """

        # Just about every method needs this
        self._pav_cfg = pav_cfg

        # Compute the actual name of test, using the subtest config parameter.
        self.name = config['name']
        if 'subtest' in config and config['subtest']:
            self.name = self.name + '.' + config['subtest']

        # Create the tests directory if it doesn't already exist.
        tests_path = pav_cfg.working_dir/'tests'

        self.config = config

        # Get an id for the test, if we weren't given one.
        if test_id is None:
            self.id, self.path = utils.create_id_dir(tests_path)
            self._save_config()
        else:
            self.id = test_id
            self.path = utils.make_id_path(tests_path, self.id)
            if not self.path.is_dir():
                raise PavTestNotFoundError(
                    "No test with id '{}' could be found.".format(self.id))

        # Set a logger more specific to this test.
        self.LOGGER = logging.getLogger('pav.PavTest.{}'.format(self.id))

        # This will be set by the scheduler
        self._job_id = None

        # Setup the initial status file.
        self.status = StatusFile(self.path/'status')
        self.status.set(STATES.CREATED,
                        "Test directory and status file created.")

        self.build_path = None
        self.build_name = None
        self.build_hash = None
        self.build_script_path = None

        build_config = self.config.get('build', {})
        if build_config:
            self.build_path = self.path/'build'
            if self.build_path.is_symlink():
                build_rp = self.build_path.resolve()
                self.build_hash = build_rp.name
            else:
                self.build_hash = self._create_build_hash(build_config)

            short_hash = self.build_hash[:self.BUILD_HASH_BYTES*2]
            self.build_name = '{hash}'.format(hash=short_hash)
            self.build_origin = pav_cfg.working_dir/'builds'/self.build_name

            self.build_script_path = self.path/'build.sh'
            self._write_script(self.build_script_path, build_config)

        run_config = self.config.get('run', {})
        if run_config:
            self.run_tmpl_path = self.path/'run.tmpl'
            self.run_script_path = self.path/'run.sh'
            self._write_script(self.run_tmpl_path, run_config)
        else:
            self.run_tmpl_path = None
            self.run_script_path = None

        self.status.set(STATES.CREATED, "Test directory setup complete.")

    @classmethod
    def from_id(cls, pav_cfg, test_id):
        """Load a new PavTest object based on id."""

        path = utils.make_id_path(pav_cfg.working_dir/'tests', test_id)

        if not path.is_dir():
            raise PavTestError("Test directory for test id {} does not exist "
                               "at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        return PavTest(pav_cfg, config, test_id)

    def run_cmd(self):
        """Construct a shell command that would cause pavilion to run this
        test."""

        pav_path = self._pav_cfg.pav_root/'bin'/'pav'

        return '{} run {}'.format(pav_path, self.id)

    def _save_config(self):
        """Save the configuration for this test to the test config file."""

        config_path = self.path/'config'

        try:
            with config_path.open('w') as json_file:
                json.dump(self.config, json_file)
        except (OSError, IOError) as err:
            raise PavTestError("Could not save PavTest ({}) config at {}: {}"
                               .format(self.name, self.path, err))
        except TypeError as err:
            raise PavTestError("Invalid type in config for ({}): {}"
                               .format(self.name, err))

    @classmethod
    def _load_config(cls, test_path):
        config_path = test_path/'config'

        if not config_path.is_file():
            raise PavTestError("Could not find config file for test at {}."
                               .format(test_path))

        try:
            with config_path.open('r') as config_file:
                return json.load(config_file)
        except TypeError as err:
            raise PavTestError("Bad config values for config '{}': {}"
                               .format(config_path, err))
        except (IOError, OSError) as err:
            raise PavTestError("Error reading config file '{}': {}"
                               .format(config_path, err))

    def _find_file(self, file, sub_dir=None):
        """Look for the given file and return a full path to it. Relative paths
        are searched for in all config directories under 'test_src'.
        :param Path file: The path to the file.
        :param sub_dir: The subdirectory in each config directory in which to
            search.
        :returns: The full path to the found file, or None if no such file
            could be found.
        """

        if file.is_absolute():
            if file.exists():
                return file
            else:
                return None

        # Assemble a potential location from each config dir.
        for config_dir in self._pav_cfg.config_dirs:
            path = config_dir
            if sub_dir is not None:
                path = path/sub_dir
            path = path/file

            if path.exists():
                return path

        return None

    @staticmethod
    def _isurl(url):
        """Determine if the given path is a url."""
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme != ''

    def _download_path(self, loc, name):
        """Get the path to where a source_download would be downloaded.
        :param str loc: The url for the download, from the config's
            source_location field.
        :param str name: The name of the download, from the config's
            source_download_name field."""

        fn = name

        if fn is None:
            url_parts = urllib.parse.urlparse(loc)
            path_parts = url_parts.path.split('/')
            if path_parts and path_parts[-1]:
                fn = path_parts[-1]
            else:
                # Use a hash of the url if we can't get a name from it.
                fn = hashlib.sha256(loc.encode()).hexdigest()

        return self._pav_cfg.working_dir/'downloads'/fn

    def _update_src(self, build_config):
        """Retrieve and/or check the existence of the files needed for the
            build. This can include pulling from URL's.
        :param dict build_config: The build configuration dictionary.
        :returns: src_path, extra_files
        """

        src_loc = build_config.get('source_location')
        if src_loc is None:
            return None

        # For URL's, check if the file needs to be updated, and try to do so.
        if self._isurl(src_loc):
            dwn_name = build_config.get('source_download_name')
            src_dest = self._download_path(src_loc, dwn_name)

            wget.update(self._pav_cfg, src_loc, src_dest)

            return src_dest

        src_path = self._find_file(Path(src_loc), 'test_src')
        if src_path is None:
            raise PavTestError("Could not find and update src location '{}'"
                               .format(src_loc))

        if src_path.is_dir():
            # For directories, update the directories mtime to match the
            # latest mtime in the entire directory.
            self._date_dir(src_path)
            return src_path

        elif src_path.is_file():
            # For static files, we'll end up just hashing the whole thing.
            return src_path

        else:
            raise PavTestError("Source location '{}' points to something "
                               "unusable.".format(src_path))

    def _create_build_hash(self, build_config):
        """Turn the build config, and everything the build needs, into hash.
        This includes the build config itself, the source tarball, and all
        extra files. Additionally, system variables may be included in the
        hash if specified via the pavilion config."""

        # The hash order is:
        #  - The build config (sorted by key)
        #  - The src archive.
        #    - For directories, the mtime (updated to the time of the most
        #      recently updated file) is hashed instead.
        #  - All of the build's 'extra_files'
        #  - Each of the pav_cfg.build_hash_vars

        hash_obj = hashlib.sha256()

        # Update the hash with the contents of the build config.
        hash_obj.update(self._hash_dict(build_config))

        src_path = self._update_src(build_config)

        if src_path is not None:
            if src_path.is_file():
                hash_obj.update(self._hash_file(src_path))
            elif src_path.is_dir():
                hash_obj.update(self._hash_dir(src_path))
            else:
                raise PavTestError("Invalid src location {}.".format(src_path))

        for extra_file in build_config.get('extra_files', []):
            extra_file = Path(extra_file)
            full_path = self._find_file(extra_file, 'test_src')

            if full_path is None:
                raise PavTestError("Could not find extra file '{}'"
                                   .format(extra_file))
            elif full_path.is_file():
                hash_obj.update(self._hash_file(full_path))
            elif full_path.is_dir():
                self._date_dir(full_path)

                hash_obj.update(self._hash_dir(full_path))
            else:
                raise PavTestError("Extra file '{}' must be a regular "
                                   "file or directory.".format(extra_file))

        hash_obj.update(build_config.get('specificity', '').encode('utf-8'))

        return hash_obj.hexdigest()[:self.BUILD_HASH_BYTES*2]

    def build(self):
        """Perform the build if needed, do a soft-link copy of the build
        directory into our test directory, and note that we've used the given
        build. Returns True if these steps completed successfully.
        """

        # Only try to do the build if it doesn't already exist.
        if not self.build_origin.exists():
            # Make sure another test doesn't try to do the build at
            # the same time.
            # Note cleanup of failed builds HAS to occur under this lock to
            # avoid a race condition, even though it would be way simpler to
            # do it in .build()
            lock_path = self.build_origin.with_suffix('.lock')
            with lockfile.LockFile(lock_path, group=self._pav_cfg.shared_group):
                # Make sure the build wasn't created while we waited for
                # the lock.
                if not self.build_origin.exists():
                    build_dir = self.build_origin.with_suffix('.tmp')

                    try:
                        # Attempt to perform the actual build, this shouldn't
                        # raise an exception unless
                        # something goes terribly wrong.
                        if not self._build(build_dir):
                            return False

                        # Rename the build to it's final location.
                        build_dir.rename(self.build_origin)
                    finally:
                        # The build failed. The reason should already be set
                        # in the status file.
                        def handle_error(_, path, exc_info):
                            self.LOGGER.error(
                                "Error removing temporary build "
                                "directory '{}': {}"
                                .format(path, exc_info))

                        if build_dir.exists():
                            # Cleanup the temporary build tree.
                            shutil.rmtree(path=str(build_dir),
                                          onerror=handle_error)

        # Perform a symlink copy of the original build directory into our test
        # directory.
        try:
            shutil.copytree(str(self.build_origin),
                            str(self.build_path),
                            symlinks=True,
                            copy_function=utils.symlink_copy)
        except OSError as err:
            msg = "Could not perform the build directory copy: {}".format(err)
            self.status.set(STATES.BUILD_ERROR, msg)
            self.LOGGER.error(msg)
            return False

        # Touch the original build directory, so that we know it was used
        # recently.
        try:
            now = time.time()
            os.utime(str(self.build_origin), (now, now))
        except OSError as err:
            self.LOGGER.warning("Could not update timestamp on build directory "
                                "'{}': {}"
                                .format(self.build_origin, err))

        return True

    # A process should produce some output at least once every this many
    # seconds.
    BUILD_SILENT_TIMEOUT = 30

    def _build(self, build_dir):
        """Perform the build. This assumes there actually is a build to perform.
        :param Path build_dir: The directory in which to perform the build.
        :returns: True or False, depending on whether the build appears to have
            been successful.
        """
        try:
            self._setup_build_dir(build_dir)
        except PavTestError as err:
            self.status.set(STATES.BUILD_ERROR,
                            "Error setting up build directory '{}': {}"
                            .format(build_dir, err))
            return False

        build_log_path = build_dir/'pav_build_log'

        try:
            with build_log_path.open('w') as build_log:
                proc = subprocess.Popen([str(self.build_script_path)],
                                        cwd=str(build_dir),
                                        stdout=build_log,
                                        stderr=build_log)

                timeout = self.BUILD_SILENT_TIMEOUT
                result = None
                while result is None:
                    try:
                        result = proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        log_stat = build_log_path.stat()
                        quiet_time = time.time() - log_stat.st_mtime
                        # Has the output file changed recently?
                        if self.BUILD_SILENT_TIMEOUT < quiet_time:
                            # Give up on the build, and call it a failure.
                            proc.kill()
                            self.status.set(STATES.BUILD_FAILED,
                                            "Build timed out after {} seconds."
                                            .format(self.BUILD_SILENT_TIMEOUT))
                            return False
                        else:
                            # Only wait a max of BUILD_SILENT_TIMEOUT next
                            # 'wait'
                            timeout = self.BUILD_SILENT_TIMEOUT - quiet_time

        except subprocess.CalledProcessError as err:
            self.status.set(STATES.BUILD_ERROR,
                            "Error running build process: {}".format(err))
            return False

        except (IOError, OSError) as err:
            self.status.set(STATES.BUILD_ERROR,
                            "Error that's probably related to writing the "
                            "build output: {}".format(err))
            return False

        try:
            self._fix_build_permissions()
        except OSError as err:
            self.LOGGER.warning("Error fixing build permissions: {}"
                                .format(err))

        if result != 0:
            self.status.set(STATES.BUILD_FAILED,
                            "Build returned a non-zero result.")
            return False
        else:

            self.status.set(STATES.BUILD_DONE, "Build completed successfully.")
            return True

    TAR_SUBTYPES = (
        'gzip',
        'x-gzip',
        'x-bzip2',
        'x-xz',
        'x-tar',
        'x-lzma',
    )

    def _setup_build_dir(self, build_path):
        """Setup the build directory, by extracting or copying the source
            and any extra files.
        :param build_path: Path to the intended build directory.
        :return: None
        """

        build_config = self.config.get('build', {})

        src_loc = build_config.get('source_location')
        if src_loc is None:
            src_path = None
        elif self._isurl(src_loc):
            # Remove special characters from the url to get a reasonable
            # default file name.
            download_name = build_config.get('source_download_name')
            # Download the file to the downloads directory.
            src_path = self._download_path(src_loc, download_name)
        else:
            src_path = self._find_file(Path(src_loc), 'test_src')
            if src_path is None:
                raise PavTestError("Could not find source file '{}'"
                                   .format(src_path))

        if src_path is None:
            # If there is no source archive or data, just make the build
            # directory.
            build_path.mkdir()

        elif src_path.is_dir():
            # Recursively copy the src directory to the build directory.
            shutil.copytree(str(src_path), str(build_path), symlinks=True)

        elif src_path.is_file():
            # Handle decompression of a stream compressed file. The interfaces
            # for the libs are all the same; we just have to choose the right
            # one to use. Zips are handled as an archive, below.
            category, subtype = utils.get_mime_type(src_path)

            if category == 'application' and subtype in self.TAR_SUBTYPES:
                if tarfile.is_tarfile(str(src_path)):
                    try:
                        with tarfile.open(str(src_path), 'r') as tar:
                            # Filter out all but the top level items.
                            top_level = [m for m in tar.members
                                         if '/' not in m.name]
                            # If the file contains only a single directory,
                            # make that directory the build directory. This
                            # should be the default in most cases.
                            if len(top_level) == 1 and top_level[0].isdir():
                                tmpdir = build_path.with_suffix('.tmp')
                                tmpdir.mkdir()
                                tar.extractall(str(tmpdir))
                                opath = tmpdir/top_level[0].name
                                opath.rename(build_path)
                                tmpdir.rmdir()
                            else:
                                # Otherwise, the build path will contain the
                                # extracted contents of the archive.
                                build_path.mkdir()
                                tar.extractall(str(build_path))
                    except (OSError, IOError,
                            tarfile.CompressionError, tarfile.TarError) as err:
                        raise PavTestError(
                            "Could not extract tarfile '{}' into '{}': {}"
                            .format(src_path, build_path, err))

                else:
                    # If it's a compressed file but isn't a tar, extract the
                    # file into the build directory.
                    # All the python compression libraries have the same basic
                    # interface, so we can just dynamically switch between
                    # modules.
                    if subtype in ('gzip', 'x-gzip'):
                        comp_lib = gzip
                    elif subtype == 'x-bzip2':
                        comp_lib = bz2
                    elif subtype in ('x-xz', 'x-lzma'):
                        comp_lib = lzma
                    elif subtype == 'x-tar':
                        raise PavTestError(
                            "Test src file '{}' is a bad tar file."
                            .format(src_path))
                    else:
                        raise RuntimeError("Unhandled compression type. '{}'"
                                           .format(subtype))

                    decomp_fn = src_path.with_suffix('').name
                    decomp_fn = build_path/decomp_fn
                    build_path.mkdir()

                    try:
                        with comp_lib.open(str(src_path)) as infile, \
                                decomp_fn.open('wb') as outfile:
                            shutil.copyfileobj(infile, outfile)
                    except (OSError, IOError, lzma.LZMAError) as err:
                        raise PavTestError(
                            "Error decompressing compressed file "
                            "'{}' into '{}': {}"
                            .format(src_path, decomp_fn, err))

            elif category == 'application' and subtype == 'zip':
                try:
                    # Extract the zipfile, under the same conditions as
                    # above with tarfiles.
                    with zipfile.ZipFile(str(src_path)) as zipped:

                        tmpdir = build_path.with_suffix('.unzipped')
                        tmpdir.mkdir()
                        zipped.extractall(str(tmpdir))

                        files = os.listdir(str(tmpdir))
                        if len(files) == 1 and (tmpdir/files[0]).is_dir():
                            # Make the zip's root directory the build dir.
                            (tmpdir/files[0]).rename(build_path)
                            tmpdir.rmdir()
                        else:
                            # The overall contents of the zip are the build dir.
                            tmpdir.rename(build_path)

                except (OSError, IOError, zipfile.BadZipFile) as err:
                    raise PavTestError(
                        "Could not extract zipfile '{}' into destination "
                        "'{}': {}".format(src_path, build_path, err))

            else:
                # Finally, simply copy any other types of files into the build
                # directory.
                dest = build_path/src_path.name
                try:
                    build_path.mkdir()
                    shutil.copyfile(str(src_path), str(dest))
                except OSError as err:
                    raise PavTestError(
                        "Could not copy test src '{}' to '{}': {}"
                        .format(src_path, dest, err))

        # Now we just need to copy over all of the extra files.
        for extra in build_config.get('extra_files', []):
            extra = Path(extra)
            path = self._find_file(extra, 'test_src')
            dest = build_path/path.name
            try:
                shutil.copyfile(str(path), str(dest))
            except OSError as err:
                raise PavTestError(
                    "Could not copy extra file '{}' to dest '{}': {}"
                    .format(path, dest, err))

    RUN_SILENT_TIMEOUT = 5*60

    def _fix_build_permissions(self):
        """The files in a build directory should never be writable, but
            directories should be. Users are thus allowed to delete build
            directories and their files, but never modify them. Additions,
            deletions within test build directories will effect the soft links,
            not the original files themselves. (This applies both to owner and
            group).
        :raises OSError: If we lack permissions or something else goes wrong."""

        # We rely on the umask to handle most restrictions.
        # This just masks out the write bits.
        file_mask = 0o777555

        # We shouldn't have to do anything to directories, they should have
        # the correct permissions already.
        for path, _, files in os.walk(str(self.build_origin)):
            path = Path(path)
            for file in files:
                file_path = path/file
                st = file_path.stat()
                file_path.lchmod(st.st_mode & file_mask)

    def run(self, sched_vars):
        """Run the test, returning True on success, False otherwise.
        :param dict sched_vars: The scheduler variables for resolving the build
        template.
        """

        if self.run_tmpl_path is not None:
            # Convert the run script template into the final run script.
            try:
                var_man = variables.VariableSetManager()
                var_man.add_var_set('sched', sched_vars)
                var_man.add_var_set('sys', self._pav_cfg.sys_vars)

                self.resolve_template(self.run_tmpl_path,
                                      self.run_script_path,
                                      var_man)
            except KeyError as err:
                msg = ("Error converting run template '{}' into the final " 
                       "script: {}"
                       .format(self.run_tmpl_path, err))
                self.LOGGER.error(msg)
                self.status.set(STATES.RUN_ERROR, msg)
            except PavTestError as err:
                self.LOGGER.error(err)
                self.status.set(STATES.RUN_ERROR, err)

        run_log_path = self.path/'run.log'

        with run_log_path.open('wb') as run_log:
            run_wd = str(self.build_path) if self.build_path is not None \
                                            else None
            proc = subprocess.Popen([str(self.run_script_path)],
                                    cwd=run_wd,
                                    stdout=run_log,
                                    stderr=run_log)

            # Run the test, but timeout if it doesn't produce any output every
            # RUN_SILENT_TIMEOUT seconds
            timeout = self.RUN_SILENT_TIMEOUT
            result = None
            while result is None:
                try:
                    result = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    out_stat = run_log_path.stat()
                    quiet_time = time.time() - out_stat.st_mtime
                    # Has the output file changed recently?
                    if self.RUN_SILENT_TIMEOUT < quiet_time:
                        # Give up on the build, and call it a failure.
                        proc.kill()
                        self.status.set(STATES.RUN_FAILED,
                                        "Run timed out after {} seconds."
                                        .format(self.RUN_SILENT_TIMEOUT))
                        return False
                    else:
                        # Only wait a max of BUILD_SILENT_TIMEOUT next 'wait'
                        timeout = self.RUN_SILENT_TIMEOUT - quiet_time

        if result != 0:
            self.status.set(STATES.RUN_FAILED, "Test run failed.")
            return False
        else:
            self.status.set(STATES.RUN_DONE,
                            "Test run has completed successfully.")
            return True

    def process_results(self):
        """Process the results of the test."""

    @property
    def is_built(self):
        """Whether the build for this test exists.
        :returns: True if the build exists (or the test doesn't have a build),
            False otherwise.
        """

        if self.build_path.resolve().exists():
            return True
        else:
            return False

    @property
    def job_id(self):

        path = self.path/'jobid'

        if self._job_id is not None:
            return self._job_id

        try:
            with path.open('r') as job_id_file:
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

        path = self.path/'jobid'

        try:
            with path.open('w') as job_id_file:
                job_id_file.write(job_id)
        except (IOError, OSError) as err:
            self.LOGGER.error("Could not write jobid file '{}': {}"
                              .format(path, err))

        self._job_id = job_id

    @property
    def ts(self):
        """Return the unix timestamp for this test, based on the last
        modified date for the test directory."""
        return self.path.stat().st_mtime

    def _hash_dict(self, mapping):
        """Create a hash from the keys and items in 'mapping'. Keys are
            processed in order. Can handle lists and other dictionaries as
            values.
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
        :param Path path: Path to the file to hash.
        """

        hash_obj = hashlib.sha256()

        with path.open('rb') as file:
            chunk = file.read(self._BLOCK_SIZE)
            while chunk:
                hash_obj.update(chunk)
                chunk = file.read(self._BLOCK_SIZE)

        return hash_obj.digest()

    @staticmethod
    def _hash_dir(path):
        """Instead of hashing the files within a directory, we just create a
            'hash' based on it's name and mtime, assuming we've run _date_dir
            on it before hand. This produces an arbitrary string, not a hash.
        :param Path path: The path to the directory.
        :returns: The 'hash'
        """

        dir_stat = path.stat()
        return '{} {:0.5f}'.format(path, dir_stat.st_mtime).encode('utf-8')

    @staticmethod
    def _date_dir(base_path):
        """Update the mtime of the given directory or path to the the latest
        mtime contained within.
        :param Path base_path: The root of the path to evaluate.
        """

        src_stat = base_path.stat()
        latest = src_stat.st_mtime

        paths = utils.flat_walk(base_path)
        for path in paths:
            dir_stat = path.stat()
            if dir_stat.st_mtime > latest:
                latest = dir_stat.st_mtime

        if src_stat.st_mtime != latest:
            os.utime(str(base_path), (src_stat.st_atime, latest))

    def _write_script(self, path, config):
        """Write a build or run script or template. The formats for each are
            identical.
        :param str path: Path to the template file to write.
        :param dict config: Configuration dictionary for the script file.
        :return:
        """

        script = scriptcomposer.ScriptComposer(
            details=scriptcomposer.ScriptDetails(
                path=path,
                group=self._pav_cfg.shared_group,
            ))

        pav_lib_bash = self._pav_cfg.pav_root/'bin'/'pav-lib.bash'

        script.comment('The following is added to every test build and '
                       'run script.')
        script.env_change({'TEST_ID': '{}'.format(self.id)})
        script.command('source {}'.format(pav_lib_bash))

        modules = config.get('modules', [])
        if modules:
            script.newline()
            script.comment('Perform module related changes to the environment.')

            for module in config.get('modules', []):
                script.module_change(module, self._pav_cfg.sys_vars)

        env = config.get('env', {})
        if env:
            script.newline()
            script.comment("Making any environment changes needed.")
            script.env_change(config.get('env', {}))

        script.newline()
        cmds = config.get('cmds', [])
        if cmds:
            script.comment("Perform the sequence of test commands.")
            for line in config.get('cmds', []):
                for split_line in line.split('\n'):
                    script.command(split_line)
        else:
            script.comment('No commands given for this script.')

        script.write()

    @classmethod
    def resolve_template(cls, tmpl_path, script_path, var_man):
        """Resolve the test deferred variables using the appropriate escape
            sequence.
        :param Path tmpl_path: Path to the template file to read.
        :param Path script_path: Path to the script file to write.
        :param variables.VariableSetManager var_man: A variable set manager for
            retrieving found variables. Is expected to contain the sys and
            sched variable sets.
        :raises KeyError: For unknown variables in the template.
        """

        try:
            with tmpl_path.open('r') as tmpl, \
                 script_path.open('w') as script:

                for line in tmpl.readlines():
                    script.write(var_man.resolve_deferred_str(line))

            # Add group and owner execute permissions to the produced script.
            new_mode = (script_path.stat().st_mode |
                        stat.S_IXGRP |
                        stat.S_IXUSR)
            os.chmod(str(script_path), new_mode)

        except ValueError as err:
            raise PavTestError("Problem escaping run template file '{}': {}"
                               .format(tmpl_path, err))

        except (IOError, OSError) as err:
            raise PavTestError("Failed processing run template file '{}' into "
                               "run script'{}': {}"
                               .format(tmpl_path, script_path, err))

    def __repr__(self):
        return "PavTest({s.name}-{s.id})".format(s=self)
