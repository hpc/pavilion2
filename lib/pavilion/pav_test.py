from pathlib import Path
from pavilion import lockfile
from pavilion import result_parsers
from pavilion import scriptcomposer
from pavilion import utils
from pavilion import wget
from pavilion.status_file import StatusFile, STATES
from pavilion.test_config import variables
import bz2
import datetime
import gzip
import hashlib
import json
import logging
import lzma
import os
import re
import shutil
import stat
import subprocess
import tarfile
import time
import tzlocal
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

    def __init__(self, pav_cfg, config, sys_vars, _id=None):
        """Create an new PavTest object. If loading an existing test instance,
        use the PavTest.from_id method.
        :param pav_cfg: The pavilion configuration.
        :param config: The test configuration dictionary.
        :param Union(dict, None) sys_vars: System variables.
        :param _id: The test id of an existing test. (You should be using
            PavTest.load).
        """

        if _id is None and sys_vars is None:
            raise RuntimeError("New PavTest objects require a sys_vars dict. ")

        # Just about every method needs this
        self._pav_cfg = pav_cfg

        # Compute the actual name of test, using the subtest config parameter.
        self.name = config['name']
        if 'subtest' in config and config['subtest']:
            self.name = self.name + '.' + config['subtest']

        self.scheduler = config['scheduler']

        # Create the tests directory if it doesn't already exist.
        tests_path = pav_cfg.working_dir/'tests'

        self.config = config

        # Get an id for the test, if we weren't given one.
        if _id is None:
            self.id, self.path = utils.create_id_dir(tests_path)
            self._save_config()
        else:
            self.id = _id
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
        if _id is None:
            self.status.set(STATES.CREATED,
                            "Test directory and status file created.")

        self._started = None
        self._finished = None

        self.build_path = None          # type: Path
        self.build_name = None
        self.build_hash = None          # type: str
        self.build_script_path = None   # type: Path
        self.build_origin = None        # type: Path
        self.run_log = self.path/'run.log'
        self.results_path = self.path/'results.json'

        build_config = self.config.get('build', {})

        self.build_script_path = self.path/'build.sh'
        if not self.build_script_path.exists():
            self._write_script(self.build_script_path,
                               build_config,
                               sys_vars)

        self.build_path = self.path/'build'
        if self.build_path.is_symlink():
            build_rp = self.build_path.resolve()
            self.build_hash = build_rp.name
        else:
            self.build_hash = self._create_build_hash(build_config)

        short_hash = self.build_hash[:self.BUILD_HASH_BYTES*2]
        self.build_name = '{hash}'.format(hash=short_hash)
        self.build_origin = pav_cfg.working_dir/'builds'/self.build_name

        run_config = self.config.get('run', {})
        if run_config:
            self.run_tmpl_path = self.path/'run.tmpl'
            self.run_script_path = self.path/'run.sh'
            if not self.run_tmpl_path.exists():
                self._write_script(self.run_tmpl_path, run_config, sys_vars)
        else:
            self.run_tmpl_path = None
            self.run_script_path = None

        if _id is None:
            self.status.set(STATES.CREATED, "Test directory setup complete.")

    @classmethod
    def load(cls, pav_cfg, test_id):
        """Load an old PavTest object given a test id.
        :param pav_cfg: The pavilion config
        :param int test_id: The test's id number.
        """

        path = utils.make_id_path(pav_cfg.working_dir/'tests', test_id)

        if not path.is_dir():
            raise PavTestError("Test directory for test id {} does not exist "
                               "at '{}' as expected."
                               .format(test_id, path))

        config = cls._load_config(path)

        return PavTest(pav_cfg, config, None, _id=test_id)

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
                utils.json_dump(self.config, json_file)
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
                # Because only string keys are allowed in test configs,
                # this is a reasonable way to load them.
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
        #  - The build script
        #  - The build specificity
        #  - The src archive.
        #    - For directories, the mtime (updated to the time of the most
        #      recently updated file) is hashed instead.
        #  - All of the build's 'extra_files'

        hash_obj = hashlib.sha256()

        # Update the hash with the contents of the build script.
        hash_obj.update(self._hash_file(self.build_script_path))

        specificity = build_config.get('specificity', '')
        hash_obj.update(specificity.encode('utf8'))

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
            self.status.set(STATES.BUILDING,
                            "Starting build {}.".format(self.build_hash))
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
                        # raise an exception unless something goes terribly
                        # wrong.
                        # This will also set the test status for
                        # non-catastrophic cases.
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
                            shutil.rmtree(path=build_dir.as_posix(),
                                          onerror=handle_error)
                else:
                    self.status.set(
                        STATES.BUILDING,
                        "Build {} created while waiting for build lock."
                        .format(self.build_hash))

                # Make a symlink in the build directory that points to
                # the original test that built it
                try:
                    dst = str(self.build_origin) + "/test"
                    src = str(self.path)
                    os.symlink(src, dst)
                except: 
                    self.LOGGER.warning("Could not create symlink to test")

        else:
            self.status.set(STATES.BUILDING,
                            "Build {} already exists.".format(self.build_hash))

        # Perform a symlink copy of the original build directory into our test
        # directory.
        try:
            shutil.copytree(self.build_origin.as_posix(),
                            self.build_path.as_posix(),
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
            os.utime(self.build_origin.as_posix(), (now, now))
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
            # Do the build, and wait for it to complete.
            with build_log_path.open('w') as build_log:
                # Build scripts take the test id as a first argument.
                cmd = [self.build_script_path.as_posix(), str(self.id)]
                proc = subprocess.Popen(cmd,
                                        cwd=build_dir.as_posix(),
                                        stdout=build_log,
                                        stderr=subprocess.STDOUT)

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
            shutil.copytree(src_path.as_posix(),
                            build_path.as_posix(),
                            symlinks=True)

        elif src_path.is_file():
            # Handle decompression of a stream compressed file. The interfaces
            # for the libs are all the same; we just have to choose the right
            # one to use. Zips are handled as an archive, below.
            category, subtype = utils.get_mime_type(src_path)

            if category == 'application' and subtype in self.TAR_SUBTYPES:
                if tarfile.is_tarfile(src_path.as_posix()):
                    try:
                        with tarfile.open(src_path.as_posix(), 'r') as tar:
                            # Filter out all but the top level items.
                            top_level = [m for m in tar.members
                                         if '/' not in m.name]
                            # If the file contains only a single directory,
                            # make that directory the build directory. This
                            # should be the default in most cases.
                            if len(top_level) == 1 and top_level[0].isdir():
                                tmpdir = build_path.with_suffix('.extracted')
                                tmpdir.mkdir()
                                tar.extractall(tmpdir.as_posix())
                                opath = tmpdir/top_level[0].name
                                opath.rename(build_path)
                                tmpdir.rmdir()
                            else:
                                # Otherwise, the build path will contain the
                                # extracted contents of the archive.
                                build_path.mkdir()
                                tar.extractall(build_path.as_posix())
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
                        with comp_lib.open(src_path.as_posix()) as infile, \
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
                    with zipfile.ZipFile(src_path.as_posix()) as zipped:

                        tmpdir = build_path.with_suffix('.unzipped')
                        tmpdir.mkdir()
                        zipped.extractall(tmpdir.as_posix())

                        files = os.listdir(tmpdir.as_posix())
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
                    shutil.copyfile(src_path.as_posix(), dest.as_posix())
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
                shutil.copyfile(path.as_posix(), dest.as_posix())
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
        for path, _, files in os.walk(self.build_origin.as_posix()):
            path = Path(path)
            for file in files:
                file_path = path/file
                st = file_path.stat()
                file_path.lchmod(st.st_mode & file_mask)

    def run(self, sched_vars, sys_vars):
        """Run the test, returning True on success, False otherwise.
        :param dict sched_vars: The scheduler variables for resolving the build
            template.
        :param dict sys_vars: The system variables."""

        self.status.set(STATES.PREPPING_RUN,
                        "Resolving final run script.")

        if self.run_tmpl_path is not None:
            # Convert the run script template into the final run script.
            try:
                var_man = variables.VariableSetManager()
                var_man.add_var_set('sched', sched_vars)
                var_man.add_var_set('sys', sys_vars)

                self.resolve_template(self.run_tmpl_path,
                                      self.run_script_path,
                                      var_man)
            except KeyError as err:
                msg = ("Error converting run template '{}' into the final " 
                       "script: {}"
                       .format(self.run_tmpl_path, err))
                self.LOGGER.error(msg)
                self.status.set(STATES.RUN_ERROR, msg)
                return STATES.RUN_ERROR
            except PavTestError as err:
                self.LOGGER.error(err)
                self.status.set(STATES.RUN_ERROR, err)
                return STATES.RUN_ERROR

        with self.run_log.open('wb') as run_log:
            self.status.set(STATES.RUNNING,
                            "Starting the run script.")

            tz = tzlocal.get_localzone()

            self._started = tz.localize(datetime.datetime.now())

            # TODO: There should always be a build directory, even if there
            #       isn't a build.
            # Set the working directory to the build path, if there is one.
            run_wd = None
            if self.build_path is not None:
                run_wd = self.build_path.as_posix()

            # Run scripts take the test id as a first argument.
            cmd = [self.run_script_path.as_posix(), str(self.id)]
            proc = subprocess.Popen(cmd,
                                    cwd=run_wd,
                                    stdout=run_log,
                                    stderr=subprocess.STDOUT)

            # Run the test, but timeout if it doesn't produce any output every
            # RUN_SILENT_TIMEOUT seconds
            timeout = self.RUN_SILENT_TIMEOUT
            result = None
            while result is None:
                try:
                    result = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    out_stat = self.run_log.stat()
                    quiet_time = time.time() - out_stat.st_mtime
                    # Has the output file changed recently?
                    if self.RUN_SILENT_TIMEOUT < quiet_time:
                        # Give up on the build, and call it a failure.
                        proc.kill()
                        self.status.set(STATES.RUN_FAILED,
                                        "Run timed out after {} seconds."
                                        .format(self.RUN_SILENT_TIMEOUT))
                        self._finished = tz.localize(datetime.datetime.now())
                        return STATES.RUN_TIMEOUT
                    else:
                        # Only wait a max of BUILD_SILENT_TIMEOUT next 'wait'
                        timeout = self.RUN_SILENT_TIMEOUT - quiet_time

        self._finished = tz.localize(datetime.datetime.now())
        if result != 0:
            self.status.set(STATES.RUN_FAILED, "Test run failed.")
            return STATES.RUN_FAILED
        else:
            self.status.set(STATES.RUN_DONE,
                            "Test run has completed successfully.")
            return STATES.RUN_DONE

    def set_run_complete(self):
        """Write a file in the test directory that indicates that the test
        has completed a run, one way or another. This should only be called
        when we're sure their won't be any more status changes."""

        # Write the current time to the file. We don't actually use the contents
        # of the file, but it's nice to have another record of when this was
        # run.
        with (self.path/'RUN_COMPLETE').open('w') as run_complete:
            run_complete.write(
                tzlocal.get_localzone().localize(
                    datetime.datetime.now()
                ).isoformat()
            )

    WAIT_INTERVAL = 0.5

    def wait(self, timeout=None):
        """Wait for the test run to be complete. This works across hosts, as
        it simply checks for files in the run directory.
        :param Union(None, float) timeout: How long to wait in seconds. If
            this is None, wait forever.
        :raises TimeoutError: if the timeout expires.
        """

        run_complete_file = self.path/'RUN_COMPLETE'

        if timeout is not None:
            timeout = time.time() + timeout

        while 1:
            if run_complete_file.exists():
                return

            if timeout is not None and time.time() > timeout:
                raise TimeoutError("Timed out waiting for test '{}' to "
                                   "complete".format(self.id))

    RESERVED_RESULT_KEYS = [
        'name',
        'id',
        'created',
        'started',
        'finished',
        'duration',
    ]

    def check_result_parsers(self):
        """Make sure the result parsers are sensible.
         - No duplicated key names.
         - Sensible keynames: /[a-z0-9_-]+/
         - No reserved key names.

        :raises PavTestError: When a config breaks the rules.
        """

        used_parsers = self.config['results']

        key_names = []

        for rtype in used_parsers:
            for rconf in self.config['results'][rtype]:
                key = rconf.get('key')

                if key is None:
                    raise RuntimeError(
                        "ResultParser config for parser '{}' missing key. "
                        "This is an error with the result parser itself,"
                        "probably.".format(rtype)
                    )

                regex = re.compile(result_parsers.ResultParser.KEY_REGEX_STR)

                if regex.match(key) is None:
                    raise RuntimeError(
                        "ResultParser config for parser '{}' has invalid key."
                        "Key does not match the required format. "
                        "This is an error with the result parser itself, "
                        "probably.".format(rtype)
                    )

                if key in key_names:
                    raise PavTestError(
                        "Duplicate result parser key name '{}' in test '{}'"
                        .format(key, self.name)
                    )

                if key in self.RESERVED_RESULT_KEYS:
                    raise PavTestError(
                        "Result parser key '{}' in test '{}' is reserved."
                        .format(key, self.name)
                    )

                key_names.append(key)

                parser = result_parsers.get_plugin(rtype)
                try:
                    # The parser's don't know about the 'key' config item.
                    args = rconf.copy()
                    del args['key']

                    parser.check_args(self, args)
                except result_parsers.ResultParserError as err:
                    raise PavTestError(
                        "Test '{}' has a result parser of type '{}' with"
                        "key '{}' that has invalid arguments: {}"
                        .format(self.name, rtype,
                                rconf.get('key', '<unset>'), err)
                    )

    def gather_results(self, run_result):
        """Process and log the results of the test, including the default set
        of result keys.

        Default Result Keys:
          name - The name of the test
          id - The test id
          created - When the test was created.
          started - When the test was started.
          finished - When the test finished running (or failed).
          duration - Length of the test run.
          result - Defaults to PASS if the test completed (with a zero
            exit status). Is generally expected to be overridden by other
            result parsers.

        :param str run_result: The result of the run.
        """

        if self._finished is None:
            raise RuntimeError(
                "test.gather_results can't be run unless the test was run"
                "(or an attempt was made to run it. "
                "This occurred for test {s.name}, #{s.id}"
                .format(s=self)
            )

        parser_configs = self.config['results']

        # Create a human readable timestamp from the test directories
        # modified (should be creation) timestamp.
        created = tzlocal.get_localzone().localize(
            datetime.datetime.fromtimestamp(
                self.path.stat().st_mtime
            )
        ).isoformat(" ")

        if run_result == STATES.RUN_DONE:
            default_result = result_parsers.PASS
        else:
            default_result = result_parsers.FAIL

        results = {
            # These can't be overridden
            'name': self.name,
            'id': self.id,
            'created': created,
            'started': self._started.isoformat(" "),
            'finished': self._finished.isoformat(" "),
            'duration': str(self._finished - self._started),
            # This may be overridden by result parsers.
            'result': default_result
        }

        self.status.set(STATES.RESULTS,
                        "Parsing {} result types."
                        .format(len(parser_configs)))

        for parser_name in parser_configs.keys():
            # This is almost guaranteed to work, as the config wouldn't
            # have validated otherwise.
            parser = result_parsers.get_plugin(parser_name)

            for rconf in parser_configs[parser_name]:
                try:
                    # The parser's don't know about the 'key' config item.
                    args = rconf.copy()
                    del args['key']

                    if 'file' not in args:
                        args['file'] = self.run_log

                    result = parser(self, **args)

                    results[rconf['key']] = result
                except (result_parsers.ResultParserError, KeyError) as err:
                    self.LOGGER.warning(
                        "Error parsing results for result parser '{}'"
                        "with key '{}': {}"
                        .format(parser.name, rconf.get('key', '<no_key>'), err))

        return results

    def save_results(self, results):
        """Save the results to the results file.
        :param dict results: The results dictionary.
        """

        with self.results_path.open('w') as results_file:
            json.dump(results, results_file)

    def load_results(self):
        """Load results from the results file.
        :returns A dict of results, or None if the results file doesn't exist.
        """

        if self.results_path.exists():
            with self.results_path.open() as results_file:
                return json.load(results_file)
        else:
            return None

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
            os.utime(base_path.as_posix(), (src_stat.st_atime, latest))

    def _write_script(self, path, config, sys_vars):
        """Write a build or run script or template. The formats for each are
            identical.
        :param str path: Path to the template file to write.
        :param dict config: Configuration dictionary for the script file.
        :return:
        """

        if sys_vars is None:
            raise RuntimeError("Trying to write script without sys_vars "
                               "in test '{}'.".format(self.id))

        script = scriptcomposer.ScriptComposer(
            details=scriptcomposer.ScriptDetails(
                path=path,
                group=self._pav_cfg.shared_group,
            ))

        pav_lib_bash = self._pav_cfg.pav_root/'bin'/'pav-lib.bash'

        # If we include this directly, it breaks build hashing.
        script.comment('The first (and only) argument of the build script is '
                       'the test id.')
        script.env_change({'TEST_ID': '$1'})
        script.command('source {}'.format(pav_lib_bash))

        modules = config.get('modules', [])
        if modules:
            script.newline()
            script.comment('Perform module related changes to the environment.')

            for module in config.get('modules', []):
                script.module_change(module, sys_vars)

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
            os.chmod(script_path.as_posix(), new_mode)

        except ValueError as err:
            raise PavTestError("Problem escaping run template file '{}': {}"
                               .format(tmpl_path, err))

        except (IOError, OSError) as err:
            raise PavTestError("Failed processing run template file '{}' into "
                               "run script'{}': {}"
                               .format(tmpl_path, script_path, err))

    def __repr__(self):
        return "PavTest({s.name}-{s.id})".format(s=self)
