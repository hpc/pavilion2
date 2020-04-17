"""Contains the object for tracking multi-threaded builds, along with
the TestBuilder class itself."""

import bz2
import datetime
import glob
import gzip
import hashlib
import io
import logging
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from pavilion import lockfile
from pavilion import output
from pavilion import utils
from pavilion import wget
from pavilion.status_file import STATES


class TestBuilderError(RuntimeError):
    """Exception raised when builds encounter an error."""


class MultiBuildTracker:
    """Allows for the central organization of multiple build tracker objects.

        :ivar {StatusFile} status_files: The dictionary of status
            files by build.
    """

    def __init__(self):
        """

        """

        # A map of build tokens to build names
        self.messages = {}
        self.status = {}
        self.status_files = {}
        self.lock = threading.Lock()

        self.logger = logging.getLogger(__name__)

    def register(self, builder, test_status_file):
        """Register a builder, and get your own build tracker.

        :param TestBuilder builder: The builder object to track.
        :param status_file.StatusFile test_status_file: The status file object
            for the corresponding test.
        :return: A build tracker instance that can be used by builds directly.
        :rtype: BuildTracker
        """

        with self.lock:
            self.status_files[builder] = test_status_file
            self.status[builder] = None
            self.messages[builder] = []

        tracker = BuildTracker(builder, self)
        return tracker

    def update(self, builder, note, state=None, log=None):
        """Add a message for the given builder without changes the status.

        :param TestBuilder builder: The builder object to set the message.
        :param note: The message to set.
        :param str state: A status_file state to set on this builder's status
            file.
        :param int log: A log level for the python logger. If set, also
            log the message to the Pavilion log.
        """

        if state is not None:
            self.status_files[builder].set(state, note)

        now = datetime.datetime.now()

        with self.lock:
            self.messages[builder].append((now, state, note))
            if state is not None:
                self.status[builder] = state

        if log is not None:
            self.logger.log(level=log, msg=note)

    def get_notes(self, builder):
        """Return all notes for the given builder.
        :param TestBuilder builder: The test builder object to get notes for.
        :rtype: [str]
        """

        return self.messages[builder]

    def state_counts(self):
        """Return a dictionary of the states across all builds and the number
        of occurrences of each."""
        counts = defaultdict(lambda: 0)
        for state in self.status.values():
            counts[state] += 1

        return counts

    def failures(self):
        """Returns a list of builders that have failed."""
        return [builder for builder in self.status.keys()
                if builder.tracker.failed]


class BuildTracker:
    """Tracks the status updates for a single build."""

    def __init__(self, builder, tracker):
        self.builder = builder
        self.tracker = tracker
        self.failed = False

    def update(self, note, state=None, log=None):
        """Update the tracker for this build with the given note."""

        self.tracker.update(self.builder, note, log=log, state=state)

    def warn(self, note, state=None):
        """Add a note and warn via the logger."""
        self.tracker.update(self.builder, note, log=logging.WARNING,
                            state=state)

    def error(self, note, state=STATES.BUILD_ERROR):
        """Add a note and error via the logger denote as a failure."""
        self.tracker.update(self.builder, note, log=logging.ERROR, state=state)

        self.failed = True

    def fail(self, note, state=STATES.BUILD_FAILED):
        """Denote that the test has failed."""
        self.error(note, state=state)

    def notes(self):
        """Return the notes for this tracker."""
        return self.tracker.get_notes(self.builder)


