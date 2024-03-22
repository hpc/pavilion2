"""Contains the object for tracking multi-threaded builds, along with
the TestBuilder class itself."""

# pylint: disable=too-many-lines

import glob
import hashlib
import io
import os
import shutil
import stat
import subprocess
import tarfile
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Union, Dict, Optional
from contextlib import ExitStack

import pavilion.config
import pavilion.errors
from pavilion import extract, lockfile, utils, wget, create_files
from pavilion.build_tracker import BuildTracker
from pavilion.lockfile import FuzzyLock
from pavilion.errors import TestBuilderError, TestConfigError
from pavilion.status_file import TestStatusFile, STATES
from pavilion.test_config import parse_timeout
from pavilion.test_config.spack import SpackEnvConfig


class TestBuilder:
    """Manages a test build and their organization.

    :cvar int _BLOCK_SIZE: Chunk size when reading and hashing files.
    :cvar int BUILD_HASH_BYTES: Number of bytes in the build hash (1/2 the
        chars)
    :cvar str DEPRECATED: The name of the build deprecation file.
    :ivar Path ~.path: The intended location of this build in the build
        directory.
    :ivar Path fail_path: Where this build will be placed if it fails.
    :ivar str name: The name of this build."""

    _BLOCK_SIZE = 4096*1024

    # We have to worry about hash collisions, but we don't need all the bytes
    # of hash most algorithms give us. The birthday attack math for 64 bits (
    # 8 bytes) of hash and 10 million items yields a collision probability of
    # just 0.00027%. Easily good enough.
    BUILD_HASH_BYTES = 8

    DEPRECATED = ".pav_deprecated_build"
    FINISHED_SUFFIX = '.finished'

    LOG_NAME = "pav_build_log"

    def __init__(self, pav_cfg: pavilion.config.PavConfig, working_dir: Path, config: dict,
                 script: Path, status: TestStatusFile, download_dest: Path,
                 templates: Dict[Path, Path] = None,
                 spack_config: dict = None, build_name=None):
        """Initialize the build object.

        :param pav_cfg: The Pavilion config object
        :param working_dir: The working directory where this build should go.
        :param config: The build configuration.
        :param script: Path to the build script
        :param templates: Paths to template files and their destinations.
        :param spack_config: Give a spack config to enable spack builds.
        :param build_name: The build name, if this is a build that already exists.
        :raises TestBuilderError: When the builder can't be initialized.
        """

        self._pav_cfg = pav_cfg
        self._config = config
        self._spack_config = spack_config
        self._script_path = script
        self._download_dest = download_dest
        self._templates: Dict[Path, Path] = templates or {}
        self._build_hash = None

        try:
            self._timeout = parse_timeout(config.get('timeout'))
        except ValueError:
            raise TestBuilderError("Build timeout must be a positive integer or null, "
                                   "got '{}'".format(config.get('timeout')))

        self.status = status

        self._timeout_file = config.get('timeout_file')

        self._fix_source_path()

        self._version = 1

        if build_name is None:
            self.name = self.name_build()
        else:
            self.name = build_name

        self.path = working_dir/'builds'/self.name  # type: Path

        if not self.path.exists():
            status.set(state=STATES.BUILD_CREATED, note="Builder created.")

        self.tmp_log_path = self.path.with_suffix('.log')
        self.log_path = self.path/self.LOG_NAME
        fail_name = 'fail.{}.{}'.format(self.name, time.time())
        self.fail_path = self.path.parent/fail_name
        self.finished_path = self.path.with_suffix(self.FINISHED_SUFFIX)

        if self._timeout_file is not None:
            self._timeout_file = self.path/self._timeout_file
        else:
            self._timeout_file = self.tmp_log_path

        # Verify template and file creation destinations
        for file in self._config.get('create_files', {}).keys():
            try:
                create_files.verify_path(file, self.path)
            except TestConfigError as err:
                raise TestBuilderError("build.create_file has bad path '{}'".format(file), err)

        for tmpl, dest in self._config.get('templates', {}).items():
            try:
                create_files.verify_path(tmpl, self.path)
            except TestConfigError as err:
                raise TestBuilderError("build.create_file has bad template path '{}'"
                                       .format(tmpl), err)
            try:
                create_files.verify_path(dest, self.path)
            except TestConfigError as err:
                raise TestBuilderError("build.create_file has bad destination path '{}'"
                                       .format(dest), err)

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

    @property
    def build_hash(self) -> str:
        """Get the cached build hash, if it exists. Otherwise,
        create it and cache it."""
        if self._build_hash is None:
            self._build_hash = self._create_build_hash()

        return self._build_hash

    def _create_build_hash(self) -> str:
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
        hash_obj.update(self._hash_file(self._script_path, save=False))

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

        # Hash all the given template files.
        for tmpl_src in sorted(self._templates.keys()):
            hash_obj.update(self._hash_file(tmpl_src))

        # Hash extra files.
        for extra_file in self._config.get('extra_files', []):
            extra_file = Path(extra_file)
            full_path = self._pav_cfg.find_file(extra_file, Path('test_src'))

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
        for file, contents in self._config.get('create_files', {}).items():
            with io.StringIO() as io_contents:
                io_contents.write("{}\n".format(file))
                create_files.write_file(contents, io_contents)
                hash_obj.update(self._hash_io(io_contents))

        hash_obj.update(self._config.get('specificity', '').encode())

        return hash_obj.hexdigest()[:self.BUILD_HASH_BYTES*2]

    def name_build(self) -> str:
        """Search for the first non-deprecated version of this build (whether
        or not it exists) and name the build for it."""

        base_hash = self.build_hash

        builds_dir = self._pav_cfg.working_dir/'builds'
        name = base_hash
        path = builds_dir/name

        while path.exists() and (path/self.DEPRECATED).exists():
            self._version += 1
            name = self.rehash_name(name)
            path = builds_dir/name

        return name

    @classmethod
    def rehash_name(cls, name: str) -> str:
        """Rehash the given build name with the given version."""

        rehash = hashlib.sha256(name.encode())
        return rehash.hexdigest()[:cls.BUILD_HASH_BYTES*2]

    def rename_build(self):
        """Rechecks deprecation and updates the build name."""

        self.name = self.name_build()
        self.path = self._pav_cfg.working_dir/'builds'/self.name  # type: Path
        fail_name = 'fail.{}.{}'.format(self.name, time.time())
        self.fail_path = self.path.parent/fail_name
        self.finished_path = self.path.with_suffix(self.FINISHED_SUFFIX)

    def deprecate(self):
        """Deprecate this build, so that it will be rebuilt if any other
        test run wants to use it.
        """

        dep_tmp_path = self.path/'.dep_tmp-{}'.format(time.time())
        dep_path = self.path/self.DEPRECATED
        if dep_path.exists():
            return

        dep_path.touch()

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
                "or absolute, got '{}'".format(src_path), err)

        found_src_path = self._pav_cfg.find_file(src_path, 'test_src')

        src_url = self._config.get('source_url')
        src_download = self._config.get('source_download')

        if (src_url is not None
                and ((src_download == 'missing' and found_src_path is None)
                     or src_download == 'latest')):

            if self._download_dest is None:
                raise TestBuilderError(
                    """Cannot update source, no download directory available."""
                )

            if not self._download_dest.exists():
                self._download_dest.mkdir(parents=True)

            # Make sure we have the library support to perform a download.
            missing_libs = wget.missing_libs()
            if missing_libs:
                raise TestBuilderError(
                    "The dependencies needed for remote source retrieval "
                    "({}) are not available on this system. Please provide "
                    "your test source locally."
                    .format(', '.join(missing_libs)))

            if not src_path.is_absolute():
                dwn_dest = self._download_dest/src_path
            else:
                dwn_dest = src_path

            if not dwn_dest.parent.exists():
                try:
                    dwn_dest.parent.mkdir(parents=True)
                except OSError as err:
                    raise TestBuilderError(
                        "Could not create parent directory to place "
                        "downloaded source:\n{}".format(err))

            self.status.set(STATES.BUILDING,
                            "Updating source at '{}'.".format(found_src_path))

            try:
                wget.update(self._pav_cfg, src_url, dwn_dest)
            except pavilion.errors.WGetError as err:
                raise TestBuilderError(
                    "Could not retrieve source from the given url '{}'".format(src_url), err)

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

    def _remove_existing_path(self, tracker: BuildTracker) -> bool:
        """Attempt to remove the path associated with the build,
        and report, as a boolean, whether the removal was successful."""

        tracker.warn(
            "Build lock acquired, but build exists that was "
            "not marked as finished. Deleting...")
        try:
            shutil.rmtree(self.path)
        except OSError as err:
            tracker.error(
                "Could not remove unfinished build.\n{}"
                .format(err))

            return False

        return True

    def _name_failed_path(self, cancel_event: Optional[threading.Event],
         tracker: BuildTracker) -> None:
        """Rename the path associated with the build to indicate build failure,
        and cancel other threads or processes working on the same build."""

        try:
            self.path.rename(self.fail_path)
        except FileNotFoundError as err:
            tracker.error(
                "Failed to move build {} from {} to "
                "failure path {}"
                .format(self.name, self.path,
                        self.fail_path), err)
            try:
                self.fail_path.mkdir()
            except OSError as err2:
                tracker.error(
                    "Could not create fail directory for "
                    "build {} at {}"
                    .format(self.name, self.fail_path, err2))

        if cancel_event is not None:
            cancel_event.set()

    def build(self, test_id: str, tracker: BuildTracker,
              cancel_event: threading.Event = None):
        """Perform the build if needed, do a soft-link copy of the build
        directory into our test directory, and note that we've used the given
        build.

        :param test_id: The test 'full_id' for the test initiating this build.
        :param tracker: A thread-safe tracker object for keeping info on what the
            build is doing.
        :param cancel_event: Allows builds to tell each other
            to die.
        :return: True if these steps completed successfully.
        """

        if not self.finished_path.exists():
            # Make sure another test doesn't try to do the build at
            # the same time.
            # Note cleanup of failed builds HAS to occur under this lock to
            # avoid a race condition, even though it would be way simpler to
            # do it in .build()

            tracker.update(
                state=STATES.BUILD_WAIT,
                note="Waiting on lock for build {}.".format(self.name))

            mb_tracker = tracker.tracker
            locks = [mb_tracker.make_lock_context(self.build_hash)]

            # Only use FuzzyLock if building on nodes
            if self._pav_cfg.get('build', {}).get('on_nodes', 'false').lower() == 'true':
                locks.append(FuzzyLock(self.path.parent / f"{self.name}.lock"))

            # Allows for variable number of locks
            with ExitStack() as stack:
                for lock in locks:
                    stack.enter_context(lock)

                # Make sure the build wasn't created while we waited for
                # the lock.
                if not self.finished_path.exists():
                    tracker.update(
                        state=STATES.BUILDING,
                        note="Starting build {}.".format(self.name))

                    # If the build directory exists, we're assuming there was
                    # an incomplete build at this point.
                    if self.path.exists():
                        if not self._remove_existing_path(tracker):
                            return False

                    if not self._build(self.path, cancel_event, test_id, tracker):
                        self._name_failed_path(cancel_event, tracker)
                        return False

                    try:
                        self.finished_path.touch()
                    except OSError:
                        tracker.warn("Could not touch '<build>.finished' file.")

                else:
                    tracker.update(
                        state=STATES.BUILD_REUSED,
                        note="Build {s.name} created while waiting for build "
                            "lock.".format(s=self))

        else:
            tracker.update(
                note=("Build {s.name} is being reused.".format(s=self)),
                state=STATES.BUILD_REUSED)

        return True

    def create_spack_env(self, build_dir):
        """Creates a spack.yaml file in the build dir, so that each unique
        build can activate it's own spack environment."""

        spack_config = self._spack_config

        spack_path = self._pav_cfg['spack_path']
        spack_dir = spack_path/'opt'/'spack'

        # Set up upstreams, will always have 'main', so that builds in the
        # global spack instance can be reused.
        upstreams = {
            'main': {
                'install_tree': spack_dir
            }
        }
        upstreams.update(spack_config.get('upstreams', {}))

        # Set the spack env based on the passed spack_config and build_dir.
        config = {
            'spack': {
                'config': {
                    # New spack installs will be built in the specified
                    # build_dir.
                    'install_tree': str(build_dir/'spack_installs'),
                    'install_path_scheme': "{name}-{version}-{hash}",
                    'build_jobs': spack_config.get('build_jobs', 6)
                },
                'mirrors': spack_config.get('mirrors', {}),
                'repos': spack_config.get('repos', []),
                'upstreams': upstreams,
            },
        }

        # Create the spack.yaml file with the updated configs.
        spack_env_config = build_dir/'spack.yaml'
        with open(spack_env_config.as_posix(), "w+") as spack_env_file:
            SpackEnvConfig().dump(spack_env_file, values=config,)

    def _build(self, build_dir, cancel_event, test_id, tracker: BuildTracker) -> bool:
        """Perform the build. This assumes there actually is a build to perform.
        :param Path build_dir: The directory in which to perform the build.
        :param threading.Event cancel_event: Event to signal that the build
            should stop.
        :param test_id: The 'full_id' of the test initiating the build.
        :param tracker: Build tracker for this build.
        :returns: True or False, depending on whether the build appears to have
            been successful.
        """

        try:
            self._setup_build_dir(build_dir, tracker)
        except TestBuilderError as err:
            tracker.error(
                note=("Error setting up build directory '{}': {}"
                      .format(build_dir, err)))
            return False

        # Generate an anonymous spack environment for a new build.
        if self._spack_config is not None:
            self.create_spack_env(build_dir)

        try:
            # Do the build, and wait for it to complete.
            with self.tmp_log_path.open('w') as build_log:
                # Build scripts take the test id as a first argument.
                cmd = [self._script_path.as_posix(), test_id]
                proc = subprocess.Popen(cmd,
                                        cwd=build_dir.as_posix(),
                                        stdout=build_log,
                                        stderr=build_log)

                result = None
                timeout = time.time() + self._timeout
                while result is None:
                    try:
                        result = proc.wait(timeout=0.2)
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
                            tracker.fail(
                                state=STATES.BUILD_TIMEOUT,
                                note="Build timed out after {} seconds."
                                .format(self._timeout))
                            return False

                        if cancel_event is not None and cancel_event.is_set():
                            proc.kill()
                            tracker.update(
                                state=STATES.ABORTED,
                                note="Build canceled due to other builds "
                                     "failing.")
                            return False

        except subprocess.CalledProcessError as err:
            tracker.error(
                note="Error running build process: {}".format(err))
            return False

        except (IOError, OSError) as err:

            tracker.error(
                note="Error that's probably related to writing the "
                     "build output: {}".format(err))
            return False
        finally:
            try:
                self.tmp_log_path.rename(build_dir/self.LOG_NAME)
            except OSError as err:
                tracker.warn(
                    "Could not move build log from '{}' to final location '{}': {}"
                    .format(self.tmp_log_path, build_dir, err))

        try:
            self._fix_build_permissions(build_dir)
        except OSError as err:
            tracker.warn("Error fixing build permissions: %s".format(err))

        if result != 0:
            tracker.fail(
                note="Build returned a non-zero result.")
            if cancel_event is not None:
                cancel_event.set()
            return False
        else:

            tracker.update(
                state=STATES.BUILD_SUCCESS,
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

    def _setup_build_dir(self, dest, tracker: BuildTracker):
        """Setup the build directory, by extracting or copying the source
            and any extra files.
        :param dest: Path to the intended build directory. This is generally a
            temporary location.
        :param tracker: Build tracker for this build.
        :return: None
        """

        umask = os.umask(0)
        os.umask(umask)

        raw_src_path = self._config.get('source_path')
        if raw_src_path is None:
            src_path = None
        else:
            src_path = self._pav_cfg.find_file(Path(raw_src_path), 'test_src')
            if src_path is None:
                raise TestBuilderError("Could not find source file '{}'"
                                       .format(raw_src_path))

            # Resolve any softlinks to get the real file.
            src_path = src_path.resolve()

        umask = int(self._pav_cfg['umask'], 8)

        # All of the file extraction functions return an error message on failure, None on success.
        extract_error = None

        if src_path is None:
            # If there is no source archive or data, just make the build
            # directory.
            dest.mkdir()

        elif src_path.is_dir():
            # Recursively copy the src directory to the build directory.
            tracker.update(
                state=STATES.BUILDING,
                note=("Copying source directory {} for build {} "
                      "as the build directory."
                      .format(src_path, dest)))

            utils.copytree(
                src_path.as_posix(),
                dest.as_posix(),
                copy_function=shutil.copyfile,
                copystat=utils.make_umask_filtered_copystat(umask),
                symlinks=True)

        elif src_path.is_file():
            category, subtype = utils.get_mime_type(src_path)

            if category == 'application' and subtype in self.TAR_SUBTYPES:

                if tarfile.is_tarfile(src_path.as_posix()):
                    tracker.update(
                        state=STATES.BUILDING,
                        note=("Extracting tarfile {} for build {}"
                              .format(src_path, dest)))
                    extract_error = extract.extract_tarball(src_path, dest, umask)
                else:
                    tracker.update(
                        state=STATES.BUILDING,
                        note=(
                            "Extracting {} file {} for build {} into the "
                            "build directory."
                            .format(subtype, src_path, dest)))
                    extract_error = extract.decompress_file(src_path, dest, subtype)
            elif category == 'application' and subtype == 'zip':
                tracker.update(
                    state=STATES.BUILDING,
                    note=("Extracting zip file {} for build {}."
                          .format(src_path, dest)))
                extract_error = extract.unzip_file(src_path, dest)

            else:
                # Finally, simply copy any other types of files into the build
                # directory.
                tracker.update(
                    state=STATES.BUILDING,
                    note="Copying file {} for build {} into the build "
                         "directory.".format(src_path, dest))

                copy_dest = dest / src_path.name
                try:
                    dest.mkdir()
                    shutil.copy(src_path.as_posix(), copy_dest.as_posix())
                except OSError as err:
                    raise TestBuilderError(
                        "Could not copy test src '{}' to '{}'"
                        .format(src_path, dest), err)

        if extract_error is not None:
            raise TestBuilderError("Error extracting file '{}'\n  {}"
                                   .format(src_path.as_posix(), extract_error))

        tracker.update(
            state=STATES.BUILDING,
            note="Generating dynamically created files.")

        # Create build time file(s).
        for file, contents in self._config.get('create_files', {}).items():
            try:
                create_files.create_file(file, self.path, contents)
            except TestConfigError as err:
                raise TestBuilderError(
                    "Error creating 'create_file' '{}'"
                    .format(file), err)

        # Copy over the template files.
        for tmpl_src, tmpl_dest in self._templates.items():
            tmpl_dest = self.path/tmpl_dest
            try:
                tmpl_dest.parent.mkdir(exist_ok=True)
                shutil.copyfile(tmpl_src, tmpl_dest)
            except OSError as err:
                raise TestBuilderError(
                    "Error copying template file from {} to {}"
                    .format(tmpl_src, tmpl_dest), err)

        # Now we just need to copy over all the extra files.
        for extra in self._config.get('extra_files', []):
            extra = Path(extra)
            path = self._pav_cfg.find_file(extra, 'test_src')
            final_dest = dest / path.name
            try:
                if path.is_dir():
                    utils.copytree(
                        path.as_posix(),
                        final_dest.as_posix(),
                        copy_function=shutil.copyfile,
                        copystat=utils.make_umask_filtered_copystat(umask),
                        symlinks=True)
                else:
                    shutil.copyfile(path.as_posix(), final_dest.as_posix())
            except OSError as err:
                raise TestBuilderError(
                    "Could not copy extra file '{}' to dest '{}'"
                    .format(path, dest), err)

    def copy_build(self, dest: Path):
        """Copy the build (using 'symlink' copying to the destination.

        :param dest: Where to copy the build to.
        :raises TestBuilderError: When copy errors happen
        :returns: True on success, False on failure
        """

        start = time.time()

        do_copy = set()
        copy_globs = self._config.get('copy_files', [])
        for copy_glob in copy_globs:
            final_glob = self.path.as_posix() + '/' + copy_glob
            blob = glob.glob(final_glob, recursive=True)
            if not blob:
                avail = '\n'.join(glob.glob(final_glob.rsplit('/')[0]))
                raise TestBuilderError(
                    "Could not perform build copy. Files meant to be fully copied ("
                    "rather than symlinked) could not be found:\n"
                    "base_glob: {}\n"
                    "full_glob: {}\n"
                    "These files were available in the top glob dir"
                    .format(copy_glob, final_glob, avail))

            do_copy.update(blob)

        def maybe_symlink_copy(src, dst):
            """Makes a symlink from src to dst, unless the file is in
            the list of files to do a regular copy on.
            """

            if src in do_copy:
                # Actually copy files that were explicitly asked for.
                cpy_path = shutil.copy2(src, dst)
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
            raise TestBuilderError(
                "Could not perform the build directory copy".format(err))

        # Touch the original build directory, so that we know it was used
        # recently.
        try:
            now = time.time()
            os.utime(self.path.as_posix(), (now, now))
        except OSError as err:
            self.status.set(
                STATES.WARNING,
                "Could not update timestamp on build directory '%s': %s"
                .format(self.path, err))

        self.status.set(STATES.BUILD_COPIED,
                        "Performed symlink copy in {:0.2f}s."
                        .format(time.time() - start))

        return True

    def _fix_build_permissions(self, root_path):
        """The files in a build directory should never be writable, but
            directories should be. Users are thus allowed to delete build
            directories and their files, but never modify them. Additions,
            deletions within test build directories will effect the soft links,
            not the original files themselves. (This applies both to owner and
            group).
        :raises OSError: If we lack permissions or something else goes wrong."""

        _ = self

        # We rely on the umask to handle most restrictions.
        # This just masks out the write bits.
        file_mask = 0o222

        for path, dirs, files in os.walk(root_path.as_posix()):
            path = Path(path)
            # Clear the write bits on all files
            for file in files:
                file_path = path/file
                file_stat = file_path.stat()
                file_path.chmod(file_stat.st_mode & ~file_mask)

            # and set them aon all directories (if needed).
            path_mode = path.stat().st_mode
            if (path_mode & 0o220) != 0o220:
                path.chmod(path_mode | 0o220)

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

        stat_ = path.stat()
        hash_fn = path.with_name('.' + path.name + '.hash')

        # Read the has from the hashfile as long as it was created after
        # our test source's last update.
        if hash_fn.exists() and hash_fn.stat().st_mtime > stat_.st_mtime:
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
            with hash_fn.open('wb') as hash_file:
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

    @staticmethod
    def _date_dir(base_path):
        """Update the mtime of the given directory or path to the the latest
        mtime contained within.
        :param Path base_path: The root of the path to evaluate.
        """

        src_stat = base_path.stat()
        latest = src_stat.st_mtime

        for path in utils.flat_walk(base_path):
            try:
                dir_stat = path.stat()
            except OSError as err:
                raise TestBuilderError(
                    "Could not stat file in test source dir '{}'"
                    .format(base_path), err)
            if dir_stat.st_mtime > latest:
                latest = dir_stat.st_mtime

        if src_stat.st_mtime != latest:
            os.utime(base_path.as_posix(), (src_stat.st_atime, latest))

    def __hash__(self):
        """Having a comparison operator breaks hashing."""
        return id(self)

    def __eq__(self, other):
        if not isinstance(other, TestBuilder):
            raise ValueError("Can only compare a builder instance with another "
                             "builder instance.")

        compare_keys = [
            'name',
            '_timeout',
            '_script_path',
            'path',
        ]

        if self is other:
            return True

        compares = [getattr(self, key) == getattr(other, key)
                    for key in compare_keys]
        return all(compares)
