"""This module contains a variety of helper functions that implement
common tasks, like command-line output and date formatting. These should
generally be used to help make Pavilion consistent across its code and
plugins.
"""

import datetime as dt
import errno
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Iterator, Union, TextIO
from typing import List


def str_bool(val):
    """Returns true if the string value is the string 'true' with allowances
    for capitalization."""

    if isinstance(val, str) and val.lower() == 'true':
        return True
    elif isinstance(val, bool):
        return val
    else:
        return False


# Python 3.5 issue. Python 3.6 Path.resolve() handles this correctly.
# pylint: disable=protected-access
def resolve_path(path, strict=False):
    """Stolen straight from python3.6 pathlib."""

    sep = '/'
    accessor = path._accessor
    seen = {}

    def _resolve(path_, rest):
        if rest.startswith(sep):
            path_ = ''

        for name in rest.split(sep):
            if not name or name == '.':
                # current dir
                continue
            if name == '..':
                # parent dir
                path_, _, _ = path_.rpartition(sep)
                continue
            newpath = str(path_) + sep + name
            if newpath in seen:
                # Already seen this path
                path_ = seen[newpath]
                if path_ is not None:
                    # use cached value
                    continue
                # The symlink is not resolved, so we must have a symlink loop.
                raise RuntimeError("Symlink loop from %r" % newpath)
            # Resolve the symbolic link
            try:
                target = accessor.readlink(newpath)
            except OSError as err:
                if err.errno != errno.EINVAL and strict:
                    raise
                # Not a symlink, or non-strict mode. We just leave the path
                # untouched.
                path_ = newpath
            else:
                seen[newpath] = None  # not resolved symlink
                path_ = _resolve(path_, target)
                seen[newpath] = path_  # resolved symlink

        return Path(path_)

    # NOTE: according to POSIX, getcwd() cannot contain path components
    # which are symlinks.
    base = '' if path.is_absolute() else os.getcwd()
    return _resolve(base, str(path)) or sep


def dir_contains(file, directory):
    """Check if 'file' is or is contained by 'directory'."""

    file = Path(file)
    directory = Path(directory)
    while file.parent != file:
        if file == directory:
            return True
        file = file.parent
    return False


def owner(path: Path) -> str:
    """Safely get the owner of a file, even if that user isn't known."""

    try:
        return path.owner()
    except KeyError:
        try:
            uid = path.stat().st_uid
        except OSError:
            uid = 'no_uid'
        return "<unknown user '{}'>".format(uid)


def make_umask_filtered_copystat(umask: int):
    """Create a 'copystat' function that first applies a umask to any permissions."""

    def copystat(src, dst, *, follow_symlinks=True):
        """Simplified python3.6 shutil that assumes Linux.  Doesn't copy xattrs,
        and masks permissions with the umask."""

        # follow symlinks (aka don't not follow symlinks)
        follow = follow_symlinks or not (os.path.islink(src) and os.path.islink(dst))

        stat = os.stat(src, follow_symlinks=follow)
        mode = stat.st_mode & 0o777 & ~umask
        os.utime(dst, ns=(stat.st_atime_ns, stat.st_mtime_ns), follow_symlinks=follow)
        try:
            os.chmod(dst, mode, follow_symlinks=follow)
        except NotImplementedError:
            pass

    return copystat


