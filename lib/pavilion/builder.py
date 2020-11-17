"""Contains the object for tracking multi-threaded builds, along with
the TestBuilder class itself."""

import datetime
import glob
import hashlib
import io
import logging
import os
import shutil
import subprocess
import stat
import tarfile
import threading
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Union, List

from pavilion import dir_db
from pavilion import extract
from pavilion import lockfile
from pavilion import utils
from pavilion import wget
from pavilion.permissions import PermissionsManager
from pavilion.status_file import STATES


class TestBuilderError(RuntimeError):
    """Exception raised when builds encounter an error."""


class MultiBuildTracker:
    """Allows for the central organization of multiple build tracker objects.
        :ivar {StatusFile} status_files: The dictionary of status
            files by build.
    """

    def __init__(self, log=True):
        """Setup the build tracker.
       :param bool log: Whether to also log messages in some instances.
        """

        # A map of build tokens to build names
        self.messages = {}
        self.status = {}
        self.status_files = {}
        self.lock = threading.Lock()

        self.logger = None
        if log:
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

        if log is not None and self.logger:
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
    FINISHED_SUFFIX = '.finished'

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
            mb_tracker = MultiBuildTracker(log=False)
        self.tracker = mb_tracker.register(self, test.status)

        self._pav_cfg = pav_cfg
        self._config = test.config.get('build', {})
        self._group = test.group
        self._umask = test.umask
        self._script_path = test.build_script_path
        self.test = test
        self._timeout = test.build_timeout
        self._timeout_file = test.build_timeout_file

        self._fix_source_path()

        if not test.build_local:
            self.tracker.update(state=STATES.BUILD_DEFERRED,
                                note="Build will run on nodes.")

        if build_name is None:
            self.name = self.name_build()
            self.tracker.update(state=STATES.BUILD_CREATED,
                                note="Builder created.")
        else:
            self.name = build_name

        self.path = pav_cfg.working_dir/'builds'/self.name  # type: Path
        self.tmp_log_path = self.path.with_suffix('.log')
        self.log_path = self.path/self.LOG_NAME
        fail_name = 'fail.{}.{}'.format(self.name, self.test.id)
        self.fail_path = pav_cfg.working_dir/'builds'/fail_name
        self.finished_path = self.path.with_suffix(self.FINISHED_SUFFIX)

        if self._timeout_file is not None:
            self._timeout_file = self.path/self._timeout_file
        else:
            self._timeout_file = self.tmp_log_path

        # Don't allow a file to be written outside of the build context dir.
        files_to_create = self._config.get('create_files')
        if files_to_create:
            for file, contents in files_to_create.items():
                file_path = Path(utils.resolve_path(self.path / file))
                if not utils.dir_contains(file_path,
                                          utils.resolve_path(self.path)):
                    raise TestBuilderError("'create_file: {}': file path"
                                           " outside build context."
                                           .format(file_path))

    def exists(self):
        """Return True if the given build exists."""
        return self.path.exists()

    DOWNLOAD_HASH_SIZE = 13

    def _fix_source_path(self):
        """Create a source path from the url if one wasn't given. These will
        be put in a .downloads directory under test_src."""

        src_path = self._config.get('source_path')
        src_url = self._config.get('source_url')

        if src_path is None and src_url is not None:
            url_hash = hashlib.sha256(src_url.encode()).hexdigest()
            src_path = '.downloads/' + url_hash[:self.DOWNLOAD_HASH_SIZE]
            self._config['source_path'] = src_path

    def log_updated(self) -> Union[float, None]:
        """Return the last time the build log was updated. Simply returns
        None if the log can't be found or read."""

        # The log will be here during the build.
        if self.tmp_log_path.exists():
            try:
                return self.tmp_log_path.stat().st_mtime
            except OSError:
                # This mostly for the race condition, but will also handle
                # any permission problems.
                pass

        # After the build, the log will be here.
        if self.log_path.exists():
            try:
                return self.log_path.stat().st_mtime
            except OSError:
                return None

    def create_build_hash(self):
        """Turn the build config, and everything the build needs, into a hash.
        This includes the build config itself, the source tarball, and all
        extra files."""

        # The hash order is:
        #  - The build script
        #  - The build specificity
        #  - The build group and umask
        #  - The src archive.
        #    - For directories, the mtime (updated to the time of the most
        #      recently updated file) is hashed instead.
        #  - All of the build's 'extra_files'
        #  - All files needed to be created at build time 'create_files'

        hash_obj = hashlib.sha256()

        # Update the hash with the contents of the build script.
        hash_obj.update(self._hash_file(self._script_path, save=False))
        group = self._group.encode() if self._group is not None else b'<def>'
        hash_obj.update(group)
        umask = oct(self._umask).encode() if self._umask is not None \
            else b'<def>'
        hash_obj.update(umask)

        specificity = self._config.get('specificity', '')
        hash_obj.update(specificity.encode('utf8'))

        # Update the source and get the final source path.
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

        hash_obj.update(self._config.get('specificity', '').encode())

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
        self.finished_path = self.path.with_suffix(self.FINISHED_SUFFIX)

    def deprecate(self):
        """Deprecate this build, so that it will be rebuilt if any other
        test run wants to use it."""

        deprecated_path = self.path/self.DEPRECATED
        deprecated_path.touch()

    def _update_src(self):
        """Retrieve and/or check the existence of the files needed for the
            build. This can include pulling from URL's.
        :returns: src_path, extra_files
        """

        src_path = self._config.get('source_path')
        if src_path is None:
            # There is no source to do anything with.
            return None

        try:
            src_path = Path(src_path)
        except ValueError as err:
            raise TestBuilderError(
                "The source path must be a valid unix path, either relative "
                "or absolute, got '{}':\n{}"
                .format(src_path, err.args[0]))

        found_src_path = self._find_file(src_path, 'test_src')

        src_url = self._config.get('source_url')
        src_download = self._config.get('source_download')

        if (src_url is not None
                and ((src_download == 'missing' and found_src_path is None)
                     or src_download == 'latest')):

            # Make sure we have the library support to perform a download.
            missing_libs = wget.missing_libs()
            if missing_libs:
                raise TestBuilderError(
                    "The dependencies needed for remote source retrieval "
                    "({}) are not available on this system. Please provide "
                    "your test source locally."
                    .format(', '.join(missing_libs)))

            if not src_path.is_absolute():
                dwn_dest = self.test.suite_path.parents[1]/'test_src'/src_path
            else:
                dwn_dest = src_path

            if not src_path.parent.exists():
                try:
                    src_path.parent.mkdir(parents=True)
                except OSError as err:
                    raise TestBuilderError(
                        "Could not create parent directory to place "
                        "downloaded source:\n{}".format(err.args[0]))

            self.tracker.update("Updating source at '{}'."
                                .format(found_src_path),
                                STATES.BUILDING)

            try:
                wget.update(self._pav_cfg, src_url, dwn_dest)
            except wget.WGetError as err:
                raise TestBuilderError(
                    "Could not retrieve source from the given url '{}':\n{}"
                    .format(src_url, err.args[0]))

            return dwn_dest

        if found_src_path is None:
            raise TestBuilderError(
                "Could not find source '{}'".format(src_path.as_posix()))

        if found_src_path.is_dir():
            # For directories, update the directories mtime to match the
            # latest mtime in the entire directory.
            self._date_dir(found_src_path)
            return found_src_path

        elif found_src_path.is_file():
            # For static files, we'll end up just hashing the whole thing.
            return found_src_path

        else:
            raise TestBuilderError(
                "Source location '{}' points to something unusable."
                .format(found_src_path))

    def build(self, cancel_event=None):
        """Perform the build if needed, do a soft-link copy of the build
        directory into our test directory, and note that we've used the given
        build.
        :param threading.Event cancel_event: Allows builds to tell each other
        to die.
        :return: True if these steps completed successfully.
        """

        # Only try to do the build if it doesn't already exist and is finished.
        if not self.finished_path.exists():
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
                if not self.finished_path.exists():
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note="Starting build {}.".format(self.name))

                    # If the build directory exists, we're assuming there was
                    # an incomplete build at this point.
                    if self.path.exists():
                        self.tracker.warn(
                            "Build lock acquired, but build exists that was "
                            "not marked as finished. Deleting...")
                        try:
                            shutil.rmtree(self.path)
                        except OSError as err:
                            self.tracker.error(
                                "Could not remove unfinished build.\n{}"
                                .format(err.args[0]))
                            return False

                    # Attempt to perform the actual build, this shouldn't
                    # raise an exception unless something goes terribly
                    # wrong.
                    # This will also set the test status for
                    # non-catastrophic cases.
                    with PermissionsManager(self.path, self._group,
                                            self._umask):
                        if not self._build(self.path, cancel_event):

                            try:
                                self.path.rename(self.fail_path)
                            except FileNotFoundError as err:
                                self.tracker.error(
                                    "Failed to move build {} from {} to "
                                    "failure path {}: {}"
                                    .format(self.name, self.path,
                                            self.fail_path, err))
                                self.fail_path.mkdir()
                            if cancel_event is not None:
                                cancel_event.set()

                            return False

                    # Make a file with the test id of the building test.
                    built_by_path = self.path / '.built_by'
                    try:
                        with PermissionsManager(built_by_path, self._group,
                                                self._umask | 0o222), \
                                built_by_path.open('w') as built_by:
                            built_by.write(str(self.test.id))
                    except OSError:
                        self.tracker.warn("Could not create built_by file.")

                    try:
                        with PermissionsManager(self.finished_path,
                                                self._group, self._umask):
                            self.finished_path.touch()
                    except OSError:
                        self.tracker.warn("Could not touch '<build>.finished' "
                                          "file.")

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

        try:
            # Do the build, and wait for it to complete.
            with self.tmp_log_path.open('w') as build_log:
                # Build scripts take the test id as a first argument.
                cmd = [self._script_path.as_posix(), str(self.test.id)]
                proc = subprocess.Popen(cmd,
                                        cwd=build_dir.as_posix(),
                                        stdout=build_log,
                                        stderr=build_log)

                result = None
                timeout = self._timeout
                while result is None:
                    try:
                        result = proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        if self._timeout_file.exists():
                            timeout_file = self._timeout_file
                        else:
                            timeout_file = self.tmp_log_path

                        try:
                            timeout = max(
                                timeout,
                                timeout_file.stat().st_mtime + self._timeout)
                        except OSError:
                            pass

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
                self.tmp_log_path.rename(build_dir/self.LOG_NAME)
            except OSError as err:
                self.tracker.warn(
                    "Could not move build log from '{}' to final location "
                    "'{}': {}"
                    .format(self.tmp_log_path, build_dir, err))

        try:
            self._fix_build_permissions(build_dir)
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

        raw_src_path = self._config.get('source_path')
        if raw_src_path is None:
            src_path = None
        else:
            src_path = self._find_file(Path(raw_src_path), 'test_src')
            if src_path is None:
                raise TestBuilderError("Could not find source file '{}'"
                                       .format(raw_src_path))

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
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note=("Extracting tarfile {} for build {}"
                              .format(src_path, dest)))
                    extract.extract_tarball(src_path, dest)
                else:
                    self.tracker.update(
                        state=STATES.BUILDING,
                        note=(
                            "Extracting {} file {} for build {} into the "
                            "build directory."
                            .format(subtype, src_path, dest)))
                    extract.decompress_file(src_path, dest, subtype)
            elif category == 'application' and subtype == 'zip':
                self.tracker.update(
                    state=STATES.BUILDING,
                    note=("Extracting zip file {} for build {}."
                          .format(src_path, dest)))
                extract.unzip_file(src_path, dest)

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

        # Create build time file(s).
        files_to_create = self._config.get('create_files')
        if files_to_create:
            for file, contents in files_to_create.items():
                file_path = Path(utils.resolve_path(dest / file))
                # Do not allow file to clash with existing directory.
                if file_path.is_dir():
                    raise TestBuilderError("'create_file: {}' clashes with"
                                           " existing directory in test source."
                                           .format(str(file_path)))
                dirname = file_path.parent
                (dest / dirname).mkdir(parents=True, exist_ok=True)
                with file_path.open('w') as file_:
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
            final_glob = self.path.as_posix() + '/' + copy_glob
            blob = glob.glob(final_glob, recursive=True)
            if not blob:
                avail = '\n'.join(glob.glob(final_glob.rsplit('/')[0]))
                self.tracker.error(
                    state=STATES.BUILD_ERROR,
                    note=("Could not perform build copy. Files meant to be "
                          "fully copied (rather than symlinked) could not be "
                          "found:\n"
                          "base_glob: {}\n"
                          "full_glob: {}\n"
                          "These files were available in the top glob dir:\n"
                          "{}"
                          .format(copy_glob, final_glob, avail)))
                return False

            do_copy.update(blob)

        def maybe_symlink_copy(src, dst):
            """Makes a symlink from src to dst, unless the file is in
            the list of files to do a regular copy on.
            """

            if src in do_copy:
                # Actually copy files that were explicitly asked for.
                cpy_path = shutil.copy2(src, dst, follow_symlinks=True)
                base_mode = os.stat(cpy_path).st_mode
                os.chmod(cpy_path, base_mode | stat.S_IWUSR | stat.S_IWGRP)
                return cpy_path
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
                state=STATES.BUILD_ERROR,
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

    def _fix_build_permissions(self, root_path):
        """The files in a build directory should never be writable, but
            directories should be. Users are thus allowed to delete build
            directories and their files, but never modify them. Additions,
            deletions within test build directories will effect the soft links,
            not the original files themselves. (This applies both to owner and
            group).
        :raises OSError: If we lack permissions or something else goes wrong."""

        # We rely on the umask to handle most restrictions.
        # This just masks out the write bits.
        file_mask = 0o222 | self._umask

        # We shouldn't have to do anything to directories, they should have
        # the correct permissions already.
        for path, dirs, files in os.walk(root_path.as_posix()):
            path = Path(path)
            for file in files:
                file_path = path/file
                file_stat = file_path.stat()
                file_path.chmod(file_stat.st_mode & ~file_mask)

    @classmethod
    def _hash_dict(cls, mapping):
        """Create a hash from the keys and items in 'mapping'. Keys are
            processed in order. Can handle lists and other dictionaries as
            values.
        :param dict mapping: The dictionary to hash.
        """

        hash_obj = hashlib.sha256()

        for key in sorted(mapping.keys()):
            hash_obj.update(str(key).encode())

            val = mapping[key]

            if isinstance(val, str):
                hash_obj.update(val.encode())
            elif isinstance(val, list):
                for item in val:
                    hash_obj.update(item.encode())
            elif isinstance(val, dict):
                hash_obj.update(cls._hash_dict(val))

        return hash_obj.digest()

    def _hash_file(self, path, save=True):
        """Hash the given file (which is assumed to exist).
        :param Path path: Path to the file to hash.
        """

        stat = path.stat()
        hash_fn = path.with_name('.' + path.name + '.hash')

        # Read the has from the hashfile as long as it was created after
        # our test source's last update.
        if hash_fn.exists() and hash_fn.stat().st_mtime > stat.st_mtime:
            try:
                with hash_fn.open('rb') as hash_file:
                    return hash_file.read()
            except OSError:
                pass

        hash_obj = hashlib.sha256()

        with path.open('rb') as file:
            chunk = file.read(self._BLOCK_SIZE)
            while chunk:
                hash_obj.update(chunk)
                chunk = file.read(self._BLOCK_SIZE)

        file_hash = hash_obj.digest()

        if save:
            # This should all be under the build lock.
            with PermissionsManager(hash_fn, self._group, self._umask), \
                    hash_fn.open('wb') as hash_file:
                hash_file.write(file_hash)

        return file_hash

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
        return '{} {:0.5f}'.format(path, dir_stat.st_mtime).encode()

    @staticmethod
    def _isurl(url):
        """Determine if the given path is a url."""
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme != ''

    def _find_file(self, file: Path, sub_dir=None) -> Union[Path, None]:
        """Look for the given file and return a full path to it. Relative paths
        are searched for in all config directories under 'test_src'.

:param file: The path to the file.
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

        for path in utils.flat_walk(base_path):
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


def _get_used_build_paths(tests_dir: Path) -> set:
    """Generate a set of all build paths currently used by one or more test
    runs."""

    used_builds = set()

    for path in dir_db.select(tests_dir)[0]:
        build_origin_symlink = path/'build_origin'
        build_origin = None
        if (build_origin_symlink.exists() and
            build_origin_symlink.is_symlink() and
                utils.resolve_path(build_origin_symlink).exists()):
            build_origin = build_origin_symlink.resolve()

        if build_origin is not None:
            used_builds.add(build_origin.name)

    return used_builds


def delete_unused(tests_dir: Path, builds_dir: Path, verbose: bool = False) \
        -> (int, List[str]):
    """Delete all the build directories, that are unused by any test run.

    :param tests_dir: The test_runs directory path object.
    :param builds_dir: The builds directory path object.
    :param verbose: Print

    :return int count: The number of builds that were removed.

    """

    used_build_paths = _get_used_build_paths(tests_dir)

    def filter_builds(build_path: Path) -> bool:
        """Return whether a build is not used."""
        return build_path.name not in used_build_paths

    count = 0

    lock_path = builds_dir.with_suffix('.lock')
    msgs = []
    with lockfile.LockFile(lock_path):
        for path in dir_db.select(builds_dir, filter_builds, fn_base=16)[0]:
            try:
                shutil.rmtree(path.as_posix())
                path.with_suffix(TestBuilder.FINISHED_SUFFIX).unlink()
            except OSError as err:
                msgs.append("Could not remove build {}: {}"
                            .format(path, err))
                continue
            count += 1
            if verbose:
                msgs.append('Removed build {}.'.format(path.name))

    return count, msgs
