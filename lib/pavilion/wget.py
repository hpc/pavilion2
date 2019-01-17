import urllib.parse
import requests
import os
import tempfile
import dbm
import logging

LOGGER = logging.getLogger('pavilion.' + __file__)


class WGetError(RuntimeError):
    pass


# How many times to follow redirects in a 'head' call before giving up and returning whatever we
# last got.
REDIRECT_LIMIT = 10


def get(pav_cfg, url, dest):
    """Download the file at the given url and store it at dest. If a file already exists at dest
    it will be overwritten (assuming we have the permissions to do so). Proxies are handled
    automatically based on pav_cfg settings. This is done atomically; the download is saved to an
    intermediate location and then moved.
    :param pav_cfg: The pavilion configuration object.
    :param str url: The url for the file to download.
    :param str dest: The path to where the file will be stored.
    """

    proxies = _get_proxies(pav_cfg, url)

    session = requests.Session()
    session.trust_env = False

    dest_dir = os.path.dirname(os.path.realpath(dest))

    try:
        with session.get(url, proxies=proxies, stream=True) as response, \
              tempfile.NamedTemporaryFile(dir=dest_dir, delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=4096):
                tmp.write(chunk)
    except requests.exceptions.RequestException as err:
        # The requests package exceptions are pretty descriptive already.
        raise WGetError(err)
    except (IOError, OSError) as err:
        raise WGetError("Error writing download '{}' to file in '{}': {}"
                        .format(url, dest_dir, err))

    try:
        os.rename(tmp.name, dest)
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
        response = session.head(url, proxies=proxies)
        # The location header is the redirect location. While the requests library resolves these
        # automatically, it still returns the first header result from a 'head' call. We need to
        # follow these manually, up to a point.
        while 'Location' in response.headers and response.headers['Location'] != url:
            redirects += 1
            if redirects > REDIRECT_LIMIT:
                return response
            redirect_url = response.headers['Location']
            proxies = _get_proxies(pav_cfg, redirect_url)
            response = session.head(redirect_url, proxies=proxies)

    except requests.exceptions.RequestException as err:
        raise WGetError(err)

    return response.headers


def _get_proxies(pav_cfg, url):
    """Figure out the proxies based on the the pav_cfg and the particular url we're going to.
    This mostly handles disabling the proxy for internal urls.
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


def _get_info(path):
    """Get the contents of the info file for the given file, which is located at <filename>.info.
    Additionally, add some useful stat information to the info object we return.
    :param str path: The path to the file we want the info object for.
    :returns: A dictionary of the info information.
    :rtype dict:
    """

    info_fn = '{}.info'.format(path)

    info = {}

    if os.path.isfile(info_fn):
        try:
            with dbm.open(info_fn) as db:

                for key in db.keys():
                    # Convert everything to unicode.
                    info[key.decode('utf-8')] = db[key].decode('utf-8')

        except dbm.error as err:
            LOGGER.warning("Error reading dbm file '{}': {}".format(info_fn, err))

    stat = os.stat(path)

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
    :param str path: The path to the file we're creating the info object for.
    :param dict head_data: The header information from an http HEAD request for the object.
    """

    info_fn = '{}.info'.format(path)

    try:
        with dbm.open(info_fn, 'n') as db:
            for field in INFO_HEADER_FIELDS:
                if field in head_data:
                    db[field] = head_data[field]
    except dbm.error as err:
        LOGGER.warning("Error writing dbm file '{}': {}".format(info_fn, err))


def update(pav_cfg, url, dest):
    """Check if the file needs to be re-downloaded, and do so if necessary. This will
    careate a '{dest}.info' file in the same directory that will be used to check if updates are
    necessary.
    :param pav_cfg: The pavilion configuration object.
    :param str url: The url for the file to download.
    :param str dest: The path to where we want to store the file.
    """

    fetch = False

    info_path = '{}.info'.format(dest)

    head_data = head(pav_cfg, url)

    # If the file doesn't exist, just get it.
    if not os.path.exists(dest):
        fetch = True
    else:
        info = _get_info(dest)

        # If the file .info file doesn't exist, check to see if we can get a matching
        # Content-Length and fetch it if we can't.
        if not os.path.exists(info_path) and head_data.get('Content-Length') != info['size']:
            fetch = True

        # If we do have an info file and neither the ETag or content length match, refetch.
        # Note that the content length vs saved length depends on the transfer encoding. It should
        # match for any already compressed files, but other data types are frequently compressed.
        elif not (info['ETag'] == head_data.get('ETag') or
                  # If the old content length is the same, it's probably unchanged. Probably...
                  head_data.get('Content-Length') == info['Content-Length'] or
                  # Or if the content length matches the actual size.
                  head_data.get('Content-Length') == info['size']):
            fetch = True

    if fetch:
        get(pav_cfg, url, dest)
        _save_info(dest, head_data)
