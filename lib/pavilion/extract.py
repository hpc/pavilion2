import bz2
import gzip
import lzma
import os
import pathlib
import shutil
import tarfile
import zipfile
from typing import Union


class FixedZipFile(zipfile.ZipFile):
    """The python zipfile library doesn't do a good job handling unix
    permissions in zip files. Notably, it drops execute permissions on files."""

    def _extract_member(self, member, targetpath, pwd):
        """Extract the ZipInfo object 'member' to a physical
           file on the path targetpath.
        """
        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        # build the destination pathname, replacing
        # forward slashes to platform specific separators.
        arcname = member.filename.replace('/', os.path.sep)

        if os.path.altsep:
            arcname = arcname.replace(os.path.altsep, os.path.sep)
        # interpret absolute pathname as relative, remove drive letter or
        # UNC path, redundant separators, "." and ".." components.
        arcname = os.path.splitdrive(arcname)[1]
        invalid_path_parts = ('', os.path.curdir, os.path.pardir)
        arcname = os.path.sep.join(x for x in arcname.split(os.path.sep)
                                   if x not in invalid_path_parts)
        if os.path.sep == '\\':
            # filter illegal characters on Windows
            arcname = self._sanitize_windows_name(arcname, os.path.sep)

        targetpath = os.path.join(targetpath, arcname)
        targetpath = os.path.normpath(targetpath)

        # Create all upper directories if necessary.
        upperdirs = os.path.dirname(targetpath)
        if upperdirs and not os.path.exists(upperdirs):
            os.makedirs(upperdirs)

        if member.is_dir():
            if not os.path.isdir(targetpath):
                os.mkdir(targetpath)
            return targetpath

        with self.open(member, pwd=pwd) as source, \
                open(targetpath, "wb") as target:
            shutil.copyfileobj(source, target)

        # The Unix attributes are in the high order bits.
        mode = member.external_attr >> 16
        mode = mode & 0o770

        # Only apply them if they exist. Otherwise leave things as-is.
        if mode:
            os.chmod(targetpath, mode)

        return targetpath


class FixedTarFile(tarfile.TarFile):
    """Tarfile, except permissions on files and directories respect the umask."""

    def __init__(self, *args, umask=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._umask =  umask

    def chown(self, tarinfo, targetpath, numeric_owner: bool) -> None:
        """Never chown files, even if we're root."""

    def chmod(self, tarinfo, targetpath) -> None:
        """Chmod, minus umask bits."""

        if hasattr(os, 'chmod'):

            if self._umask is not None:
                mode = tarinfo.mode & ~self._umask
            else:
                mode = tarinfo.mode

            try:
                os.chmod(targetpath, mode)
            except OSError:
                raise tarfile.ExtractError("could not change mode")


def extract_tarball(src: pathlib.Path, dest: pathlib.Path, umask: int):
    """Extract the given tarball at 'src' to the directory 'dest'. If the
    tarball contains a single directory then that directory will be 'dest',
    otherwise the contents of the tarball will be extracted into 'dest'.

    :param src: The location of the tarball.
    :param dest: Where to extract to.
    :param umask: Umask to apply to extracted files.
    :returns: None if successful, an error message otherwise.
    """

    try:
        with FixedTarFile.open(src.as_posix(), umask=umask) as tar:
            # Filter out all but the top level items.
            top_level = [m for m in tar.members
                         if '/' not in m.name]

            for member in tar.members:
                mpath = pathlib.Path(member.name)
                if mpath.is_absolute():
                    return ("Tarfile '{}' contains members with absolute "
                            "paths, refusing to extract.".format(src))

            # If the file contains only a single directory,
            # make that directory the build directory. This
            # should be the default in most cases.
            if len(top_level) == 1 and top_level[0].isdir():
                tmpdir = dest.with_suffix('.extracted')
                tmpdir.mkdir()
                tar.extractall(tmpdir.as_posix())
                opath = tmpdir / top_level[0].name
                opath.rename(dest)
                tmpdir.rmdir()
            else:
                # Otherwise, the build path will contain the
                # extracted contents of the archive.
                dest.mkdir()
                tar.extractall(dest.as_posix())
    except (OSError, IOError,
            tarfile.CompressionError, tarfile.TarError) as err:
        return ("Could not extract tarfile '{}' into '{}': {}"
                .format(src, dest, err))


def decompress_file(src: pathlib.Path, dest: pathlib.Path, subtype: str) \
        -> Union[None, str]:
    """Decompress the given file according to its MIME subtype (gleaned
    from file magic).

    :returns: An error message on failure. None otherwise.
    """

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
        return ("Test src file '{}' is a bad tar file."
                .format(src))
    else:
        return ("Unhandled compression type. '{}' for source location {}."
                .format(subtype, src))

    decomp_fn = src.with_suffix('').name
    decomp_fn = dest / decomp_fn
    dest.mkdir()

    try:
        with comp_lib.open(src.as_posix()) as infile, \
                decomp_fn.open('wb') as outfile:
            shutil.copyfileobj(infile, outfile)
    except (OSError, IOError, lzma.LZMAError) as err:
        return ("Error decompressing compressed file '{}' into '{}':\n {}"
                .format(src, decomp_fn, err))


def unzip_file(src, dest):
    """Extract the contents of a zipfile."""

    tmpdir = dest.with_suffix('.unzipped')
    try:
        # Extract the zipfile, under the same conditions as
        # above with tarfiles.
        with FixedZipFile(src.as_posix()) as zipped:

            tmpdir.mkdir()
            zipped.extractall(tmpdir.as_posix())

            files = os.listdir(tmpdir.as_posix())
            if len(files) == 1 and (tmpdir / files[0]).is_dir():
                # Make the zip's root directory the build dir.
                (tmpdir / files[0]).rename(dest)
                tmpdir.rmdir()
            else:
                # The overall contents of the zip are the build dir.
                tmpdir.rename(dest)

    except (OSError, IOError, zipfile.BadZipFile) as err:
        return ("Could not extract zipfile '{}' into destination '{}': \n{}"
                .format(src, dest, err))
    finally:
        if tmpdir.exists():
            shutil.rmtree(tmpdir.as_posix())