def copytree(src, dst, symlinks=False, ignore=None, copy_function=shutil.copy2,
             ignore_dangling_symlinks=False, copystat=shutil.copystat):
    """This is identical to the python 3.6 copytree, except the user can provide
    a copystat function."""
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.islink(srcname):
                linkto = os.readlink(srcname)
                if symlinks:
                    # We can't just leave it to `copy_function` because legacy
                    # code with a custom `copy_function` may rely on copytree
                    # doing the right thing.
                    os.symlink(linkto, dstname)
                    copystat(srcname, dstname, follow_symlinks=not symlinks)
                else:
                    # ignore dangling symlink if the flag is on
                    if not os.path.exists(linkto) and ignore_dangling_symlinks:
                        continue
                    # otherwise let the copy occurs. copy2 will raise an error
                    if os.path.isdir(srcname):
                        copytree(srcname, dstname, symlinks, ignore,
                                 copy_function, ignore_dangling_symlinks, copystat)
                    else:
                        copy_function(srcname, dstname)
                        copystat(srcname, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore, copy_function,
                         ignore_dangling_symlinks, copystat)
            else:
                # Will raise a SpecialFileError for unsupported file types
                copy_function(srcname, dstname)
                copystat(srcname, dstname)
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
    try:
        copystat(src, dst)
    except OSError as why:
        # Copying file access times may fail on Windows
        if getattr(why, 'winerror', None) is None:
            errors.append((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)
    return dst


def path_is_external(path: Path):
    """Returns True if a path contains enough back 'up-references' to escape
    the base directory."""

    up_refs = path.parts.count('..')
    not_up_refs = len([part for part in path.parts if part != '..'])
    return not_up_refs - up_refs <= 0


def flat_walk(path, *args, **kwargs) -> Iterator[Path]:
    """Perform an os.walk on path, but simply generate each item walked over.

:param Path path: The path to walk with os.walk.
:param args: Any additional positional args for os.walk.
:param kwargs: Any additional kwargs for os.walk.
"""

    for directory, dirnames, filenames in os.walk(str(path), *args, **kwargs):
        directory = Path(directory)
        for dirname in dirnames:
            yield directory / dirname

        for filename in filenames:
            yield directory / filename


def get_mime_type(path):
    """Use the filemagic command to get the mime type of a file. Returned as a
    tuple of category and subtype.

    :param Path path: The path to the file to examine.
    :rtype: (str, str)
    :returns: category, subtype"""

    ftype = subprocess.check_output(['file',
                                     # Don't print the filename
                                     '-b',
                                     # Mime types are more sane to deal with
                                     '--mime-type',
                                     str(path)])

    # Get rid of whitespace and convert to unicode, and split
    parts = ftype.strip().decode().split('/', 2)

    category = parts[0]
    subtype = parts[1] if len(parts) > 1 else None

    return category, subtype


def deserialize_datetime(when) -> float:
    """Return a datetime object from a serialized representation produced
    by serialize_datetime()."""

    if isinstance(when, float):
        return when

    if isinstance(when, str):
        when = dt.datetime.strptime(when, "%Y-%m-%d %H:%M:%S.%f")
        return when.timestamp()

    return 0


def get_login():
    """Get the current user's login, either through os.getlogin or
    the environment, or the id command."""

    # We've found this to be generally more reliable in sudo situations
    # than getlogin.
    if 'USER' in os.environ:
        return os.environ['USER']

    try:
        return os.getlogin()
    except OSError:
        pass

    try:
        name = subprocess.check_output(['id', '-un'],
                                       stderr=subprocess.DEVNULL)
        return name.decode('utf8').strip()
    except Exception:
        raise RuntimeError(
            "Could not get the name of the current user.")


class ZipFileFixed(zipfile.ZipFile):
    """Overrides the default behavior in ZipFile to preserve execute
    permissions."""
    def _extract_member(self, member, targetpath, pwd):

        ret = super()._extract_member(member, targetpath, pwd)

        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        perms = member.external_attr >> 16

        file_path = os.path.join(targetpath, member.filename)
        if perms != 0:
            try:
                os.chmod(file_path, perms)
            except OSError:
                pass

        return ret


def relative_to(other: Path, base: Path) -> Path:
    """Get a relative path from base to other, even if other isn't contained
    in base."""

    if not base.is_dir():
        raise ValueError(
            "The base '{}' must be a directory."
            .format(base))

    base = Path(resolve_path(base))
    other = Path(resolve_path(other))

    bparts = base.parts
    oparts = other.parts

    i = 0
    for i in range(min([len(bparts), len(oparts)])):
        if bparts[i] != oparts[i]:
            if i <= 1:
                # The paths have nothing in common, just return the other path.
                return other
            else:
                o_steps = i
                up_dirs = len(bparts) - i
                break
    else:
        o_steps = i + 1
        up_dirs = 0

    ref = ('..',) * up_dirs + oparts[o_steps:]
    return Path(*ref)


def repair_symlinks(base: Path) -> None:
    """Makes all symlinks under the path 'base' relative."""

    base = base.resolve()

    for file in flat_walk(base):

        if file.is_symlink():
            # Found a second thing that pathlib doesn't do (though a requst
            # for Path.readlink has already been merged in the Python develop
            # branch)
            target = Path(os.readlink(file.as_posix()))
            target = Path(resolve_path(target))
            sym_dir = file.parent
            if target.is_absolute() and dir_contains(target, base):
                rel_target = relative_to(target, sym_dir)
                file.unlink()
                file.symlink_to(rel_target)


def hr_cutoff_to_ts(cutoff_time: str,
                    _now: dt.datetime = None) -> Union[float, None]:
    """Convert a human readable datetime string to an actual datetime. The
    string can come in two forms:

    1. An ISO-8601 like timestamp (YYYY-MM-DD.HH:MM:SS), where the
       sep can be any non-digit. This can be partial; components may be left
       off from right to left. So '2019-3' is valid, but '3-12' is not.
    2. As an amount of time before the current time, expressed as an
       number followed by a unit. Valid units are seconds, minutes, hours,
       days, weeks, months (approximate), and years (or the singular form of
       those words). The value and unit may be separated by whitespace.
    3. An empty string, which implies no time (returns None).

    :param cutoff_time: The string time to parse.
    :param _now: For testing purposes. The current time.
    """

    if cutoff_time == '':
        return None

    if _now is None:
        now = dt.datetime.now()
    else:
        now = _now

    rel_time_regex = re.compile(r'^(\d+(?:\.\d+)?)\s*([a-z]+)$')
    ts_regex = re.compile(r'^(\d{4})'
                          r'(?:-(\d{1,2})'
                          r'(?:-(\d{1,2})'
                          r'(?:[T ](\d{1,2})'
                          r'(?::(\d{1,2})'
                          r'(?::(\d{1,2})?)?)?)?)?)?$')

    match = rel_time_regex.match(cutoff_time)
    if match is not None:
        time_amount = float(match.groups()[0])
        time_unit = match.groups()[1]

        # Convert time into hours.
        if time_unit == 'second' or time_unit == 'seconds':
            delta = dt.timedelta(seconds=time_amount)
        elif time_unit == 'minute' or time_unit == 'minutes':
            delta = dt.timedelta(minutes=time_amount)
        elif time_unit == 'hour' or time_unit == 'hours':
            delta = dt.timedelta(hours=time_amount)
        elif time_unit == 'day' or time_unit == 'days':
            delta = dt.timedelta(days=time_amount)
        elif time_unit == 'week' or time_unit == 'weeks':
            delta = dt.timedelta(weeks=time_amount)
        elif time_unit == 'month' or time_unit == 'months':
            delta = dt.timedelta(days=time_amount*365.25/12)
        elif time_unit == 'year' or time_unit == 'years':
            delta = dt.timedelta(days=time_amount*365.25)
        else:
            raise ValueError("Invalid unit time unit '{}'".format(time_unit))

        try:
            return (now - delta).timestamp()
        except OverflowError:
            # Make the assumption if the user asks for tests in the last
            # 10,000 year we just return the oldest possible datetime obj.
            return dt.datetime(1, 1, 1).timestamp()

    match = ts_regex.match(cutoff_time)
    if match is not None:

        parts = [part if part is None else int(part)
                 for part in match.groups()]
        # Set defaults for missing parts
        defaults = (1, 1, 1, 0, 0, 0)
        for i in (1, 2, 3, 4, 5):
            if parts[i] is None:
                parts[i] = defaults[i]

        try:
            return dt.datetime(*parts).timestamp()
        except ValueError as err:
            raise ValueError(
                "Invalid time '{}':\n{}".format(cutoff_time, err.args[0])
            )

    raise ValueError("Invalid cutoff value '{}'".format(cutoff_time))


def union_dictionary(dict1, dict2):
    """Combines two dictionaries with nested lists."""

    for key in dict2.keys():
        dict1[key] = dict1.get(key, []) + dict2[key]

    return dict1

def flatten_nested_dict(dict_in, keycollect='', new_d=dict(), keysplit='.'):
    """ Takes a nested dictionary and concatenates its nested keys
    in a single key at the top level.

    Remove keys whose value evaluates to False.
    If dict_in has only one key and it's not the final key, discard it.
    Remove key concatenator from front/back of key string.
    """

    knew = keycollect
    for k, v in dict_in.items():
        if not v:
            continue
        if len(dict_in.keys()) > 1 or not isinstance(v, dict):
            knew = keysplit.join([keycollect,k])
        if not isinstance(v, dict):
            knew = knew.strip(keysplit)
            new_d[knew] = v
        else:
            new_d = flatten_nested_dict(v, knew, new_d.copy())

    return new_d


def flatten_dictionaries(nested_dicts):
    """ Takes a (possibly nested) dictionary or list of dictionaries
    and returns a dictionary that contains only (key: value) pairs
    by merging nested keys.

    Remove keys whose value evaluates to False.
    Returns the type you gave it, list or dict.
    When when flattening a sub dictionary, check that the resulting
    keys are not already in the main dict to be overwritten when
    the flattened key:values are added. If the key is present,
    append the parent dictionary key referring to the sub dictionary
    to the flattened key and add to the flattened dictionary.
    """
    dictout = isinstance(nested_dicts, dict)
    flat_dicts=[]

    if dictout:
        nested_ds = [nested_dicts]
    else:
        nested_ds = nested_dicts[:]

    for nested_dict in nested_ds:
        flat_dict = dict()
        ndkeys = list(nested_dict.keys())
        for k, v in nested_dict.items():
            if not v:
                continue
            elif isinstance(v, dict):
                flatv = flatten_nested_dict(v)
                for kf, vf in flatv.items():
                    kfa = kf
                    if kf in ndkeys:
                        kfa = ".".join([k,kf])
                    flat_dict[kfa] = vf
                flatv.clear()
            else:
                flat_dict[k] = v

        flat_dicts.append(flat_dict)

    if dictout:
        flat_dicts = flat_dicts[0]

    return flat_dicts



def auto_type_convert(value):
    """Try to convert 'value' to a int, float, or bool. Otherwise leave
    as a string. This is done recursively with complex values."""

    if value is None:
        return None

    if isinstance(value, list):
        return [auto_type_convert(item) for item in value]
    elif isinstance(value, dict):
        return {key: auto_type_convert(val) for key, val in value.items()}

    if isinstance(value, (int, float, bool)):
        return value

    # Probably a string?
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    if value in ('True', 'False'):
        return value == 'True'

    return value


class IndentedLog:
    """A logging object for writing indented, easy to follow logs."""

    INDENT = '  '

    def __init__(self):

        self.lines = []

    def __call__(self, msg):
        """Write the message to log with the set indentation level."""

        self.lines.append(msg)

    def save(self, file: TextIO):
        """Save the log to the given path."""

        for line in self.lines:
            file.write(line)
            file.write('\n')

    def indent(self, log: Union['IndentedLog', List[str], str]):
        """Extend the log with the given lines, indenting them one level."""

        if isinstance(log, IndentedLog):
            lines = log.lines
        elif isinstance(log, list):
            lines = log
        elif isinstance(log, str):
            lines = log.split('\n')
        else:
            raise TypeError("The 'log' argument must be a string, list of strings, or "
                            "an IndentedLog object.")

        for line in lines:
            for part in line.split('\n'):
                self.lines.append(self.INDENT + part)