class TestBuilder:
    """Manages a test build and their organization.

:cvar int _BLOCK_SIZE: Chunk size when reading and hashing files.
:cvar int BUILD_HASH_BYTES: Number of bytes in the build hash (1/2 the
    chars)
:cvar str DEPRECATED: The name of the build deprecation file.
:ivar Path ~.path: The intended location of this build in the build directory.
:ivar Path fail_path: Where this build will be placed if it fails.
:ivar str name: The name of this build.
"""

    _BLOCK_SIZE = 4096*1024

    # We have to worry about hash collisions, but we don't need all the bytes
    # of hash most algorithms give us. The birthday attack math for 64 bits (
    # 8 bytes) of hash and 10 million items yields a collision probability of
    # just 0.00027%. Easily good enough.
    BUILD_HASH_BYTES = 8

    DEPRECATED = ".pav_deprecated_build"

    LOG_NAME = "pav_build_log"

    def __init__(self, pav_cfg, test, mb_tracker, build_name=None):
        """Inititalize the build object.
        :param pav_cfg: The Pavilion config object
        :param pavilion.test_run.TestRun test: The test run responsible for
        starting this build.
        :param MultiBuildTracker mb_tracker: A thread-safe tracker object for
        keeping info on what the build is doing.
        :param str build_name: The build name, if this is a build that already
        exists.
        :raises TestBuilderError: When the builder can't be initialized.
        """

        if mb_tracker is None:
            mb_tracker = MultiBuildTracker()
        self.tracker = mb_tracker.register(self, test.status)

        self._pav_cfg = pav_cfg
        self._config = test.config.get('build', {})
        self._script_path = test.build_script_path
        self.test = test
        self._timeout = test.build_timeout

        if not test.build_local:
            self.tracker.update(state=STATES.BUILD_DEFERRED,
                                note="Build will run on nodes.")

        if build_name is None:
            self.name = self.name_build()
            self.tracker.update(state=STATES.BUILD_CREATED,
                                note="Builder created.")
        else:
            self.name = build_name

        # TODO: Builds can get renamed, this needs to be fixed.
        self.path = pav_cfg.working_dir/'builds'/self.name  # type: Path
        fail_name = 'fail.{}.{}'.format(self.name, self.test.id)
        self.fail_path = pav_cfg.working_dir/'builds'/fail_name

    def exists(self):
        """Return True if the given build exists."""
        return self.path.exists()

    def create_build_hash(self):
        """Turn the build config, and everything the build needs, into a hash.
        This includes the build config itself, the source tarball, and all
        extra files."""

        # The hash order is:
        #  - The build script
        #  - The build specificity
        #  - The src archive.
        #    - For directories, the mtime (updated to the time of the most
        #      recently updated file) is hashed instead.
        #  - All of the build's 'extra_files'
        #  - All files needed to be created at build time 'create_files'

        hash_obj = hashlib.sha256()

        # Update the hash with the contents of the build script.
        hash_obj.update(self._hash_file(self._script_path))

        specificity = self._config.get('specificity', '')
        hash_obj.update(specificity.encode('utf8'))

        src_path = self._update_src()

        if src_path is not None:
            if src_path.is_file():
                hash_obj.update(self._hash_file(src_path))
            elif src_path.is_dir():
                hash_obj.update(self._hash_dir(src_path))
            else:
                raise TestBuilderError(
                    "Invalid src location {}."
                    .format(src_path))

        # Hash extra files.
        for extra_file in self._config.get('extra_files', []):
            extra_file = Path(extra_file)
            full_path = self._find_file(extra_file, Path('test_src'))

            if full_path is None:
                raise TestBuilderError(
                    "Could not find extra file '{}'"
                    .format(extra_file))
            elif full_path.is_file():
                hash_obj.update(self._hash_file(full_path))
            elif full_path.is_dir():
                self._date_dir(full_path)
                hash_obj.update(self._hash_dir(full_path))
            else:
                raise TestBuilderError(
                    "Extra file '{}' must be a regular file or directory."
                    .format(extra_file))

        # Hash created build files. These files are generated at build time in
        # the test's build directory but we need the contents of these files
        # hashed before build time. Thus, we include a hash of each file
        # consisting of the filename (including path) and it's contents via
        # IOString object.
        files_to_create = self._config.get('create_files')
        if files_to_create:
            for file, contents in files_to_create.items():
                io_contents = io.StringIO()
                io_contents.write("{}\n".format(file))
                for line in contents:
                    io_contents.write("{}\n".format(line))
                hash_obj.update(self._hash_io(io_contents))
                io_contents.close()

        hash_obj.update(self._config.get('specificity', '').encode('utf-8'))

        return hash_obj.hexdigest()[:self.BUILD_HASH_BYTES * 2]

    def name_build(self):
        """Search for the first non-deprecated version of this build (whether
        or not it exists) and name the build for it."""

        bhash = self.create_build_hash()

        builds_dir = self._pav_cfg.working_dir/'builds'
        version = 1
        base_name = bhash[:self.BUILD_HASH_BYTES*2]
        name = base_name
        path = builds_dir/name

        while path.exists() and (path/self.DEPRECATED).exists():
            version += 1
            name = '{base}-{version}'.format(base=base_name, version=version)
            path = builds_dir/name

        return name

    def rename_build(self):
        """Rechecks deprecation and updates the build name."""

        self.name = self.name_build()
        self.path = self._pav_cfg.working_dir/'builds'/self.name  # type: Path
        fail_name = 'fail.{}.{}'.format(self.name, self.test.id)
        self.fail_path = self._pav_cfg.working_dir/'builds'/fail_name

    def deprecate(self):
        """Deprecate this build, so that it will be rebuilt if any other
        test run wants to use it."""

        deprecated_path = self.path/self.DEPRECATED
        deprecated_path.touch(exist_ok=True)

    def _update_src(self):
        """Retrieve and/or check the existence of the files needed for the
            build. This can include pulling from URL's.
        :returns: src_path, extra_files
        """

        src_loc = self._config.get('source_location')
        if src_loc is None:
            return None

        # For URL's, check if the file needs to be updated, and try to do so.
        if self._isurl(src_loc):
            missing_libs = wget.missing_libs()
            if missing_libs:
                raise TestBuilderError(
                    "The dependencies needed for remote source retrieval "
                    "({}) are not available on this system. Please provide "
                    "your test source locally."
                    .format(', '.join(missing_libs)))

            dwn_name = self._config.get('source_download_name')
            src_dest = self._download_path(src_loc, dwn_name)

            wget.update(self._pav_cfg, src_loc, src_dest)

            return src_dest

        src_path = self._find_file(Path(src_loc), 'test_src')
        if src_path is None:
            raise TestBuilderError(
                "Could not find and update src location '{}'"
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
            raise TestBuilderError(
                "Source location '{}' points to something unusable."
                .format(src_path))

    def build(self, cancel_event=None):
        """Perform the build if needed, do a soft-link copy of the build
        directory into our test directory, and note that we've used the given
        build.
        :param threading.Event cancel_event: Allows builds to tell each other
        to die.
        :return: True if these steps completed successfully.
        """

        # Only try to do the build if it doesn't already exist.
        if not self.path.exists():
            # Make sure another test doesn't try to do the build at
            # the same time.
            # Note cleanup of failed builds HAS to occur under this lock to
            # avoid a race condition, even though it would be way simpler to
            # do it in .build()
            self.tracker.update(
                state=STATES.BUILD_WAIT,
                note="Waiting on lock for build {}.".format(self.name))
            lock_path = self.path.with_suffix('.lock')
            with lockfile.LockFile(lock_path, group=self._pav_cfg.shared_group):
                # Make sure the build wasn't created while we waited for
                # the lock.
                if not self.path.exists():
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note="Starting build {}.".format(self.name))
                    build_dir = self.path.with_suffix('.tmp')

                    # Attempt to perform the actual build, this shouldn't
                    # raise an exception unless something goes terribly
                    # wrong.
                    # This will also set the test status for
                    # non-catastrophic cases.
                    if not self._build(build_dir, cancel_event):
                        try:
                            build_dir.rename(self.fail_path)
                        except FileNotFoundError as err:
                            self.tracker.error(
                                "Failed to move build {} from {} to "
                                "failure path {}: {}"
                                .format(self.name, build_dir,
                                        self.fail_path, err))
                            self.fail_path.mkdir()
                            if cancel_event is not None:
                                cancel_event.set()

                        # If the build didn't succeed, copy the attempted build
                        # into the test run, and set the run as complete.
                        return False

                    # Rename the build to it's final location.
                    build_dir.rename(self.path)

                    # Make a file with the test id of the building test.
                    try:
                        dst = self.path / '.built_by'
                        with dst.open('w') as built_by:
                            built_by.write(str(self.test.id))
                    except OSError:
                        self.tracker.warn("Could not create built_by file.")
                else:
                    self.tracker.update(
                        state=STATES.BUILD_REUSED,
                        note="Build {s.name} created while waiting for build "
                             "lock.".format(s=self))
        else:
            self.tracker.update(
                note=("Test {s.name} run {s.test.id} reusing build."
                      .format(s=self)),
                state=STATES.BUILD_REUSED)

        return True

    def _build(self, build_dir, cancel_event):
        """Perform the build. This assumes there actually is a build to perform.
        :param Path build_dir: The directory in which to perform the build.
        :param threading.Event cancel_event: Event to signal that the build
        should stop.
        :returns: True or False, depending on whether the build appears to have
            been successful.
        """

        try:
            self._setup_build_dir(build_dir)
        except TestBuilderError as err:
            self.tracker.error(
                note=("Error setting up build directory '{}': {}"
                      .format(build_dir, err)))
            return False

        # Create the build log outside the build directory, to avoid issues
        # with the build process deleting the file.
        build_log_path = build_dir.with_suffix('.log')

        try:
            # Do the build, and wait for it to complete.
            with build_log_path.open('w') as build_log:
                # Build scripts take the test id as a first argument.
                cmd = [self._script_path.as_posix(), str(self.test.id)]
                proc = subprocess.Popen(cmd,
                                        cwd=build_dir.as_posix(),
                                        stdout=build_log,
                                        stderr=build_log)

                result = None
                while result is None:
                    try:
                        result = proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        log_stat = build_log_path.stat()
                        timeout = log_stat.st_mtime + self._timeout
                        # Has the output file changed recently?
                        if time.time() > timeout:
                            # Give up on the build, and call it a failure.
                            proc.kill()
                            cancel_event.set()
                            self.tracker.fail(
                                state=STATES.BUILD_TIMEOUT,
                                note="Build timed out after {} seconds."
                                .format(self._timeout))
                            return False

                        if cancel_event is not None and cancel_event.is_set():
                            proc.kill()
                            self.tracker.update(
                                state=STATES.ABORTED,
                                note="Build canceled due to other builds "
                                     "failing.")
                            return False

        except subprocess.CalledProcessError as err:
            if cancel_event is not None:
                cancel_event.set()
            self.tracker.error(
                note="Error running build process: {}".format(err))
            return False

        except (IOError, OSError) as err:
            if cancel_event is not None:
                cancel_event.set()

            self.tracker.error(
                note="Error that's probably related to writing the "
                     "build output: {}".format(err))
            return False
        finally:
            try:
                build_log_path.rename(build_dir/self.LOG_NAME)
            except OSError as err:
                self.tracker.warn(
                    "Could not move build log from '{}' to final location "
                    "'{}': {}"
                    .format(build_log_path, build_dir, err))

        try:
            self._fix_build_permissions()
        except OSError as err:
            self.tracker.warn("Error fixing build permissions: %s".format(err))

        if result != 0:
            if cancel_event is not None:
                cancel_event.set()
            self.tracker.fail(
                note="Build returned a non-zero result.")
            return False
        else:

            self.tracker.update(
                state=STATES.BUILD_DONE,
                note="Build completed successfully.")
            return True

    TAR_SUBTYPES = (
        'gzip',
        'x-gzip',
        'x-bzip2',
        'x-xz',
        'x-tar',
        'x-lzma',
    )

    def _setup_build_dir(self, dest):
        """Setup the build directory, by extracting or copying the source
            and any extra files.
        :param dest: Path to the intended build directory. This is generally a
        temporary location.
        :return: None
        """

        src_loc = self._config.get('source_location')
        if src_loc is None:
            src_path = None
        elif self._isurl(src_loc):
            # Remove special characters from the url to get a reasonable
            # default file name.
            download_name = self._config.get('source_download_name')
            # Download the file to the downloads directory.
            src_path = self._download_path(src_loc, download_name)
        else:
            src_path = self._find_file(Path(src_loc), 'test_src')
            if src_path is None:
                raise TestBuilderError("Could not find source file '{}'"
                                       .format(src_path))
            # Resolve any softlinks to get the real file.
            src_path = src_path.resolve()

        if src_path is None:
            # If there is no source archive or data, just make the build
            # directory.
            dest.mkdir()

        elif src_path.is_dir():
            # Recursively copy the src directory to the build directory.
            self.tracker.update(
                state=STATES.BUILDING,
                note=("Copying source directory {} for build {} "
                      "as the build directory."
                      .format(src_path, dest)))
            shutil.copytree(src_path.as_posix(),
                            dest.as_posix(),
                            symlinks=True)

        elif src_path.is_file():
            # Handle decompression of a stream compressed file. The interfaces
            # for the libs are all the same; we just have to choose the right
            # one to use. Zips are handled as an archive, below.
            category, subtype = utils.get_mime_type(src_path)

            if category == 'application' and subtype in self.TAR_SUBTYPES:

                if tarfile.is_tarfile(src_path.as_posix()):
                    self._extract_tarball(src_path, dest)
                else:
                    self._decompress_file(src_path, dest, subtype)
            elif category == 'application' and subtype == 'zip':

                self._unzip_file(src_path, dest)

            else:
                # Finally, simply copy any other types of files into the build
                # directory.
                self.tracker.update(
                    state=STATES.BUILDING,
                    note="Copying file {} for build {} into the build "
                         "directory.".format(src_path, dest))

                copy_dest = dest / src_path.name
                try:
                    dest.mkdir()
                    shutil.copy(src_path.as_posix(), copy_dest.as_posix())
                except OSError as err:
                    raise TestBuilderError(
                        "Could not copy test src '{}' to '{}': {}"
                        .format(src_path, dest, err))

        # Generate file(s) from build_config
        files_to_create = self._config.get('create_files')
        if files_to_create:
            for file, contents in files_to_create.items():
                # FIXME: We don't want to allow users to create files outside of
                # the build directory. The build should fail here, not skip.
                if '../' in file:
                    output.fprint("BUILD WARNING: invalid path syntax; "
                                  + "skipping 'create_file: {}'".format(str(file)),
                                  sys.stderr, color=output.YELLOW)
                    continue
                dirname = os.path.dirname(file)
                Path(dest / dirname).mkdir(parents=True, exist_ok=True)
                file_path = Path(file)
                with open(str(dest / file_path), 'w') as file_:
                    for line in contents:
                        file_.write("{}\n".format(line))

        # Now we just need to copy over all of the extra files.
        for extra in self._config.get('extra_files', []):
            extra = Path(extra)
            path = self._find_file(extra, 'test_src')
            final_dest = dest / path.name
            try:
                shutil.copy(path.as_posix(), final_dest.as_posix())
            except OSError as err:
                raise TestBuilderError(
                    "Could not copy extra file '{}' to dest '{}': {}"
                    .format(path, dest, err))

    def copy_build(self, dest):
        """Copy the build (using 'symlink' copying to the destination.

        :param Path dest: Where to copy the build to.
        :returns: True on success, False on failure
        """

        do_copy = set()
        copy_globs = self._config.get('copy_files', [])
        for copy_glob in copy_globs:
            do_copy.update(glob.glob(self.path.as_posix() + '/' + copy_glob,
                                     recursive=True))

        def maybe_symlink_copy(src, dst):
            """Makes a symlink from src to dst, unless the file is in
            the list of files to do a regular copy on.
            """

            if src in do_copy:
                # Actually copy files that were explicitly asked for.
                return shutil.copy2(src, dst, follow_symlinks=True)
            else:
                src = os.path.realpath(src)
                return os.symlink(src, dst)

        # Perform a symlink copy of the original build directory into our test
        # directory.
        try:
            shutil.copytree(self.path.as_posix(),
                            dest.as_posix(),
                            symlinks=True,
                            copy_function=maybe_symlink_copy)
        except OSError as err:
            self.tracker.error(
                note=("Could not perform the build directory copy: {}"
                      .format(err)))
            return False

        # Touch the original build directory, so that we know it was used
        # recently.
        try:
            now = time.time()
            os.utime(self.path.as_posix(), (now, now))
        except OSError as err:
            self.tracker.warn(
                "Could not update timestamp on build directory '%s': %s"
                .format(self.path, err))

        return True

    def _extract_tarball(self, src_path, build_dest):

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
                        self.tracker.update(
                            state=STATES.BUILDING,
                            note=("Extracting tarfile {} for build {} "
                                  "as the build directory."
                                  .format(src_path, build_dest)))
                        tmpdir = self.path.with_suffix('.extracted')
                        tmpdir.mkdir()
                        tar.extractall(tmpdir.as_posix())
                        opath = tmpdir / top_level[0].name
                        opath.rename(build_dest)
                        tmpdir.rmdir()
                    else:
                        # Otherwise, the build path will contain the
                        # extracted contents of the archive.
                        self.tracker.update(
                            state=STATES.BUILDING,
                            note=("Extracting tarfile {} for build {} into the "
                                  "build directory."
                                  .format(src_path, build_dest)))
                        build_dest.mkdir()
                        tar.extractall(build_dest.as_posix())
            except (OSError, IOError,
                    tarfile.CompressionError, tarfile.TarError) as err:
                raise TestBuilderError(
                    "Could not extract tarfile '{}' into '{}': {}"
                    .format(src_path, build_dest, err))

    def _decompress_file(self, src_path, build_dest, subtype):

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
            raise TestBuilderError(
                "Test src file '{}' is a bad tar file."
                .format(src_path))
        else:
            raise RuntimeError("Unhandled compression type. '{}'"
                               .format(subtype))

        self.tracker.update(
            state=STATES.BUILDING,
            note=("Extracting {} file {} for build {} into the build directory."
                  .format(subtype, src_path, build_dest)))
        decomp_fn = src_path.with_suffix('').name
        decomp_fn = build_dest / decomp_fn
        build_dest.mkdir()

        try:
            with comp_lib.open(src_path.as_posix()) as infile, \
                    decomp_fn.open('wb') as outfile:
                shutil.copyfileobj(infile, outfile)
        except (OSError, IOError, lzma.LZMAError) as err:
            raise TestBuilderError(
                "Error decompressing compressed file "
                "'{}' into '{}': {}"
                .format(src_path, decomp_fn, err))

    def _unzip_file(self, src_path, build_dest):
        tmpdir = build_dest.with_suffix('.unzipped')
        try:
            # Extract the zipfile, under the same conditions as
            # above with tarfiles.
            with ZipFile(src_path.as_posix()) as zipped:

                tmpdir.mkdir()
                zipped.extractall(tmpdir.as_posix())

                files = os.listdir(tmpdir.as_posix())
                if len(files) == 1 and (tmpdir / files[0]).is_dir():
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note=("Extracting zip file {} for build {} as the "
                              "build directory."
                              .format(src_path, build_dest)))
                    # Make the zip's root directory the build dir.
                    (tmpdir / files[0]).rename(build_dest)
                    tmpdir.rmdir()
                else:
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note=("Extracting zip file {} for build {} into the "
                              "build directory."
                              .format(src_path, build_dest)))
                    # The overall contents of the zip are the build dir.
                    tmpdir.rename(build_dest)

        except (OSError, IOError, BadZipFile) as err:
            raise TestBuilderError(
                "Could not extract zipfile '{}' into destination "
                "'{}': {}".format(src_path, build_dest, err))
        finally:
            if tmpdir.exists():
                shutil.rmtree(tmpdir.as_posix())

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
        for path, _, files in os.walk(self.path.as_posix()):
            path = Path(path)
            for file in files:
                file_path = path/file
                file_stat = file_path.stat()
                file_path.lchmod(file_stat.st_mode & file_mask)

    @classmethod
    def _hash_dict(cls, mapping):
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
                hash_obj.update(cls._hash_dict(val))

        return hash_obj.digest()

    @classmethod
    def _hash_file(cls, path):
        """Hash the given file (which is assumed to exist).
        :param Path path: Path to the file to hash.
        """

        hash_obj = hashlib.sha256()

        with path.open('rb') as file:
            chunk = file.read(cls._BLOCK_SIZE)
            while chunk:
                hash_obj.update(chunk)
                chunk = file.read(cls._BLOCK_SIZE)

        return hash_obj.digest()

    @classmethod
    def _hash_io(cls, contents):
        """Hash the given file in IOString format.
        :param IOString contents: file name (as relative path to build
                                  directory) and file contents to hash."""

        hash_obj = hashlib.sha256()
        chunk = contents.read(cls._BLOCK_SIZE)
        while chunk:
            hash_obj.update(chunk)
            chunk = contents.read(cls._BLOCK_SIZE)

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
    def _isurl(url):
        """Determine if the given path is a url."""
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme != ''

    def _download_path(self, loc, filename):
        """Get the path to where a source_download would be downloaded.
        :param str loc: The url for the download, from the config's
            source_location field.
        :param str filename: The name of the download, from the config's
            source_download_name field."""

        if filename is None:
            url_parts = urllib.parse.urlparse(loc)
            path_parts = url_parts.path.split('/')
            if path_parts and path_parts[-1]:
                filename = path_parts[-1]
            else:
                # Use a hash of the url if we can't get a name from it.
                filename = hashlib.sha256(loc.encode()).hexdigest()

        return self._pav_cfg.working_dir/'downloads'/filename

    def _find_file(self, file, sub_dir=None):
        """Look for the given file and return a full path to it. Relative paths
        are searched for in all config directories under 'test_src'.

:param Path file: The path to the file.
:param str sub_dir: The subdirectory in each config directory in which to
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

    def __hash__(self):
        """Having a comparison operator breaks hashing."""
        return id(self)

    def __eq__(self, other):
        if not isinstance(other, TestBuilder):
            raise ValueError("Can only compare a builder instance with another"
                             "builder instance.")

        compare_keys = [
            'name',
            '_timeout',
            '_script_path',
            'path',
            'fail_path'
        ]

        if self is other:
            return True

        compares = [getattr(self, key) == getattr(other, key)
                    for key in compare_keys]
        return all(compares)
