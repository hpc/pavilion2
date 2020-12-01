# pylint: disable=C0413

from pathlib import Path
import json
import logging
import tempfile
import urllib.parse

_MISSING_LIBS = []
try:
    import ssl  # pylint: disable=W0611
except ImportError:
    _MISSING_LIBS.append('ssl')
    ssl = None

try:
    import requests
except ImportError as err:
    if hasattr(err, 'name'):
        _MISSING_LIBS.append(err.name)
    else:
        _MISSING_LIBS.append(err)

    requests = None

LOGGER = logging.getLogger('pavilion.' + __file__)


def missing_libs():
    """You should call this before using the wget module functions, to ensure
    all the dependencies are available.
    :returns: A list of one or more missing libraries. It won't necessarily
    catch them all in one pass. An empty list is good.
    """
    return _MISSING_LIBS


class WGetError(RuntimeError):
    pass


# How many times to follow redirects in a 'head' call before giving up and
# returning whatever we last got.
REDIRECT_LIMIT = 10


def get(pav_cfg, url, dest):
    """Download the file at the given url and store it at dest. If a file
    already exists at dest it will be overwritten (assuming we have the
    permissions to do so). Proxies are handled automatically based on
    pav_cfg settings. This is done atomically; the download is saved to an
    intermediate location and then moved.
    :param pav_cfg: The pavilion configuration object.
    :param str url: The url for the file to download.
    :param Path dest: The path to where the file will be stored.
    """

    proxies = _get_proxies(pav_cfg, url)

    session = requests.Session()
    session.trust_env = False

    dest_dir = dest.parent.resolve()

    try:
        response = session.get(url, proxies=proxies, stream=True,
                               timeout=pav_cfg.wget_timeout)
        with tempfile.NamedTemporaryFile(dir=str(dest_dir),
                                         delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=4096):
                tmp.write(chunk)
    except requests.exceptions.RequestException as err:
        # The requests package exceptions are pretty descriptive already.
        raise WGetError(err)
    except (IOError, OSError) as err:
        raise WGetError("Error writing download '{}' to file in '{}': {}"
                        .format(url, dest_dir, err))

    try:
        Path(tmp.name).rename(dest)
    except (IOError, OSError) as err:
        raise WGetError("Error moving file from '{}' to final location '{}': {}"
                        .format(url, dest, err))


def head(pav_cfg, url):
    """Get the header information for the given url.
    :param pav_cfg: The pavilion configuration object
    :param str url: The url we need information on.
    :returns: The http headers for the given url.
    :rtype dict:
    """

    proxies = _get_proxies(pav_cfg, url)

    session = requests.Session()
    session.trust_env = False

    redirects = 0

    try:
        response = session.head(url,
                                proxies=proxies,
                                timeout=pav_cfg.wget_timeout)
        # The location header is the redirect location. While the requests
        # library resolves these automatically, it still returns the first
        # header result from a 'head' call. We need to follow these
        # manually, up to a point.
        while ('Location' in response.headers and
               response.headers['Location'] != url):
            redirects += 1
            if redirects > REDIRECT_LIMIT:
                return response
            redirect_url = response.headers['Location']
            proxies = _get_proxies(pav_cfg, redirect_url)
            response = session.head(redirect_url,
                                    proxies=proxies,
                                    timeout=pav_cfg.wget_timeout)

    except requests.exceptions.RequestException as err:
        raise WGetError(err)

    return response.headers


def _get_proxies(pav_cfg, url):
    """Figure out the proxies based on the the pav_cfg and the particular url
    we're going to. This mostly handles disabling the proxy for internal urls.
    :param pav_cfg: The pavilion config object.
    :param str url: The url we hope to go to.
    :returns: The proxy dictionary.
    :rtype dict:
    """

    parsed_url = urllib.parse.urlparse(url)
    host = '.' + parsed_url.netloc

    for suffix in pav_cfg.no_proxy:
        if host.endswith('.' + suffix):
            return None

    return pav_cfg.proxies


def _get_info_fn(path):
    """Return the path to the info filename for the given path."""

    info_fn = '.' + path.with_suffix(path.suffix + '.info').name
    return path.parent/info_fn


def _get_info(path):
    """Get the contents of the info file for the given file.
    Additionally, add some useful stat information to the info object we return.
    :param Path path: The path to the file we want the info object for.
    :returns: A dictionary of the info information.
    :rtype dict:
    """

    info_fn = _get_info_fn(path)

    info = {}

    if info_fn.is_file():
        try:
            with info_fn.open() as info_file:
                info = json.load(info_file)

        except (ValueError, IOError, OSError) as err:
            LOGGER.warning("Error reading json file '%s': %s",
                           info_fn, err)

    stat = path.stat()

    info['mtime'] = stat.st_mtime
    info['ctime'] = stat.st_ctime
    info['size'] = stat.st_size

    return info


# The fields to save into our info files.
INFO_HEADER_FIELDS = [
    'Content-Length',
    'Content-Encoding',
    'ETag',
]


def _save_info(path, head_data):
    """Given the path and the http head data, create an info file.
    :param Path path: The path to the file we're creating the info object for.
    :param dict head_data: The header information from an http HEAD request
    for the object.
    """

    info_fn = _get_info_fn(path)

    data = {}
    for field in INFO_HEADER_FIELDS:
        if field in head_data:
            data[field] = head_data[field]

    try:
        with info_fn.open('w') as info_file:
            json.dump(data, info_file)

    except (ValueError, TypeError, IOError, OSError) as err:
        LOGGER.warning("Error writing info file '%s': %s", info_fn, err)


def update(pav_cfg, url, dest):
    """Check if the file needs to be re-downloaded, and do so if necessary.
    This will create a '{dest}.info' file in the same directory that will
    be used to check if updates are necessary.
    :param pav_cfg: The pavilion configuration object.
    :param str url: The url for the file to download.
    :param Path dest: The path to where we want to store the file.
    """

    fetch = False

    info_path = _get_info_fn(dest)

    head_data = None

    # If the file doesn't exist, just get it.
    if not dest.exists():
        fetch = True
    else:
        head_data = head(pav_cfg, url)

        info = _get_info(dest)

        # If the file .info file doesn't exist, check to see if we can get a
        # matching Content-Length and fetch it if we can't.
        if (not info_path.exists() and
                (head_data.get('Content-Length') != info['size'])):
            fetch = True

        # If we do have an info file and neither the ETag or content length
        # match, refetch. Note that the content length vs saved length
        # depends on the transfer encoding. It should match for any already
        # compressed files, but other data types are frequently compressed.
        elif (not (
                info.get('ETag') == head_data.get('ETag') or
                # If the old content length is the same, it's probably
                # unchanged. Probably...
                head_data.get('Content-Length') == info.get('Content-Length') or
                # Or if the content length matches the actual size.
                head_data.get('Content-Length') == info['size'])):
            fetch = True

    if fetch:
        if head_data is None:
            head_data = head(pav_cfg, url)

        get(pav_cfg, url, dest)
        _save_info(dest, head_data)
