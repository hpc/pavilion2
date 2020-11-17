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

    def _extract_member(self, member: Union[str, zipfile.ZipInfo],
                        targetpath: str, pwd):
        """
        :param member:
        :param targetpath:
        :param pwd:
        :return:
        """

        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        file_path = super()._extract_member(member, targetpath, pwd)

        # The Unix attributes are in the high order bits.
        mode = member.external_attr >> 16
        # Only set the owner bits; the group and user bits will be applied
        # by the Permission manager.
        mode = mode & 0o700

        # Only apply them if they exist. Otherwise leave things as-is.
        if mode:
            os.chmod(file_path, mode)


def extract_tarball(src: pathlib.Path, dest: pathlib.Path):
    """Extract the given tarball at 'src' to the directory 'dest'. If the
    tarball contains a single directory then that directory will be 'dest',
    otherwise the contents of the tarball will be extracted into 'dest'.

    :param src: The location of the tarball.
    :param dest: Where to extract to.
    :returns: None if successful, an error message otherwise.
    """

    try:
        with tarfile.open(src.as_posix()) as tar:
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


def decompress_file(src: pathlib.Path, dest: pathlib.Path, subtype: str):
    """Decompress the given file according to its MIME subtype (gleaned
    from file magic)."""

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
        raise ("Unhandled compression type. '{}' for source location {}."
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
